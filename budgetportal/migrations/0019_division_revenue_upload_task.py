from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("budgetportal", "0018_division_revenue_local_share"),
    ]

    operations = [
        migrations.CreateModel(
            name="DivisionOfRevenueUpload",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="division_revenue_uploads/%Y/%m/%d/")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("complete", "Complete"), ("failed", "Failed")], default="pending", max_length=16)),
                ("task_id", models.CharField(blank=True, max_length=255)),
                ("error_message", models.TextField(blank=True)),
                ("division_of_revenue", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="upload_jobs", to="budgetportal.DivisionOfRevenue")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Division of Revenue upload",
                "verbose_name_plural": "Division of Revenue uploads",
                "ordering": ("-uploaded_at",),
            },
        ),
    ]
