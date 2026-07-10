from django.contrib.auth.models import User
from django.db import models

from budgetportal import models as budgetportal_models


class DatasetPreparationJob(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_DOWNLOADING = "Downloading"
    STATUS_PREPARING = "Preparing"
    STATUS_PREPARED = "Prepared"
    STATUS_FAILED = "Failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, STATUS_PENDING),
        (STATUS_DOWNLOADING, STATUS_DOWNLOADING),
        (STATUS_PREPARING, STATUS_PREPARING),
        (STATUS_PREPARED, STATUS_PREPARED),
        (STATUS_FAILED, STATUS_FAILED),
    )

    CONVERSION_STATUS_PENDING = "Pending"
    CONVERSION_STATUS_QUEUED = "Queued"
    CONVERSION_STATUS_CONVERTING = "Converting"
    CONVERSION_STATUS_COMPLETED = "Completed"
    CONVERSION_STATUS_FAILED = "Failed"

    CONVERSION_STATUS_CHOICES = (
        (CONVERSION_STATUS_PENDING, CONVERSION_STATUS_PENDING),
        (CONVERSION_STATUS_QUEUED, CONVERSION_STATUS_QUEUED),
        (CONVERSION_STATUS_CONVERTING, CONVERSION_STATUS_CONVERTING),
        (CONVERSION_STATUS_COMPLETED, CONVERSION_STATUS_COMPLETED),
        (CONVERSION_STATUS_FAILED, CONVERSION_STATUS_FAILED),
    )

    DATASET_TYPE_EPRE = "EPRE"

    DATASET_TYPE_CHOICES = (
        (DATASET_TYPE_EPRE, "EPRE"),
    )

    user = models.ForeignKey(User, models.DO_NOTHING, blank=True, null=True)
    source_url = models.URLField()
    dataset_type = models.CharField(max_length=255, choices=DATASET_TYPE_CHOICES)
    financial_year = models.ForeignKey(
        budgetportal_models.FinancialYear,
        on_delete=models.CASCADE,
        related_name="dataset_preparation_jobs",
    )
    sheet_name = models.CharField(max_length=255, default="Data", blank=True)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    raw_file = models.FileField(
        upload_to=budgetportal_models.resources_file_path,
        blank=True,
        null=True,
    )
    prepared_file = models.FileField(
        upload_to=budgetportal_models.resources_file_path,
        blank=True,
        null=True,
    )
    prepared_excel_file = models.FileField(
        upload_to=budgetportal_models.resources_file_path,
        blank=True,
        null=True,
    )
    budget_vs_actual_file = models.FileField(
        upload_to=budgetportal_models.resources_file_path,
        blank=True,
        null=True,
    )
    budget_vs_actual_excel_file = models.FileField(
        upload_to=budgetportal_models.resources_file_path,
        blank=True,
        null=True,
    )
    log = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    task_id = models.CharField(max_length=255, blank=True, null=True)
    excel_conversion_status = models.CharField(
        max_length=32,
        choices=CONVERSION_STATUS_CHOICES,
        default=CONVERSION_STATUS_PENDING,
    )
    excel_conversion_task_id = models.CharField(max_length=255, blank=True, null=True)
    epre_prepared_rows = models.IntegerField(blank=True, null=True)
    budget_vs_actual_prepared_rows = models.IntegerField(blank=True, null=True)
    duration_seconds = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return "{} {} ({})".format(
            self.dataset_type, self.financial_year.slug, self.status
        )


class DatasetImportJob(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_QUEUED = "Queued"
    STATUS_IMPORTING = "Importing"
    STATUS_COMPLETED = "Completed"
    STATUS_FAILED = "Failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, STATUS_PENDING),
        (STATUS_QUEUED, STATUS_QUEUED),
        (STATUS_IMPORTING, STATUS_IMPORTING),
        (STATUS_COMPLETED, STATUS_COMPLETED),
        (STATUS_FAILED, STATUS_FAILED),
    )

    DATASET_TYPE_EPRE = "EPRE"
    DATASET_TYPE_BVA_PROVINCIAL = "Budget-vs-Actual-Provincial"

    DATASET_TYPE_CHOICES = (
        (DATASET_TYPE_EPRE, "EPRE"),
        (DATASET_TYPE_BVA_PROVINCIAL, "Budget-vs-Actual-Provincial"),
    )

    preparation_job = models.ForeignKey(
        DatasetPreparationJob,
        on_delete=models.CASCADE,
        related_name="import_jobs",
    )
    dataset_type = models.CharField(max_length=255, choices=DATASET_TYPE_CHOICES)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    task_id = models.CharField(max_length=255, blank=True, null=True)
    log = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    imported_rows = models.IntegerField(blank=True, null=True)
    duration_seconds = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    dataset_upload = models.ForeignKey(
        budgetportal_models.DatasetUpload,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="dataset_import_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = ("preparation_job", "dataset_type")

    def __str__(self):
        return "{} {} ({})".format(
            self.dataset_type,
            self.preparation_job.financial_year.slug,
            self.status,
        )
