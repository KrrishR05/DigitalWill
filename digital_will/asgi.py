"""
ASGI config for digital_will project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_will.settings')
application = get_asgi_application()
