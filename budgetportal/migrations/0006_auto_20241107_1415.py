# Generated by Django 2.2.20 on 2024-11-07 12:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('budgetportal', '0005_dataset_datasetcategories_dimensions_governmentfunctions_organisations_tags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datasetcategories',
            name='description',
            field=models.CharField(max_length=1024),
        ),
    ]
