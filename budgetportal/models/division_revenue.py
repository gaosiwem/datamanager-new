"""Domain models for published Division of Revenue equitable-share schedules."""

from django.db import models

from .government import FinancialYear, Government, Sphere


class Municipality(models.Model):
    """A municipality identified by its official Division of Revenue code."""

    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=1)
    province = models.ForeignKey(
        Government, on_delete=models.PROTECT, related_name="municipalities"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("province__name", "name")

    def __str__(self):
        return "%s (%s)" % (self.name, self.code)


class DivisionOfRevenue(models.Model):
    """One official version of a Division of Revenue Bill for a financial year."""

    financial_year = models.ForeignKey(
        FinancialYear, on_delete=models.PROTECT, related_name="division_of_revenue_bills"
    )
    version = models.PositiveSmallIntegerField(default=1)
    source_filename = models.CharField(max_length=255)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("financial_year", "version"),)
        ordering = ("-financial_year__slug", "-version")
        verbose_name = "Division of Revenue Bill"
        verbose_name_plural = "Division of Revenue Bills"

    def __str__(self):
        return "%s (version %s)" % (self.financial_year.slug, self.version)


class DivisionOfRevenueUpload(models.Model):
    """A durable upload job processed asynchronously by Django-Q."""

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETE = "complete"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED, "Failed"),
    )

    file = models.FileField(upload_to="division_revenue_uploads/%Y/%m/%d/")
    uploaded_by = models.ForeignKey(
        "auth.User", blank=True, null=True, on_delete=models.SET_NULL
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    division_of_revenue = models.ForeignKey(
        DivisionOfRevenue, blank=True, null=True, on_delete=models.SET_NULL,
        related_name="upload_jobs",
    )

    class Meta:
        ordering = ("-uploaded_at",)
        verbose_name = "Division of Revenue upload"
        verbose_name_plural = "Division of Revenue uploads"

    def __str__(self):
        return "%s (%s)" % (self.file.name, self.get_status_display())


class DivisionOfRevenueAllocation(models.Model):
    """A published equitable-share amount from Schedule 1, 2, or 3, in rands."""

    SCHEDULE_1_RECIPIENTS = (
        ("national", "National"),
        ("provincial", "Provincial"),
        ("local", "Local"),
    )

    division_of_revenue = models.ForeignKey(
        DivisionOfRevenue, on_delete=models.CASCADE, related_name="allocations"
    )
    schedule_number = models.PositiveSmallIntegerField()
    sphere = models.ForeignKey(
        Sphere,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="division_of_revenue_allocations",
    )
    government = models.ForeignKey(
        Government,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="division_of_revenue_allocations",
    )
    municipality = models.ForeignKey(
        Municipality,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="division_of_revenue_allocations",
    )
    schedule_1_recipient = models.CharField(
        max_length=16, blank=True, choices=SCHEDULE_1_RECIPIENTS
    )
    amount_rands = models.BigIntegerField()
    forward_estimate_1_rands = models.BigIntegerField(blank=True, null=True)
    forward_estimate_2_rands = models.BigIntegerField(blank=True, null=True)
    source_row_number = models.PositiveIntegerField()

    class Meta:
        unique_together = (
            ("division_of_revenue", "schedule_number", "source_row_number"),
        )
        ordering = ("schedule_number", "source_row_number")
