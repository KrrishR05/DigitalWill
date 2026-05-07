"""
AppConfig for the vault app.
The vault app handles all Digital Will features:
- Digital asset CRUD
- Nominee management
- Inactivity detection & release workflow
- Activity logging
"""

from django.apps import AppConfig


class VaultConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vault'
    verbose_name = 'Digital Vault'
