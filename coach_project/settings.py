# coach_project/settings.py (Local Version - Configured for Serving Local React Build)

import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from datetime import timedelta

# BASE_DIR points to the 'coach_project' folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Define path to the sibling React frontend app directory
REACT_APP_DIR = BASE_DIR.parent / 'solosync-pwa' # Assumes solosync-pwa is next to coach_project

# Load environment variables from .env file in the Django project base directory
# This should be your LOCAL .env file
dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    print(f"INFO (settings.py): Loading local .env from {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    print(f"WARNING (settings.py): Local .env file not found at {dotenv_path}")

# --- Security Settings ---
# Read from local .env or use a simple fallback for local dev
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-!!set-a-local-secret-key-in-.env!!')
# DEBUG should be True for local development server
DEBUG = True

# --- Host Settings ---
# Allow standard local hosts and your computer's local network IP
# Read from local .env or use defaults
default_allowed_hosts = '127.0.0.1,localhost,192.168.3.6' # Replace 192.168.3.6 if your IP is different
allowed_hosts_str = os.environ.get('ALLOWED_HOSTS', default_allowed_hosts)
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_str.split(',') if host.strip()]
# --- End Host Settings ---


# --- Django Auth URLs (For Coach/Admin Login) ---
LOGIN_URL = '/accounts/login/' # Path defined in coach_project/urls.py
LOGIN_REDIRECT_URL = '/dashboard/' # Path defined in coach_project/urls.py
LOGOUT_REDIRECT_URL = '/accounts/login/' # Where to go after Django logout


# --- Application definition ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles', # Needed for serving static files
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders', # Keep for handling potential CORS during dev if needed
    'planning.apps.PlanningConfig',
    'solosync_api',
    # Removed whitenoise
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', # Keep high up
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Removed custom debug middleware
]

ROOT_URLCONF = 'coach_project.urls'

# *** TEMPLATES setting to find React's index.html ***
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Tell Django to look for templates in the React build directory AND project templates
        'DIRS': [
             os.path.join(str(REACT_APP_DIR), 'build'), # For index.html
             os.path.join(BASE_DIR, 'templates'), # For registration/login.html etc.
             ],
        'APP_DIRS': True, # Keep True for admin and Django app templates
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
# Reads DATABASE_URL from local .env or defaults to SQLite
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
# Tell Django dev server where to find React's static assets AND any other static dirs
STATICFILES_DIRS = [
    os.path.join(str(REACT_APP_DIR), 'build', 'static'), # React static assets
    # Add BASE_DIR / 'static' if you have project-wide static files for Django templates
    # os.path.join(BASE_DIR, 'static'),
]
# STATIC_ROOT is where collectstatic puts files for production deployment
# Define it even for local use, but collectstatic isn't strictly needed for runserver
STATIC_ROOT = os.environ.get('STATIC_ROOT', BASE_DIR / 'staticfiles_collected')
# --- End Static Files ---

# --- Media files ---
MEDIA_URL = os.environ.get('MEDIA_URL', '/media/')
MEDIA_ROOT = BASE_DIR / 'mediafiles/' # Local media storage

# --- Default primary key ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- DRF / JWT ---
REST_FRAMEWORK = { 'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',), 'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',), }
SIMPLE_JWT = { 'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60), 'REFRESH_TOKEN_LIFETIME': timedelta(days=1), 'ROTATE_REFRESH_TOKENS': False, 'BLACKLIST_AFTER_ROTATION': False, }

# --- CORS Settings (Configured for standard local development) ---
# Although less critical when serving from same origin, keep for safety
CORS_ALLOW_CREDENTIALS = True
# Read from local .env or use local defaults (ports might differ if running React dev server)
cors_origins_str = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,http://192.168.3.6:3000')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_str.split(',') if origin.strip()]

# --- CSRF Settings (Configured for standard local development) ---
# Read from local .env or use local defaults
csrf_origins_str = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,http://192.168.3.6:3000')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_str.split(',') if origin.strip()]

