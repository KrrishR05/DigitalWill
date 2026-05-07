"""
Root URL configuration for digital_will project.

URL patterns are split:
  - Admin panel at /admin/
  - Authentication at /auth/  (login, register, logout)
  - Everything else handled by the vault app
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django admin panel
    path('admin/', admin.site.urls),

    # All vault app URLs (dashboard, assets, nominees, etc.)
    path('', include('vault.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
