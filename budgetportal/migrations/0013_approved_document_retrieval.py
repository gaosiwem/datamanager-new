from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("budgetportal", "0012_auto_20260528_1417")]

    operations = [
        migrations.CreateModel(
            name="ApprovedDocument",
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
                ("title", models.CharField(max_length=1024)),
                ("source", models.CharField(max_length=1024)),
                (
                    "document_type",
                    models.CharField(
                        choices=[
                            ("glossary", "Vulekamali glossary"),
                            ("budget_review", "Budget Review"),
                            ("ene", "Estimates of National Expenditure"),
                            ("aene", "Adjusted Estimates of National Expenditure"),
                            ("appropriation", "Appropriation document"),
                            ("division_of_revenue", "Division of Revenue"),
                            ("dataset_documentation", "Dataset documentation"),
                            ("help", "Vulekamali help"),
                            (
                                "national_treasury",
                                "Approved National Treasury document",
                            ),
                        ],
                        max_length=64,
                    ),
                ),
                ("url", models.URLField(blank=True, null=True)),
                (
                    "page_section",
                    models.CharField(blank=True, max_length=512, null=True),
                ),
                ("approved", models.BooleanField(db_index=True, default=False)),
                ("ingested_at", models.DateTimeField(auto_now_add=True)),
                ("text", models.TextField()),
                (
                    "financial_year",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="budgetportal.FinancialYear",
                    ),
                ),
            ],
            options={"ordering": ("title",)},
        ),
        migrations.CreateModel(
            name="ApprovedDocumentChunk",
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
                ("chunk_index", models.PositiveIntegerField()),
                ("text", models.TextField()),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="budgetportal.ApprovedDocument",
                    ),
                ),
            ],
            options={
                "ordering": ("document", "chunk_index"),
                "unique_together": {("document", "chunk_index")},
            },
        ),
    ]
