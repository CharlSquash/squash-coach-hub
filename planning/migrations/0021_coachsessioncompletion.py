# Generated by Django 5.2 on 2025-05-08 03:30

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0020_coach_user_alter_manualcourtassignment_player'),
    ]

    operations = [
        migrations.CreateModel(
            name='CoachSessionCompletion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assessments_submitted', models.BooleanField(default=False, help_text='True if the coach has submitted at least one assessment for this session.')),
                ('confirmed_for_payment', models.BooleanField(default=False, help_text='Manually set by admin/superuser once duties are verified.')),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('coach', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='session_completions', to='planning.coach')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coach_completions', to='planning.session')),
            ],
            options={
                'verbose_name': 'Coach Session Completion',
                'verbose_name_plural': 'Coach Session Completions',
                'ordering': ['session__session_date', 'session__session_start_time', 'coach__name'],
                'unique_together': {('coach', 'session')},
            },
        ),
    ]
