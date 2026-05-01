"""
WSGI config for digital_will project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_will.settings')
application = get_wsgi_application()
