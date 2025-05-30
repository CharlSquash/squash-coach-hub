# Generated by Django 5.2 on 2025-05-22 07:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0026_sessionassessment_is_hidden'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionassessment',
            name='superuser_reviewed',
            field=models.BooleanField(db_index=True, default=False, help_text='Checked by superuser if they have reviewed this assessment on their dashboard.'),
        ),
    ]
