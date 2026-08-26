import logging
import os
import time
from datetime import datetime, timedelta

from django.db import DatabaseError, OperationalError, close_old_connections
from django_q.tasks import async_task
from django.utils import timezone

from budgetportal.dataset_uploading.dataset_preprocessor import import_dataset
from budgetportal.models import Dataset, DatasetResource

from .models import DatasetImportJob, DatasetPreparationJob
from .services import (
    DatasetPreparationError,
    convert_prepared_csvs_to_excel,
    create_dataset_upload_from_field,
    get_preparation_dataset_config,
    prepare_dataset_job,
)


logger = logging.getLogger(__name__)
STALE_IMPORT_AGE = timedelta(minutes=30)


def timestamped_message(message):
    return "[{}] {}".format(datetime.utcnow().isoformat(timespec="seconds"), message)


def emit_progress(message):
    print("[dataset_preparation] {}".format(message), flush=True)
    logger.info(message)


def append_model_log(instance, message):
    emit_progress(message)
    try:
        close_old_connections()
        if instance.log:
            instance.log += "\n"
        instance.log += timestamped_message(message)
        instance.save(update_fields=["log", "updated_at"])
    except (DatabaseError, OperationalError) as exc:
        logger.warning(
            "Unable to persist progress log for %s %s: %s",
            instance.__class__.__name__,
            getattr(instance, "id", None),
            exc,
        )
        close_old_connections()


