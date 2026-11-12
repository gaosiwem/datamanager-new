# Generated manually for Django 2.2.20 compatibility.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("budgetportal", "0015_approved_document_source_key")]

    operations = [
        migrations.CreateModel(
            name="DivisionOfRevenue",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveSmallIntegerField(default=1)),
                ("source_filename", models.CharField(max_length=255)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("financial_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="division_of_revenue_bills", to="budgetportal.FinancialYear")),
            ],
            options={
                "verbose_name": "Division of Revenue Bill",
                "verbose_name_plural": "Division of Revenue Bills",
                "ordering": ("-financial_year__slug", "-version"),
                "unique_together": {("financial_year", "version")},
            },
        ),
        migrations.CreateModel(
            name="Municipality",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=16, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("category", models.CharField(max_length=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("province", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="municipalities", to="budgetportal.Government")),
            ],
            options={"ordering": ("province__name", "name")},
        ),
        migrations.CreateModel(
            name="DivisionOfRevenueAllocation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("schedule_number", models.PositiveSmallIntegerField()),
                ("amount_rands", models.BigIntegerField()),
                ("source_row_number", models.PositiveIntegerField()),
                ("allocation_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="division_of_revenue_allocations", to="budgetportal.FinancialYear")),
                ("division_of_revenue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="allocations", to="budgetportal.DivisionOfRevenue")),
                ("government", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="division_of_revenue_allocations", to="budgetportal.Government")),
                ("municipality", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="division_of_revenue_allocations", to="budgetportal.Municipality")),
                ("sphere", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="division_of_revenue_allocations", to="budgetportal.Sphere")),
            ],
            options={
                "ordering": ("schedule_number", "allocation_year__slug", "source_row_number"),
                "unique_together": {("division_of_revenue", "schedule_number", "allocation_year", "source_row_number")},
            },
        ),
    ]
