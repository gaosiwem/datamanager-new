# Generated by Django 2.2.20 on 2024-11-08 08:24

import autoslug.fields
import budgetportal.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('budgetportal', '0010_dataset_slug'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dataset',
            name='file',
        ),
        migrations.CreateModel(
            name='DatasetResource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fileName', models.CharField(max_length=1024)),
                ('description', models.CharField(max_length=1024)),
                ('slug', autoslug.fields.AutoSlugField(always_update=True, editable=False, max_length=200, populate_from='fileName')),
                ('path', models.CharField(max_length=1024)),
                ('format', models.CharField(max_length=1024)),
                ('file', models.FileField(upload_to=budgetportal.models.datasets_file_path)),
                ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resources', to='budgetportal.Dataset')),
            ],
        ),
    ]
