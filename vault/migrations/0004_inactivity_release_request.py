# Generated migration for Step 5: Inactivity Detection and Basic Release Workflow
#
# Changes made to ReleaseRequest:
#   - triggered_at : was auto_now_add=True → now null=True, blank=True (set explicitly when triggered)
#   - Remove warning_sent_at field (not in the new 3-state spec)
#   - STATUS_CHOICES simplified to: pending | triggered | completed  (removed 'warned')
#   - Meta.ordering changed from ['-triggered_at'] to ['-id'] (triggered_at may be null)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0003_digitalasset_nominees'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Remove the old auto_now_add field (we must remove it before re-adding as nullable)
        migrations.RemoveField(
            model_name='releaserequest',
            name='triggered_at',
        ),

        # 2. Remove warning_sent_at (no longer in the simplified spec)
        migrations.RemoveField(
            model_name='releaserequest',
            name='warning_sent_at',
        ),

        # 3. Add the new nullable triggered_at
        migrations.AddField(
            model_name='releaserequest',
            name='triggered_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Timestamp when the release workflow was actually triggered',
            ),
        ),

        # 4. Update status choices (alter the field to use the new choices list)
        migrations.AlterField(
            model_name='releaserequest',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('pending',   'Pending'),
                    ('triggered', 'Triggered'),
                    ('completed', 'Completed'),
                ],
                default='pending',
            ),
        ),

        # 5. Update ordering to use id (triggered_at may be null, so -triggered_at is unreliable)
        migrations.AlterModelOptions(
            name='releaserequest',
            options={'ordering': ['-id']},
        ),
    ]
