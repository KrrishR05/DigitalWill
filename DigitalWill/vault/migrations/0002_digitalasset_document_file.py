"""
Migration 0002: Add document_file field to DigitalAsset
Allows document-category assets to store an uploaded file.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='digitalasset',
            name='document_file',
            field=models.FileField(
                upload_to='documents/',
                blank=True,
                null=True,
                help_text='Uploaded file for document-type assets',
            ),
        ),
    ]
