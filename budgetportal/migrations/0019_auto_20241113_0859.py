# Generated by Django 2.2.20 on 2024-11-13 06:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('budgetportal', '0018_auto_20241113_0836'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enedataupload',
            name='selectedFinancialYear',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='budgetportal.FinancialYear'),
        ),
    ]
