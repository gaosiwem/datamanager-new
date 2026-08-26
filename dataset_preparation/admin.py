from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django_q.tasks import async_task
from django.urls import path, reverse

from .models import DatasetImportJob, DatasetPreparationJob
from .services import get_preparation_dataset_config
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
    actions = ("queue_pair_imports", "queue_excel_conversions")
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
        "consolidated_file",
        "consolidated_excel_file",
        "log",
        "error_message",
        "task_id",
        "excel_conversion_status",
        "excel_conversion_task_id",
        "epre_prepared_rows",
        "budget_vs_actual_prepared_rows",
        "consolidated_prepared_rows",
        "duration_seconds",
        "created_at",
        "updated_at",
    )
    fields = (
        "source_url",
        "dataset_type",
        "consolidation_source_url",
        "financial_year",
        "sheet_name",
        "status",
        "user",
        "raw_file",
        "prepared_file",
        "prepared_excel_file",
        "budget_vs_actual_file",
        "budget_vs_actual_excel_file",
        "consolidated_file",
        "consolidated_excel_file",
        "log",
        "error_message",
        "task_id",
        "excel_conversion_status",
        "excel_conversion_task_id",
        "epre_prepared_rows",
        "budget_vs_actual_prepared_rows",
        "consolidated_prepared_rows",
        "duration_seconds",
        "created_at",
        "updated_at",
    )

    secondary_output_fields = (
        "budget_vs_actual_file",
        "budget_vs_actual_excel_file",
        "budget_vs_actual_prepared_rows",
    )
    consolidation_output_fields = (
        "consolidated_file",
        "consolidated_excel_file",
        "consolidated_prepared_rows",
    )

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if obj:
            config = get_preparation_dataset_config(obj.dataset_type)
            hidden_fields = set()
            if not config.get("budget_vs_actual_dataset_type"):
                hidden_fields.update(self.secondary_output_fields)
            if not config.get("consolidation_dataset_type"):
                hidden_fields.update(self.consolidation_output_fields)
            return tuple(field for field in fields if field not in hidden_fields)
        return fields

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["consolidation_source_url"].help_text = (
            "Required for ENE jobs. Use the National Treasury Consolidated account "
            "of government Pivot workbook for the selected financial year."
        )
        return form

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            config = get_preparation_dataset_config(obj.dataset_type)
            hidden_fields = set()
            if not config.get("budget_vs_actual_dataset_type"):
                hidden_fields.update(self.secondary_output_fields)
            if not config.get("consolidation_dataset_type"):
                hidden_fields.update(self.consolidation_output_fields)
            return tuple(field for field in readonly_fields if field not in hidden_fields)
        return readonly_fields

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/queue-primary-import/",
                self.admin_site.admin_view(self.queue_primary_import_view),
                name="dataset_preparation_datasetpreparationjob_queue_primary_import",
            ),
            path(
                "<path:object_id>/queue-pair-imports/",
                self.admin_site.admin_view(self.queue_pair_imports_view),
                name="dataset_preparation_datasetpreparationjob_queue_pair_imports",
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
        obj = self.get_object(request, object_id)
        if obj:
            config = get_preparation_dataset_config(obj.dataset_type)
            extra_context["queue_primary_import_url"] = reverse(
                "admin:dataset_preparation_datasetpreparationjob_queue_primary_import",
                args=[object_id],
            )
            extra_context["queue_primary_import_label"] = "Queue {} Import".format(
                config["primary_log_label"]
            )
            extra_context["queue_pair_imports_url"] = reverse(
                "admin:dataset_preparation_datasetpreparationjob_queue_pair_imports",
                args=[object_id],
            )
            extra_context["has_secondary_output"] = bool(
                config.get("budget_vs_actual_dataset_type")
            )
            if extra_context["has_secondary_output"]:
                extra_context["queue_pair_imports_label"] = "Queue {} and {} Imports".format(
                    config["primary_log_label"],
                    config["budget_vs_actual_log_label"],
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

    def queue_primary_import_view(self, request, object_id):
        preparation_job = self.get_object(request, object_id)
        config = get_preparation_dataset_config(preparation_job.dataset_type)
        queued = self._queue_imports_for_preparation(
            request,
            preparation_job,
            [config["primary_dataset_type"]],
        )
        self.message_user(request, "{} import job(s) queued.".format(queued))
        return HttpResponseRedirect(
            reverse("admin:dataset_preparation_datasetpreparationjob_change", args=[object_id])
        )

    def queue_pair_imports_view(self, request, object_id):
        preparation_job = self.get_object(request, object_id)
        config = get_preparation_dataset_config(preparation_job.dataset_type)
        if not config.get("budget_vs_actual_dataset_type"):
            self.message_user(request, "This preparation type has no secondary import.", level=messages.WARNING)
            return HttpResponseRedirect(
                reverse("admin:dataset_preparation_datasetpreparationjob_change", args=[object_id])
            )
        queued = self._queue_imports_for_preparation(
            request,
            preparation_job,
            [
                config["primary_dataset_type"],
                config["budget_vs_actual_dataset_type"],
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

    def queue_pair_imports(self, request, queryset):
        queued = 0
        for preparation_job in queryset:
            config = get_preparation_dataset_config(preparation_job.dataset_type)
            if not config.get("budget_vs_actual_dataset_type"):
                continue
            queued += self._queue_imports_for_preparation(
                request,
                preparation_job,
                [
                    config["primary_dataset_type"],
                    config["budget_vs_actual_dataset_type"],
                ],
            )

        self.message_user(request, "{} import job(s) queued.".format(queued))

    queue_pair_imports.short_description = "Queue both imports for selected preparation jobs"

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
