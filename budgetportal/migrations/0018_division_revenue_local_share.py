from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("budgetportal", "0017_division_revenue_forward_estimates")]

    operations = [
        migrations.AddField(
            model_name="divisionofrevenueallocation",
            name="schedule_1_recipient",
            field=models.CharField(
                blank=True,
                choices=[
                    ("national", "National"),
                    ("provincial", "Provincial"),
                    ("local", "Local"),
                ],
                max_length=16,
            ),
        ),
    ]
