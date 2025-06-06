# Generated by Django 5.2 on 2025-04-18 11:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_appointmentconsultation'),
    ]

    operations = [
        migrations.AddField(
            model_name='scan',
            name='requires_consultation',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='scan',
            name='result_status',
            field=models.CharField(choices=[('healthy', 'Healthy'), ('requires_consultation', 'Requires Consultation'), ('inconclusive', 'Inconclusive')], default='inconclusive', max_length=25),
        ),
    ]
