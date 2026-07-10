from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django_q.tasks import async_task
from django.urls import path, reverse

from .models import DatasetImportJob, DatasetPreparationJob
from .tasks import (
    queue_dataset_import_job,
    queue_excel_conversion_job,
    run_dataset_preparation_job,
)


class DatasetImportJobInline(admin.TabularInline):
    model = DatasetImportJob
    extra = 0
    can_delete = False
    readonly_fields = (
        "dataset_type",
        "status",
        "imported_rows",
        "duration_seconds",
        "dataset_upload",
        "task_id",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields


@admin.register(DatasetPreparationJob)
class DatasetPreparationJobAdmin(admin.ModelAdmin):
    inlines = (DatasetImportJobInline,)
    actions = ("queue_both_imports", "queue_excel_conversions")
    change_form_template = "admin/dataset_preparation/datasetpreparationjob/change_form.html"
    list_display = (
        "source_url",
        "dataset_type",
        "financial_year",
        "status",
        "epre_prepared_rows",
        "budget_vs_actual_prepared_rows",
        "duration_seconds",
        "user",
        "created_at",
    )
    readonly_fields = (
        "status",
        "user",
        "raw_file",
        "prepared_file",
        "prepared_excel_file",
        "budget_vs_actual_file",
        "budget_vs_actual_excel_file",
        "log",
        "error_message",
        "task_id",
        "excel_conversion_status",
        "excel_conversion_task_id",
        "epre_prepared_rows",
        "budget_vs_actual_prepared_rows",
        "duration_seconds",
        "created_at",
        "updated_at",
    )
    fields = (
        "source_url",
        "dataset_type",
        "financial_year",
        "sheet_name",
        "status",
        "user",
        "raw_file",
        "prepared_file",
        "prepared_excel_file",
        "budget_vs_actual_file",
        "budget_vs_actual_excel_file",
        "log",
        "error_message",
        "task_id",
        "excel_conversion_status",
        "excel_conversion_task_id",
        "epre_prepared_rows",
        "budget_vs_actual_prepared_rows",
        "duration_seconds",
        "created_at",
        "updated_at",
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/queue-epre-import/",
                self.admin_site.admin_view(self.queue_epre_import_view),
                name="dataset_preparation_datasetpreparationjob_queue_epre_import",
            ),
            path(
                "<path:object_id>/queue-both-imports/",
                self.admin_site.admin_view(self.queue_both_imports_view),
                name="dataset_preparation_datasetpreparationjob_queue_both_imports",
            ),
            path(
                "<path:object_id>/queue-excel-conversion/",
                self.admin_site.admin_view(self.queue_excel_conversion_view),
                name="dataset_preparation_datasetpreparationjob_queue_excel_conversion",
            ),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["queue_epre_import_url"] = reverse(
            "admin:dataset_preparation_datasetpreparationjob_queue_epre_import",
            args=[object_id],
        )
        extra_context["queue_both_imports_url"] = reverse(
            "admin:dataset_preparation_datasetpreparationjob_queue_both_imports",
            args=[object_id],
        )
        extra_context["queue_excel_conversion_url"] = reverse(
            "admin:dataset_preparation_datasetpreparationjob_queue_excel_conversion",
            args=[object_id],
        )
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        super().save_model(request, obj, form, change)
        if not change:
            obj.task_id = async_task(run_dataset_preparation_job, job_id=obj.id)
            obj.save(update_fields=["task_id", "updated_at"])

    def _queue_imports_for_preparation(self, request, preparation_job, dataset_types):
        queued = 0
        import_jobs = preparation_job.import_jobs.filter(dataset_type__in=dataset_types)
        if not import_jobs.exists():
            self.message_user(
                request,
                "Preparation job {} has no import jobs yet. Wait for preparation to finish first.".format(
                    preparation_job.id
                ),
                level=messages.WARNING,
            )
            return queued

        for import_job in import_jobs:
            if import_job.status not in (
                DatasetImportJob.STATUS_PENDING,
                DatasetImportJob.STATUS_FAILED,
            ):
                continue
            try:
                queue_dataset_import_job(import_job)
                queued += 1
            except Exception as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
        return queued

    def queue_epre_import_view(self, request, object_id):
        preparation_job = self.get_object(request, object_id)
        queued = self._queue_imports_for_preparation(
            request,
            preparation_job,
            [DatasetImportJob.DATASET_TYPE_EPRE],
        )
        self.message_user(request, "{} import job(s) queued.".format(queued))
        return HttpResponseRedirect(
            reverse("admin:dataset_preparation_datasetpreparationjob_change", args=[object_id])
        )

    def queue_both_imports_view(self, request, object_id):
        preparation_job = self.get_object(request, object_id)
        queued = self._queue_imports_for_preparation(
            request,
            preparation_job,
            [
                DatasetImportJob.DATASET_TYPE_EPRE,
                DatasetImportJob.DATASET_TYPE_BVA_PROVINCIAL,
            ],
        )
        self.message_user(request, "{} import job(s) queued.".format(queued))
        return HttpResponseRedirect(
            reverse("admin:dataset_preparation_datasetpreparationjob_change", args=[object_id])
        )

    def queue_excel_conversion_view(self, request, object_id):
        preparation_job = self.get_object(request, object_id)
        try:
            queue_excel_conversion_job(preparation_job)
            self.message_user(request, "Excel conversion queued.")
        except Exception as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
        return HttpResponseRedirect(
            reverse("admin:dataset_preparation_datasetpreparationjob_change", args=[object_id])
        )

    def queue_both_imports(self, request, queryset):
        queued = 0
        for preparation_job in queryset:
            queued += self._queue_imports_for_preparation(
                request,
                preparation_job,
                [
                    DatasetImportJob.DATASET_TYPE_EPRE,
                    DatasetImportJob.DATASET_TYPE_BVA_PROVINCIAL,
                ],
            )

        self.message_user(request, "{} import job(s) queued.".format(queued))

    queue_both_imports.short_description = "Queue both imports for selected preparation jobs"

    def queue_excel_conversions(self, request, queryset):
        queued = 0
        for preparation_job in queryset:
            try:
                queue_excel_conversion_job(preparation_job)
                queued += 1
            except Exception as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
        self.message_user(request, "{} Excel conversion job(s) queued.".format(queued))

    queue_excel_conversions.short_description = "Queue Excel conversions for selected preparation jobs"


@admin.register(DatasetImportJob)
class DatasetImportJobAdmin(admin.ModelAdmin):
    list_display = (
        "preparation_job",
        "dataset_type",
        "status",
        "imported_rows",
        "duration_seconds",
        "dataset_upload",
        "created_at",
    )
    list_filter = ("dataset_type", "status", "preparation_job__financial_year")
    readonly_fields = (
        "preparation_job",
        "dataset_type",
        "status",
        "task_id",
        "log",
        "error_message",
        "imported_rows",
        "duration_seconds",
        "dataset_upload",
        "created_at",
        "updated_at",
    )
    actions = ("queue_selected_imports",)

    def queue_selected_imports(self, request, queryset):
        queued = 0
        for job in queryset:
            if job.status not in (DatasetImportJob.STATUS_PENDING, DatasetImportJob.STATUS_FAILED):
                continue
            try:
                queue_dataset_import_job(job)
                queued += 1
            except Exception as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
        self.message_user(request, "{} import job(s) queued.".format(queued))

    queue_selected_imports.short_description = "Queue selected import jobs"
