# coach_project/settings.py (Corrected TEMPLATES DIRS)

import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
REACT_APP_DIR = BASE_DIR.parent / 'solosync-pwa'

dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# --- Security Settings ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-!!set-local-secret-key-in-env!!')
DEBUG = True
default_allowed_hosts = '127.0.0.1,localhost,192.168.3.6'
allowed_hosts_str = os.environ.get('ALLOWED_HOSTS', default_allowed_hosts)
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_str.split(',') if host.strip()]

# --- Django Auth URLs ---
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# --- Application definition ---
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
]

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

# *** CORRECTED TEMPLATES SETTING ***
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Add BOTH the project-level templates directory AND the React build directory
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'), # <-- ADDED: For registration/login.html etc.
            os.path.join(str(REACT_APP_DIR), 'build') # <-- Keep: For React's index.html
        ],
        'APP_DIRS': True, # Keep True for admin and app templates
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
# *** END TEMPLATES SETTING ***

WSGI_APPLICATION = 'coach_project.wsgi.application'

# --- Database ---
default_db_url = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASES = { 'default': dj_database_url.config(default=os.environ.get('DATABASE_URL', default_db_url)) }

# --- Password validation ---
AUTH_PASSWORD_VALIDATORS = [ {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',} ]

# --- Internationalization ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True

# --- Static files (CSS, JavaScript, Images) ---
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(str(REACT_APP_DIR), 'build', 'static'),
    # Add project base static dir if you have one: os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.environ.get('STATIC_ROOT', BASE_DIR / 'staticfiles_collected')

# --- Media files ---
MEDIA_URL = os.environ.get('MEDIA_URL', '/media/')
MEDIA_ROOT = BASE_DIR / 'mediafiles/'

# --- Default primary key ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- DRF / JWT ---
REST_FRAMEWORK = { 'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',), 'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',), }
SIMPLE_JWT = { 'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60), 'REFRESH_TOKEN_LIFETIME': timedelta(days=1), 'ROTATE_REFRESH_TOKENS': False, 'BLACKLIST_AFTER_ROTATION': False, }

# --- CORS Settings (Configured for local development) ---
CORS_ALLOW_CREDENTIALS = True
cors_origins_str = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,http://192.168.3.6:3000')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_str.split(',') if origin.strip()]

# --- CSRF Settings (Configured for local development) ---
csrf_origins_str = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,http://192.168.3.6:3000')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_str.split(',') if origin.strip()]

