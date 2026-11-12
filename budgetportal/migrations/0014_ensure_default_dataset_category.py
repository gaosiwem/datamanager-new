from django.db import migrations


DEFAULT_CATEGORY_SLUG = "estimates-of-national-expenditure"


def ensure_default_dataset_category(apps, schema_editor):
    DatasetCategory = apps.get_model("budgetportal", "DatasetCategory")
    DatasetCategory.objects.get_or_create(
        slug=DEFAULT_CATEGORY_SLUG,
        defaults={
            "title": "Estimates of National Expenditure",
            "description": "Estimates of National Expenditure",
            "type": "Original Budget",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("budgetportal", "0013_approved_document_retrieval"),
    ]

    operations = [
        migrations.RunPython(
            ensure_default_dataset_category,
            migrations.RunPython.noop,
        ),
    ]
