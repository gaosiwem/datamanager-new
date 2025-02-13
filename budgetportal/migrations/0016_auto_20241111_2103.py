# Generated by Django 2.2.20 on 2024-11-11 19:03

import budgetportal.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('budgetportal', '0015_auto_20241111_1615'),
    ]

    operations = [
        migrations.CreateModel(
            name='ENEDataUpload',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to=budgetportal.models.datasets_file_path)),
            ],
        ),
        migrations.AlterField(
            model_name='enedata',
            name='department',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enedata', to='budgetportal.ENEDataUpload'),
        ),
    ]
