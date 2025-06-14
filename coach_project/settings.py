# coach_project/settings.py (Unified for Local and Production)

import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from datetime import timedelta
import datetime

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
dotenv_path = BASE_DIR / '.env'
if os.path.exists(dotenv_path):
    print(f"INFO: Loading .env from {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    print(f"WARNING: .env file not found at {dotenv_path}")

# Determine environment
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'


BONUS_SESSION_START_TIME = datetime.time(6, 0, 0)  # 6:00 AM
BONUS_SESSION_AMOUNT = 22.00


# React App Path


if DEBUG:
    REACT_APP_DIR      = BASE_DIR / 'solosync-pwa'
    FRONTEND_BUILD_DIR = REACT_APP_DIR / 'build'
else:
    # Production on PA: frontend_build lives inside the squash-coach-hub folder
    REACT_APP_DIR      = BASE_DIR / 'frontend_build'
    FRONTEND_BUILD_DIR = REACT_APP_DIR

# --- Security ---
SECRET_KEY = os.environ.get('SECRET_KEY', '!!!DEFINE_SECRET_KEY!!!')
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
    if host.strip()
]

# --- Auth Redirects ---
LOGIN_URL         = '/accounts/login/'
LOGIN_REDIRECT_URL= '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# --- Email Configuration ---
if DEBUG:
    # During local development, print emails to the console
    EMAIL_BACKEND      = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'noreply@squashsync.com'
else:
    # In production, use real SMTP server
    EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST          = os.environ['EMAIL_HOST']
    EMAIL_PORT          = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_HOST_USER     = os.environ['EMAIL_HOST_USER']
    EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD']
    EMAIL_USE_TLS       = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
    DEFAULT_FROM_EMAIL  = os.environ['DEFAULT_FROM_EMAIL']

# Base URL for building links in emails
APP_SITE_URL = os.environ.get('APP_SITE_URL', 'http://127.0.0.1:8000')

# --- Installed Apps ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'planning.apps.PlanningConfig',
    'solosync_api',
    'django_filters',
    'crispy_forms',
    "crispy_bootstrap5"
]

# --- Middleware ---
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'coach_project.urls'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# --- Templates ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
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

WSGI_APPLICATION = 'coach_project.wsgi.application'

# --- Database ---
default_db_url = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', default_db_url)
    )
}

# --- Password Validation ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Internationalization ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Africa/Johannesburg'
USE_I18N      = True
USE_TZ        = True

# --- Static Files ---
STATIC_URL        = '/static/'
STATICFILES_DIRS  = []
STATIC_ROOT       = os.environ.get('STATIC_ROOT', BASE_DIR / 'staticfiles_collected')

# --- Media Files ---
MEDIA_URL = os.environ.get('MEDIA_URL', '/media/')
MEDIA_ROOT= BASE_DIR / 'mediafiles/'

# --- Default Primary Key ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- DRF + JWT ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS':  False,
    'BLACKLIST_AFTER_ROTATION': False,
}

# --- CORS/CSRF ---
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS   = [
    origin.strip() for origin in os.environ.get(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000,http://192.168.3.6:3000'
    ).split(',') if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000,http://192.168.3.6:3000'
    ).split(',') if origin.strip()
]
