# Generated by Django 2.2.20 on 2024-11-14 06:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('budgetportal', '0024_auto_20241114_0822'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='enedata',
            name='selectedFinancialYear',
        ),
        migrations.RemoveField(
            model_name='enedata',
            name='value',
        ),
    ]
