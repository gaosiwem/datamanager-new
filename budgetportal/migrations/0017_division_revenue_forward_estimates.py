from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("budgetportal", "0016_division_of_revenue")]

    operations = [
        migrations.AddField(
            model_name="divisionofrevenueallocation",
            name="forward_estimate_1_rands",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="divisionofrevenueallocation",
            name="forward_estimate_2_rands",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AlterUniqueTogether(
            name="divisionofrevenueallocation",
            unique_together={("division_of_revenue", "schedule_number", "source_row_number")},
        ),
        migrations.RemoveField(
            model_name="divisionofrevenueallocation",
            name="allocation_year",
        ),
        migrations.AlterModelOptions(
            name="divisionofrevenueallocation",
            options={"ordering": ("schedule_number", "source_row_number")},
        ),
    ]