def release_stale_import_jobs(import_job):
    cutoff = timezone.now() - STALE_IMPORT_AGE
    stale_jobs = DatasetImportJob.objects.filter(
        preparation_job__financial_year=import_job.preparation_job.financial_year,
        dataset_type=import_job.dataset_type,
        status__in=[DatasetImportJob.STATUS_QUEUED, DatasetImportJob.STATUS_IMPORTING],
        updated_at__lt=cutoff,
    ).exclude(pk=import_job.pk)

    released = []
    for stale_job in stale_jobs:
        stale_job.status = DatasetImportJob.STATUS_FAILED
        stale_job.error_message = (
            "Marked stale after {} minutes without progress so a newer import could run.".format(
                int(STALE_IMPORT_AGE.total_seconds() // 60)
            )
        )
        stale_job.save(update_fields=["status", "error_message", "updated_at"])
        append_model_log(
            stale_job,
            "Automatically marked stale to unblock a newer {} import for {}.".format(
                stale_job.dataset_type,
                stale_job.preparation_job.financial_year.slug,
            ),
        )
        released.append(stale_job.id)

    return released


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
    try:
        close_old_connections()
        instance.save(update_fields=list(dict.fromkeys(update_fields)))
    except (DatabaseError, OperationalError) as exc:
        logger.warning(
            "Unable to persist status update for %s %s -> %s: %s",
            instance.__class__.__name__,
            getattr(instance, "id", None),
            status,
            exc,
        )
        close_old_connections()


def create_import_jobs_for_preparation(job):
    config = get_preparation_dataset_config(job.dataset_type)
    emit_progress(
        "Creating import jobs for preparation job {} ({})".format(
            job.id, job.financial_year.slug
        )
    )
    DatasetImportJob.objects.update_or_create(
        preparation_job=job,
        dataset_type=config["primary_dataset_type"],
        defaults={"status": DatasetImportJob.STATUS_PENDING, "error_message": "", "task_id": None},
    )
    if config.get("budget_vs_actual_dataset_type"):
        DatasetImportJob.objects.update_or_create(
            preparation_job=job,
            dataset_type=config["budget_vs_actual_dataset_type"],
            defaults={"status": DatasetImportJob.STATUS_PENDING, "error_message": "", "task_id": None},
        )
    if config.get("consolidation_dataset_type"):
        DatasetImportJob.objects.update_or_create(
            preparation_job=job,
            dataset_type=config["consolidation_dataset_type"],
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
        try:
            queue_dataset_import_job(import_job)
            queued += 1
        except DatasetPreparationError as exc:
            append_model_log(
                job,
                "Skipped queueing {} import job {}: {}".format(
                    import_job.dataset_type,
                    import_job.id,
                    exc,
                ),
            )
    return queued


def queue_dataset_import_job(import_job):
    emit_progress(
        "Queueing import job {} for {} {}".format(
            import_job.id,
            import_job.dataset_type,
            import_job.preparation_job.financial_year.slug,
        )
    )
    released_jobs = release_stale_import_jobs(import_job)
    if released_jobs:
        append_model_log(
            import_job.preparation_job,
            "Released stale {} import job(s): {}.".format(
                import_job.dataset_type,
                ", ".join(str(job_id) for job_id in released_jobs),
            ),
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
        config = get_preparation_dataset_config(job.dataset_type)
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
        job.epre_prepared_rows = len(results[config["primary_dataset_type"]])
        secondary_dataset_type = config.get("budget_vs_actual_dataset_type")
        job.budget_vs_actual_prepared_rows = (
            len(results[secondary_dataset_type]) if secondary_dataset_type else None
        )
        consolidation_dataset_type = config.get("consolidation_dataset_type")
        job.consolidated_prepared_rows = (
            len(results[consolidation_dataset_type]) if consolidation_dataset_type else None
        )
        job.save(
            update_fields=[
                "raw_file",
                "prepared_file",
                "budget_vs_actual_file",
                "consolidated_file",
                "duration_seconds",
                "epre_prepared_rows",
                "budget_vs_actual_prepared_rows",
                "consolidated_prepared_rows",
                "updated_at",
            ]
        )

        # CSV imports are deliberately completed before the more expensive
        # Excel generation. This keeps the portal responsive for large Budget
        # vs Actual outputs while the Excel resources are prepared afterwards.
        job.excel_conversion_status = DatasetPreparationJob.CONVERSION_STATUS_PENDING
        job.excel_conversion_task_id = None
        job.save(
            update_fields=[
                "excel_conversion_status",
                "excel_conversion_task_id",
                "updated_at",
            ]
        )

        create_import_jobs_for_preparation(job)
        completion_message = "Preparation completed. {} rows: {}.".format(
            config["primary_log_label"], job.epre_prepared_rows
        )
        if secondary_dataset_type:
            completion_message += " {} rows: {}.".format(
                config["budget_vs_actual_log_label"], job.budget_vs_actual_prepared_rows
            )
        if consolidation_dataset_type:
            completion_message += " {} rows: {}.".format(
                config["consolidation_log_label"], job.consolidated_prepared_rows
            )
        update_model_status(
            job,
            DatasetPreparationJob.STATUS_PREPARED,
            completion_message,
            extra_fields=["duration_seconds", "epre_prepared_rows", "budget_vs_actual_prepared_rows", "consolidated_prepared_rows"],
        )
        queued_imports = queue_import_jobs_for_preparation(job)
        prepared_filenames = [os.path.basename(job.prepared_file.name)]
        if secondary_dataset_type:
            prepared_filenames.append(os.path.basename(job.budget_vs_actual_file.name))
        if consolidation_dataset_type:
            prepared_filenames.append(os.path.basename(job.consolidated_file.name))
        append_model_log(job, "Prepared files saved to {}".format(
            " and ".join(prepared_filenames)
        ))
        append_model_log(
            job, "Import jobs created and {} import(s) queued.".format(queued_imports)
        )
        emit_progress("Preparation job {} completed successfully".format(job.id))
        return {
            "epre_prepared_rows": job.epre_prepared_rows,
            "budget_vs_actual_prepared_rows": job.budget_vs_actual_prepared_rows,
            "consolidated_prepared_rows": job.consolidated_prepared_rows,
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
        add_excel_resources_to_imported_datasets(job)
        job.excel_conversion_status = DatasetPreparationJob.CONVERSION_STATUS_COMPLETED
        job.save(
            update_fields=[
                "prepared_excel_file",
                "budget_vs_actual_excel_file",
                "consolidated_excel_file",
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


def add_excel_resources_to_imported_datasets(job):
    """Attach final Excel files after the CSV imports have created datasets."""
    for import_job in job.import_jobs.select_related("dataset_upload"):
        dataset = Dataset.objects.filter(
            title="{} {}".format(
                get_dataset_title(import_job.dataset_type),
                job.financial_year.slug,
            ),
            financial_year=job.financial_year,
        ).first()
        if not dataset:
            raise DatasetPreparationError(
                "Cannot find the Data and Analysis dataset for {}.".format(
                    import_job.dataset_type
                )
            )
        csv_resource = DatasetResource.objects.filter(
            dataset=dataset,
            format="CSV",
        ).first()
        if not csv_resource:
            raise DatasetPreparationError(
                "Cannot find the Data and Analysis CSV resource for {}.".format(
                    import_job.dataset_type
                )
            )
        excel_file = getattr(job, get_import_excel_file_field_name(import_job))
        DatasetResource.objects.update_or_create(
            dataset=csv_resource.dataset,
            format="XLSX",
            defaults={
                "fileName": csv_resource.fileName,
                "description": csv_resource.description,
                "file": excel_file,
            },
        )
    append_model_log(job, "Excel copies added to Data and Analysis")


def get_dataset_title(dataset_type):
    titles = {
        DatasetImportJob.DATASET_TYPE_EPRE: "Estimates of Provincial Revenue and Expenditure",
        DatasetImportJob.DATASET_TYPE_ENE: "Estimates of National Expenditure",
        DatasetImportJob.DATASET_TYPE_AENE: "Adjusted Estimates of National Expenditure",
        DatasetImportJob.DATASET_TYPE_BVA_NATIONAL: "Budgeted vs Actual National Expenditure",
        DatasetImportJob.DATASET_TYPE_BVA_PROVINCIAL: "Budgeted and Actual Provincial Expenditure",
        DatasetImportJob.DATASET_TYPE_CONSOLIDATION: "Consolidated Expenditure",
    }
    try:
        return titles[dataset_type]
    except KeyError:
        raise DatasetPreparationError("Unsupported dataset type '{}'".format(dataset_type))


def get_import_file_field_name(import_job):
    if import_job.dataset_type in (
        DatasetImportJob.DATASET_TYPE_EPRE,
        DatasetImportJob.DATASET_TYPE_ENE,
        DatasetImportJob.DATASET_TYPE_AENE,
    ):
        return "prepared_file"
    if import_job.dataset_type == DatasetImportJob.DATASET_TYPE_CONSOLIDATION:
        return "consolidated_file"
    return "budget_vs_actual_file"


def get_import_excel_file_field_name(import_job):
    if import_job.dataset_type in (
        DatasetImportJob.DATASET_TYPE_EPRE,
        DatasetImportJob.DATASET_TYPE_ENE,
        DatasetImportJob.DATASET_TYPE_AENE,
    ):
        return "prepared_excel_file"
    if import_job.dataset_type == DatasetImportJob.DATASET_TYPE_CONSOLIDATION:
        return "consolidated_excel_file"
    return "budget_vs_actual_excel_file"


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
            try:
                append_model_log(import_job, message)
            except Exception as exc:
                logger.warning(
                    "Progress callback failed for import job %s: %s",
                    import_job.id,
                    exc,
                )

        result = import_dataset(
            dataset_upload.id,
            progress_callback=progress_callback,
            excel_file=None,
        )
        import_job.imported_rows = result["imported_rows"]
        import_job.duration_seconds = round(time.monotonic() - started_at, 2)
        update_model_status(
            import_job,
            DatasetImportJob.STATUS_COMPLETED,
            "Import completed with {} rows".format(import_job.imported_rows),
            extra_fields=["dataset_upload", "imported_rows", "duration_seconds"],
        )
        preparation_job = import_job.preparation_job
        if not preparation_job.import_jobs.exclude(
            status=DatasetImportJob.STATUS_COMPLETED
        ).exists():
            queue_excel_conversion_job(preparation_job)
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
