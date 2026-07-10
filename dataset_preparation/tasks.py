import logging
import os
import time
from datetime import datetime

from django_q.tasks import async_task

from budgetportal.dataset_uploading.dataset_preprocessor import import_dataset

from .models import DatasetImportJob, DatasetPreparationJob
from .services import (
    DatasetPreparationError,
    convert_prepared_csvs_to_excel,
    create_dataset_upload_from_field,
    prepare_dataset_job,
)


logger = logging.getLogger(__name__)


def timestamped_message(message):
    return "[{}] {}".format(datetime.utcnow().isoformat(timespec="seconds"), message)


def emit_progress(message):
    print("[dataset_preparation] {}".format(message), flush=True)
    logger.info(message)


def append_model_log(instance, message):
    emit_progress(message)
    if instance.log:
        instance.log += "\n"
    instance.log += timestamped_message(message)
    instance.save(update_fields=["log", "updated_at"])


def update_model_status(instance, status, message=None, error_message=None, extra_fields=None):
    instance.status = status
    if error_message is not None:
        instance.error_message = error_message
    if message:
        emit_progress(message)
        if instance.log:
            instance.log += "\n"
        instance.log += timestamped_message(message)
    update_fields = ["status", "log", "updated_at"]
    if error_message is not None:
        update_fields.append("error_message")
    if extra_fields:
        update_fields.extend(extra_fields)
    instance.save(update_fields=list(dict.fromkeys(update_fields)))


def create_import_jobs_for_preparation(job):
    emit_progress(
        "Creating import jobs for preparation job {} ({})".format(
            job.id, job.financial_year.slug
        )
    )
    DatasetImportJob.objects.update_or_create(
        preparation_job=job,
        dataset_type=DatasetImportJob.DATASET_TYPE_EPRE,
        defaults={"status": DatasetImportJob.STATUS_PENDING, "error_message": "", "task_id": None},
    )
    DatasetImportJob.objects.update_or_create(
        preparation_job=job,
        dataset_type=DatasetImportJob.DATASET_TYPE_BVA_PROVINCIAL,
        defaults={"status": DatasetImportJob.STATUS_PENDING, "error_message": "", "task_id": None},
    )


def queue_import_jobs_for_preparation(job):
    queued = 0
    for import_job in job.import_jobs.all():
        if import_job.status not in (
            DatasetImportJob.STATUS_PENDING,
            DatasetImportJob.STATUS_FAILED,
        ):
            continue
        queue_dataset_import_job(import_job)
        queued += 1
    return queued


def queue_dataset_import_job(import_job):
    emit_progress(
        "Queueing import job {} for {} {}".format(
            import_job.id,
            import_job.dataset_type,
            import_job.preparation_job.financial_year.slug,
        )
    )
    active_job_exists = DatasetImportJob.objects.filter(
        preparation_job__financial_year=import_job.preparation_job.financial_year,
        dataset_type=import_job.dataset_type,
        status__in=[DatasetImportJob.STATUS_QUEUED, DatasetImportJob.STATUS_IMPORTING],
    ).exclude(pk=import_job.pk).exists()
    if active_job_exists:
        raise DatasetPreparationError(
            "Another {} import is already queued or running for {}.".format(
                import_job.dataset_type,
                import_job.preparation_job.financial_year.slug,
            )
        )

    import_job.task_id = async_task(run_dataset_import_job, import_job_id=import_job.id)
    update_model_status(
        import_job,
        DatasetImportJob.STATUS_QUEUED,
        message="Queued import job",
        error_message="",
        extra_fields=["task_id"],
    )


def run_dataset_preparation_job(job_id):
    job = DatasetPreparationJob.objects.get(id=job_id)
    started_at = time.monotonic()
    emit_progress(
        "Starting preparation job {} for {} from {}".format(
            job.id, job.financial_year.slug, job.source_url
        )
    )

    try:
        update_model_status(
            job,
            DatasetPreparationJob.STATUS_DOWNLOADING,
            "Downloading source workbook from {}".format(job.source_url),
            error_message="",
        )
        update_model_status(
            job,
            DatasetPreparationJob.STATUS_PREPARING,
            "Preparing workbook into upload format",
        )
        results = prepare_dataset_job(job)
        job.duration_seconds = round(time.monotonic() - started_at, 2)
        job.epre_prepared_rows = len(results["EPRE"])
        job.budget_vs_actual_prepared_rows = len(results["Budget-vs-Actual-Provincial"])
        job.save(
            update_fields=[
                "raw_file",
                "prepared_file",
                "budget_vs_actual_file",
                "duration_seconds",
                "epre_prepared_rows",
                "budget_vs_actual_prepared_rows",
                "updated_at",
            ]
        )

        create_import_jobs_for_preparation(job)
        queued_imports = queue_import_jobs_for_preparation(job)
        update_model_status(
            job,
            DatasetPreparationJob.STATUS_PREPARED,
            "Preparation completed. EPRE rows: {}. Budget vs Actual rows: {}.".format(
                job.epre_prepared_rows,
                job.budget_vs_actual_prepared_rows,
            ),
            extra_fields=["duration_seconds", "epre_prepared_rows", "budget_vs_actual_prepared_rows"],
        )
        append_model_log(
            job,
            "Prepared files saved to {} and {}".format(
                os.path.basename(job.prepared_file.name),
                os.path.basename(job.budget_vs_actual_file.name),
            ),
        )
        append_model_log(
            job, "Import jobs created and {} import(s) queued.".format(queued_imports)
        )
        job.excel_conversion_status = DatasetPreparationJob.CONVERSION_STATUS_PENDING
        job.excel_conversion_task_id = None
        job.save(update_fields=["excel_conversion_status", "excel_conversion_task_id", "updated_at"])
        emit_progress("Preparation job {} completed successfully".format(job.id))
        return {
            "epre_prepared_rows": job.epre_prepared_rows,
            "budget_vs_actual_prepared_rows": job.budget_vs_actual_prepared_rows,
        }
    except (DatasetPreparationError, Exception) as exc:
        logger.exception("Dataset preparation job %s failed", job_id)
        emit_progress("Preparation job {} failed: {}".format(job.id, exc))
        job.duration_seconds = round(time.monotonic() - started_at, 2)
        update_model_status(
            job,
            DatasetPreparationJob.STATUS_FAILED,
            message="Preparation failed.",
            error_message=str(exc),
            extra_fields=["duration_seconds"],
        )
        raise


