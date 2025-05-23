# Generated by Django 5.2 on 2025-04-26 15:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0014_delete_coachjournalentry'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolgroup',
            name='attendance_form_url',
            field=models.URLField(blank=True, help_text='Link to the external Google Form or attendance sheet for this group.', max_length=1024, null=True, verbose_name='Attendance Form URL'),
        ),
    ]
