from django.db import models

from budgetportal.models.government import FinancialYear

# Create your models here.

class ValidationRun(models.Model):
    # document_type = models.CharField(max_length=255)
    document_type = models.CharField(
        max_length=255,
        default="ENE",
        choices=[
            ("ENE", "ENE"),
            ("EPRE", "EPRE")
        ],
    )
    financial_year = models.ForeignKey(
        FinancialYear, on_delete=models.CASCADE
    )
    source_file = models.FileField(upload_to="validation_sources/")
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_type} {self.financial_year}"

    class Meta:
        unique_together = (("document_type", "financial_year")),
        verbose_name = "Validation Run"
        verbose_name_plural = "Validation Runs"

class ValidationResult(models.Model):
    validation_run = models.ForeignKey(
        ValidationRun,
        on_delete=models.CASCADE,
        related_name="results",
    )
    province = models.CharField(max_length=255, default="NATIONAL")
    department = models.CharField(max_length=255, null=True, blank=True)
    programme = models.CharField(max_length=255)
    subprogramme = models.CharField(max_length=255, null=True, blank=True)
    internal_amount = models.DecimalField(max_digits=20, decimal_places=3)
    external_amount = models.DecimalField(max_digits=20, decimal_places=3)
    level = models.CharField(max_length=20, default="PROGRAMME")
    is_valid = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.programme} ({'OK' if self.is_valid else 'FAIL'})"

