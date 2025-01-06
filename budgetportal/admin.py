import logging
from io import StringIO


from adminsortable.admin import SortableAdmin, SortableTabularInline
from budgetportal import models
# from budgetportal.bulk_upload import bulk_upload_view
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.views.generic import TemplateView
from import_export.admin import ImportMixin
from import_export.formats.base_formats import CSV, XLSX
from django.db import transaction, IntegrityError


import os
import csv
import budgetportal

from django_q.conf import Conf
from django_q.models import Success, Failure, Schedule, OrmQ
from django_q.tasks import async_task

from budgetportal import tasks
from budgetportal.tasks import import_irm_snapshot
from budgetportal.dataset_uploading.dataset_preprocessor import import_dataset

from .import_export_admin import (
    DepartmentImportForm,
    DepartmentResource,
    InfrastructureProjectResource,
)

logger = logging.getLogger(__name__)
admin.site.login = login_required(admin.site.login)


class FinancialYearAdmin(admin.ModelAdmin):
    pass


class SphereAdmin(admin.ModelAdmin):
    readonly_fields = ("slug",)


class GovernmentAdmin(admin.ModelAdmin):
    readonly_fields = ("slug",)


class GovtFunctionAdmin(admin.ModelAdmin):
    readonly_fields = ("slug",)


class InfrastructureProjectAdmin(ImportMixin, admin.ModelAdmin):
    resource_class = InfrastructureProjectResource
    formats = [XLSX, CSV]


class DepartmentAdmin(ImportMixin, admin.ModelAdmin):
    # Resource class to be used by the django-import-export package
    resource_class = DepartmentResource
    # File formats that can be used to import departments
    formats = [CSV]

    def get_import_form(self):
        """
        Get the import form to use by the django-import-export package
        to import departments.
        """
        return DepartmentImportForm

    def get_resource_kwargs(self, request, *args, **kwargs):
        """
        Get the kwargs to send on to the department resource when
        we import departments.
        """
        if "sphere" in request.POST:
            return {"sphere": request.POST["sphere"]}
        return {}

    list_display = (
        "vote_number",
        "name",
        "get_government",
        "get_sphere",
        "get_financial_year",
    )
    list_display_links = ("vote_number", "name")
    list_filter = (
        "government__sphere__financial_year__slug",
        "government__sphere__name",
        "government__name",
    )
    search_fields = (
        "government__sphere__financial_year__slug",
        "government__sphere__name",
        "government__name",
        "name",
    )
    readonly_fields = ("slug",)
    list_per_page = 20

    def get_government(self, obj):
        return obj.government.name

    def get_sphere(self, obj):
        return obj.government.sphere.name

    def get_financial_year(self, obj):
        return obj.government.sphere.financial_year.slug


class ProgrammeAdmin(admin.ModelAdmin):
    list_display = (
        "programme_number",
        "name",
        "get_department",
        "get_government",
        "get_sphere",
        "get_financial_year",
    )
    list_display_links = ("programme_number", "name")
    list_filter = (
        "department__government__sphere__financial_year__slug",
        "department__government__sphere__name",
        "department__government__name",
        "department__name",
    )
    search_fields = (
        "department__government__sphere__financial_year__slug",
        "department__government__sphere__name",
        "department__government__name",
        "department__name",
        "name",
    )
    readonly_fields = ("slug",)

    def get_department(self, obj):
        return obj.department.name

    def get_government(self, obj):
        return obj.department.government.name

    def get_sphere(self, obj):
        return obj.department.government.sphere.name

    def get_financial_year(self, obj):
        return obj.department.government.sphere.financial_year.slug


class EntityDatasetsView(TemplateView):
    template_name = "admin/entity_datasets.html"
    financial_year_slug = None
    sphere_slug = None

    def get_context_data(self, **kwargs):
        sphere = models.Sphere.objects.get(
            financial_year__slug=self.financial_year_slug, slug=self.sphere_slug
        )
        return {"sphere": sphere}


class UserAdmin(admin.ModelAdmin):
    pass


class SiteAdmin(admin.ModelAdmin):
    pass


class VideoLanguageInline(SortableTabularInline):
    model = models.VideoLanguage


class FAQAdmin(admin.ModelAdmin):
    model = models.FAQ


class VideoAdmin(SortableAdmin):
    inlines = [VideoLanguageInline]
    model = models.Video

class ENEDataAdmin(admin.ModelAdmin):
    model = models.ENEData

class IRMSnapshotAdmin(admin.ModelAdmin):
    pass

    def save_model(self, request, obj, form, change):
        logger.info("save_model called")
        if not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)
        obj.save()
        obj.task_id = async_task(
            func=handle_irm_snapshot_post_save, obj_id=obj.id)
        
        # handle_irm_snapshot_post_save(obj.id)
        


def handle_irm_snapshot_post_save(obj_id):

    async_task(
        tasks.import_irm_snapshot,
        snapshot_id=obj_id,
        task_name="Import IRM Snappshot file of infrastructue projects",
    )   


class InfraProjectSnapshotInline(admin.TabularInline):
    model = models.InfraProjectSnapshot
    fields = ["name", "province", "department", "status", "irm_snapshot"]
    readonly_fields = fields


