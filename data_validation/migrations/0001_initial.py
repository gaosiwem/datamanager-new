from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("budgetportal", "0012_auto_20260528_1417"),
    ]

    operations = [
        migrations.CreateModel(
            name="ValidationRun",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "document_type",
                    models.CharField(
                        choices=[("ENE", "ENE"), ("EPRE", "EPRE")],
                        default="ENE",
                        max_length=255,
                    ),
                ),
                ("source_file", models.FileField(upload_to="validation_sources/")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "financial_year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="budgetportal.FinancialYear",
                    ),
                ),
            ],
            options={
                "verbose_name": "Validation Run",
                "verbose_name_plural": "Validation Runs",
                "unique_together": {("document_type", "financial_year")},
            },
        ),
        migrations.CreateModel(
            name="ValidationResult",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("province", models.CharField(default="NATIONAL", max_length=255)),
                (
                    "department",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("programme", models.CharField(max_length=255)),
                (
                    "subprogramme",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "internal_amount",
                    models.DecimalField(decimal_places=3, max_digits=20),
                ),
                (
                    "external_amount",
                    models.DecimalField(decimal_places=3, max_digits=20),
                ),
                ("level", models.CharField(default="PROGRAMME", max_length=20)),
                ("is_valid", models.BooleanField(default=False)),
                (
                    "validation_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="data_validation.ValidationRun",
                    ),
                ),
            ],
        ),
    ]
