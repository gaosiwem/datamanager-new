from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("budgetportal", "0014_ensure_default_dataset_category")]

    operations = [
        migrations.AddField(
            model_name="approveddocument",
            name="source_key",
            field=models.CharField(blank=True, max_length=512, null=True, unique=True),
        )
    ]