def queue_excel_conversion_job(job):
    if job.status != DatasetPreparationJob.STATUS_PREPARED:
        raise DatasetPreparationError(
            "Excel conversion is only available after preparation completes."
        )
    if job.excel_conversion_status in (
        DatasetPreparationJob.CONVERSION_STATUS_QUEUED,
        DatasetPreparationJob.CONVERSION_STATUS_CONVERTING,
    ):
        raise DatasetPreparationError("Excel conversion is already queued or running.")

    job.excel_conversion_task_id = async_task(run_excel_conversion_job, job_id=job.id)
    job.excel_conversion_status = DatasetPreparationJob.CONVERSION_STATUS_QUEUED
    job.save(update_fields=["excel_conversion_task_id", "excel_conversion_status", "updated_at"])
    append_model_log(job, "Queued Excel conversion")


def run_excel_conversion_job(job_id):
    job = DatasetPreparationJob.objects.get(id=job_id)
    started_at = time.monotonic()
    emit_progress("Starting Excel conversion for preparation job {}".format(job.id))
    try:
        job.excel_conversion_status = DatasetPreparationJob.CONVERSION_STATUS_CONVERTING
        job.save(update_fields=["excel_conversion_status", "updated_at"])
        append_model_log(job, "Converting prepared CSV files to Excel copies")
        convert_prepared_csvs_to_excel(job)
        job.excel_conversion_status = DatasetPreparationJob.CONVERSION_STATUS_COMPLETED
        job.save(
            update_fields=[
                "prepared_excel_file",
                "budget_vs_actual_excel_file",
                "excel_conversion_status",
                "updated_at",
            ]
        )
        append_model_log(
            job,
            "Excel conversion completed in {:.2f}s".format(time.monotonic() - started_at),
        )
    except (DatasetPreparationError, Exception) as exc:
        logger.exception("Excel conversion failed for preparation job %s", job_id)
        job.excel_conversion_status = DatasetPreparationJob.CONVERSION_STATUS_FAILED
        job.error_message = str(exc)
        job.save(update_fields=["excel_conversion_status", "error_message", "updated_at"])
        append_model_log(job, "Excel conversion failed: {}".format(exc))
        raise


def get_import_file_field_name(import_job):
    if import_job.dataset_type == DatasetImportJob.DATASET_TYPE_EPRE:
        return "prepared_file"
    return "budget_vs_actual_file"


def run_dataset_import_job(import_job_id):
    import_job = DatasetImportJob.objects.select_related("preparation_job").get(id=import_job_id)
    started_at = time.monotonic()
    emit_progress(
        "Starting import job {} for {} {}".format(
            import_job.id,
            import_job.dataset_type,
            import_job.preparation_job.financial_year.slug,
        )
    )

    try:
        update_model_status(
            import_job,
            DatasetImportJob.STATUS_IMPORTING,
            "Starting {} import for {}".format(
                import_job.dataset_type,
                import_job.preparation_job.financial_year.slug,
            ),
            error_message="",
        )
        dataset_upload = create_dataset_upload_from_field(
            import_job.preparation_job,
            get_import_file_field_name(import_job),
            import_job.dataset_type,
        )
        import_job.dataset_upload = dataset_upload
        import_job.save(update_fields=["dataset_upload", "updated_at"])
        append_model_log(import_job, "Created DatasetUpload {}".format(dataset_upload.id))

        def progress_callback(message):
            append_model_log(import_job, message)

        result = import_dataset(dataset_upload.id, progress_callback=progress_callback)
        import_job.imported_rows = result["imported_rows"]
        import_job.duration_seconds = round(time.monotonic() - started_at, 2)
        update_model_status(
            import_job,
            DatasetImportJob.STATUS_COMPLETED,
            "Import completed with {} rows".format(import_job.imported_rows),
            extra_fields=["dataset_upload", "imported_rows", "duration_seconds"],
        )
        emit_progress("Import job {} completed successfully".format(import_job.id))
        return result
    except (DatasetPreparationError, Exception) as exc:
        logger.exception("Dataset import job %s failed", import_job_id)
        emit_progress("Import job {} failed: {}".format(import_job.id, exc))
        import_job.duration_seconds = round(time.monotonic() - started_at, 2)
        update_model_status(
            import_job,
            DatasetImportJob.STATUS_FAILED,
            message="Import failed.",
            error_message=str(exc),
            extra_fields=["dataset_upload", "duration_seconds"],
        )
        raise
