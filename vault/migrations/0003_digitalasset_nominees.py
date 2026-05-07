"""
Migration 0003: Add nominees ManyToManyField to DigitalAsset.
Allows direct assignment of nominees to specific assets.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0002_digitalasset_document_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='digitalasset',
            name='nominees',
            field=models.ManyToManyField(
                blank=True,
                help_text='Nominees who can access this asset after inactivity trigger',
                related_name='assigned_assets',
                to='vault.nominee',
            ),
        ),
    ]