class InfraProjectAdmin(admin.ModelAdmin):
    model = models.InfraProject
    inlines = [InfraProjectSnapshotInline]
    readonly_fields = ["IRM_project_id"]
    list_filter = (
        "project_snapshots__irm_snapshot__sphere__slug",
        "project_snapshots__irm_snapshot",
        "project_snapshots__province",
        "project_snapshots__department",
    )
    search_fields = ("project_snapshots__name",
                     "project_snapshots__project_number")

    
class InfraProjectSnapshotAdmin(admin.ModelAdmin):
    list_display = ("name", "project_number", "province",
                    "department", "irm_snapshot")
    list_display_links = ("name", "project_number")
    list_filter = (
        "irm_snapshot__sphere__financial_year__slug",
        "irm_snapshot__sphere__slug",
        "province",
        "department",
    )
    search_fields = ("name", "project_number")
    list_per_page = 20

    def get_readonly_fields(self, request, obj=None):
        return list(
            set(
                [field.name for field in self.opts.local_fields]
                + [field.name for field in self.opts.local_many_to_many]
            )
        )


# admin.site.register_view("bulk_upload", "Bulk Upload", view=bulk_upload_view)

class SubMenuItemInline(SortableTabularInline):
    model = models.SubMenuItem


class MainMenuItemAdmin(SortableAdmin):
    inlines = [SubMenuItemInline]
    model = models.MainMenuItem


class ShowcaseItemAdmin(SortableAdmin):
    list_display = ("name", "description", "created_at")
    model = models.ShowcaseItem

class DatasetResourceInline(admin.TabularInline):  # or `admin.StackedInline` for a different layout
    model = models.DatasetResource 
    extra = 1

class DatasetCategoryAdmin(SortableAdmin):
    list_display = ("title", "description")
    model = models.DatasetCategory

class DimensionAdmin(SortableAdmin):
    model = models.Dimension

class OrganisationAdmin(SortableAdmin):
    model = models.Organisation

class TagAdmin(SortableAdmin):
    model = models.Tag

class DatasetAdmin(SortableAdmin):
    inlines = [DatasetResourceInline]
    model = models.Dataset    
    list_display = ('title', 'slug', 'visibility', 'dataset_category')

class GovernmentFunctionAdmin(SortableAdmin):
    model = models.GovernmentFunction


def generate_import_report(
    not_matching_departments
):
    report = ""

    if len(not_matching_departments) > 0:
        report += "Department names that could not be matched on import : " + os.linesep
        for department in not_matching_departments:
            report += f"* {department} {os.linesep}"

    return report



def validate_report_type(full_text, obj_id):
    validated = False

    if not validated:
        obj_to_update = models.DatasetUpload.objects.get(id=obj_id)
        obj_to_update.num_imported = None
        obj_to_update.num_not_imported = None
        obj_to_update.import_report = generate_import_report([])
        obj_to_update.save()

    return validated


def save_imported_dataset(obj_id):

    import_dataset(obj_id)

    # async_task(
    #     import_dataset(obj_id),
    #     id=obj_id,
    #     task_name="Import dataset",
    # )   


class DatasetUploadAdmin(admin.ModelAdmin):
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)
        # It looks like the task isn't saved synchronously, so we can't set the
        # task as a related object synchronously. We have to fetch it by its ID
        # when we want to see if it's available yet.
        save_imported_dataset(obj.id)
        # obj.task_id = async_task(func=save_imported_dataset, obj_id=obj.id)
        # obj.save()

    def processing_completed(self, obj):
        task = fetch(obj.task_id)
        if task:
            return task.success

    processing_completed.boolean = True
    processing_completed.short_description = "Processing completed"


def register_site_model():
    from wagtail.core.models import Page  # Local import avoids circular dependency
    admin.site.register(Page)

register_site_model()


admin.site.register(models.FinancialYear, FinancialYearAdmin)
admin.site.register(models.Sphere, SphereAdmin)
admin.site.register(models.Government, GovernmentAdmin)
admin.site.register(models.GovtFunction, GovtFunctionAdmin)
admin.site.register(models.Department, DepartmentAdmin)
admin.site.register(models.InfrastructureProjectPart,
                    InfrastructureProjectAdmin)
admin.site.register(models.Programme, ProgrammeAdmin)
admin.site.register(models.DatasetCategory, DatasetCategoryAdmin)
admin.site.register(models.Dimension, DimensionAdmin)
admin.site.register(models.Organisation, OrganisationAdmin)
admin.site.register(models.Tag, TagAdmin)
admin.site.register(models.Dataset, DatasetAdmin)
admin.site.register(models.GovernmentFunction, GovernmentFunctionAdmin)
# admin.site.register(User, UserAdmin)
# admin.site.register(Site, SiteAdmin)
admin.site.register(models.Video, VideoAdmin)
admin.site.register(models.Event)
admin.site.register(models.FAQ, FAQAdmin)
admin.site.register(models.InfraProject, InfraProjectAdmin)
admin.site.register(models.InfraProjectSnapshot, InfraProjectSnapshotAdmin)
admin.site.register(models.IRMSnapshot, IRMSnapshotAdmin)
admin.site.register(models.Homepage, admin.ModelAdmin)
admin.site.register(models.CategoryGuide)
admin.site.register(models.MainMenuItem, MainMenuItemAdmin)
admin.site.register(models.Notice, SortableAdmin)
admin.site.register(models.ShowcaseItem, ShowcaseItemAdmin)
admin.site.register(models.ENEData, ENEDataAdmin)
admin.site.register(models.DatasetUpload, DatasetUploadAdmin)
