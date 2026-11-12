import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Environment Mode: 'development' or 'production' (default)
ENVIRONMENT = os.getenv('ENVIRONMENT', os.getenv('DJANGO_ENV', 'production')).lower().strip()
IS_DEV = ENVIRONMENT in ('dev', 'development', 'local')

SECRET_KEY = os.getenv(
    'SECRET_KEY',
    'django-insecure-custom-rss-dev-key' if IS_DEV else ''
)
if not SECRET_KEY and not IS_DEV:
    import secrets
    SECRET_KEY = secrets.token_urlsafe(50)

# Debug: Development ortamında varsayılan True, Production ortamında varsayılan False
_debug_env = os.getenv('DEBUG')
if _debug_env is not None:
    DEBUG = _debug_env.lower() in ('true', '1', 'yes')
else:
    DEBUG = True if IS_DEV else False

ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '*' if IS_DEV else '').split(',') if h.strip()]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['*'] if IS_DEV else ['localhost', '127.0.0.1']

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost,http://127.0.0.1,http://0.0.0.0:8000' if IS_DEV else 'http://localhost'
    ).split(',') if o.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic' if IS_DEV else 'django.contrib.staticfiles',
    'django.contrib.staticfiles' if IS_DEV else 'django.contrib.staticfiles',
    'feeds.apps.FeedsConfig',
]
INSTALLED_APPS = list(dict.fromkeys(INSTALLED_APPS))

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Docker & Prod ortamında statik dosyaları otomatik sunar
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database configuration: PostgreSQL with SQLite fallback for local test/dev
DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.postgresql' if not IS_DEV else 'django.db.backends.sqlite3')
if DB_ENGINE == 'django.db.backends.postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'custom_rss'),
            'USER': os.getenv('DB_USER', 'custom_rss'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'custom_rss_password'),
            'HOST': os.getenv('DB_HOST', 'db'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'tr-tr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images) & Whitenoise
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage' if not DEBUG else 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom RSS & Auth Settings
WRITE_API_KEY = os.getenv('WRITE_API_KEY', '')
READ_API_KEY = os.getenv('READ_API_KEY', '')
RSS_FEED_LIMIT = int(os.getenv('RSS_FEED_LIMIT', '50'))

# Reverse Proxy & Security Settings
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not IS_DEV and not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1')
    CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'False').lower() in ('true', '1')
