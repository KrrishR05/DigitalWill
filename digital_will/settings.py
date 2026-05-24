"""
Django settings for digital_will project.
Digital Will Platform — After-Life Data Manager
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# ─────────────────────────────────────────
# BASE DIRECTORY
# ─────────────────────────────────────────
# Build paths inside the project like: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env variables into os.environ (must be after BASE_DIR is defined)
load_dotenv(BASE_DIR / '.env')


# ─────────────────────────────────────────
# SECURITY
# ─────────────────────────────────────────
# IMPORTANT: Read from .env — never hardcode secrets in this file!
_secret_key = os.environ.get('SECRET_KEY', '')
if not _secret_key:
    raise ValueError(
        "SECRET_KEY environment variable is not set. "
        "Copy .env.example to .env and fill in your values."
    )
SECRET_KEY = _secret_key

# Set to False in production — either in .env (DEBUG=False) or here
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# PRODUCTION: Replace '*' with your actual domain(s), e.g. ['yourdomain.com']
# For local development, '*' is fine.
ALLOWED_HOSTS = ['*']

# Render (and most cloud hosts) terminate SSL at their load balancer and
# forward requests to Django over plain HTTP internally.
# These two settings tell Django to trust the X-Forwarded-Proto header
# so request.scheme returns 'https' instead of 'http' in production.
# This ensures OTP email verification links use https:// not http://
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST    = True


# ─────────────────────────────────────────
# INSTALLED APPS
# ─────────────────────────────────────────
# 'vault' is our main app for all Digital Will features
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'vault',  # Our Digital Will app
]

# ─────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise MUST be immediately after SecurityMiddleware
    # It serves collected static files directly in production without a separate web server
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',   # CSRF protection auto-enabled
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'vault.middleware.UpdateLastActivityMiddleware',   # Tracks user activity
    'vault.middleware.NoCacheAuthenticatedMiddleware', # SECURITY: prevents back-button cache leak
]

ROOT_URLCONF = 'digital_will.urls'


# ─────────────────────────────────────────
# TEMPLATES
# ─────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Global templates folder at project root
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,   # Also searches vault/templates/
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'digital_will.wsgi.application'


# ─────────────────────────────────────────
# DATABASE — SQLite (easy, no setup needed)
# ─────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',   # db stored at project root
    }
}


# ─────────────────────────────────────────
# PASSWORD VALIDATION
# ─────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ─────────────────────────────────────────
# INTERNATIONALIZATION
# ─────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'   # IST timezone
USE_I18N = True
USE_TZ = True


# ─────────────────────────────────────────
# STATIC FILES (CSS, JS, Images)
# ─────────────────────────────────────────
STATIC_URL = '/static/'

# Project-level static files (shared CSS, JS, images)
STATICFILES_DIRS = [BASE_DIR / 'static']

# Where collectstatic gathers ALL files for production
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise static file storage:
#   Production (DEBUG=False): CompressedManifestStaticFilesStorage
#     - Compresses files (gzip/brotli) for faster delivery
#     - Fingerprints filenames (main.abc123.css) for cache-busting
#     - Requires 'python manage.py collectstatic' to be run at deploy time
#     - build.sh already does this automatically on Render
#   Development (DEBUG=True): Django's default StaticFilesStorage
#     - Django dev server serves from STATICFILES_DIRS directly
#     - No collectstatic needed locally
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}


# ─────────────────────────────────────────
# MEDIA FILES (User uploaded files)
# ─────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ─────────────────────────────────────────
# AUTHENTICATION REDIRECTS
# ─────────────────────────────────────────
LOGIN_URL = '/auth/login/'           # Redirect here if not logged in
LOGIN_REDIRECT_URL = '/dashboard/'   # After successful login
LOGOUT_REDIRECT_URL = '/'            # After logout


# ─────────────────────────────────────────
# EMAIL — Gmail SMTP (real email sending)
#
# HOW TO CONFIGURE:
#   Option 1 (recommended): Set environment variables:
#       set EMAIL_HOST_USER=you@gmail.com
#       set EMAIL_HOST_PASSWORD=your_16_char_app_password
#   Option 2 (dev only): Replace the defaults below directly.
#
# A Gmail APP PASSWORD (not your login password) is required.
# Generate one at: Google Account → Security → App Passwords
# ─────────────────────────────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER',     'your_gmail@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'your_16_char_app_password')
DEFAULT_FROM_EMAIL  = os.environ.get('EMAIL_HOST_USER',     'your_gmail@gmail.com')


# ─────────────────────────────────────────
# ENCRYPTION KEY (Fernet symmetric encryption)
# Read from .env — generate a new key with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# ─────────────────────────────────────────
# IMPORTANT: Each deployment needs its OWN unique Fernet key.
# If you change this key, all previously encrypted data becomes unreadable.
# Generate one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
_fernet_key = os.environ.get('FERNET_KEY', '')
if not _fernet_key:
    raise ValueError(
        "FERNET_KEY environment variable is not set. "
        "Copy .env.example to .env and generate a Fernet key."
    )
FERNET_KEY = _fernet_key.encode()


# ─────────────────────────────────────────
# DEFAULT PRIMARY KEY
# ─────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
