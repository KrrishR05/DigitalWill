"""
Migration 0005: Add warning_sent_at to ReleaseRequest.

Tracks when nominee notification emails were dispatched.
Depends on 0004_inactivity_release_request (which removed the old
warning_sent_at and restructured ReleaseRequest).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0004_inactivity_release_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='releaserequest',
            name='warning_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Timestamp when nominee notification emails were sent',
            ),
        ),
    ]
