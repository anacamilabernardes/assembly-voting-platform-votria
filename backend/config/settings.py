import os
import re
import secrets
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
DEMO_MODE = os.getenv('VOTRIA_DEMO_MODE', 'true' if DEBUG else 'false').lower() == 'true'
DEMO_ACCESS_PASSWORD = os.getenv('VOTRIA_DEMO_ACCESS_PASSWORD', '')
if DEMO_MODE and not DEBUG and len(DEMO_ACCESS_PASSWORD) < 16:
    raise ImproperlyConfigured(
        'Online demo requires VOTRIA_DEMO_ACCESS_PASSWORD to contain at least 16 characters.'
    )
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY é obrigatório.')
    secret_path = BASE_DIR / '.local-secret'
    if not secret_path.exists():
        secret_path.write_text(secrets.token_urlsafe(64))
    SECRET_KEY = secret_path.read_text().strip()
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
RENDER_HOST = os.getenv('RENDER_EXTERNAL_HOSTNAME', '')
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'rest_framework',
    'governance',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.security.ContentSecurityPolicyMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': ['django.template.context_processors.request']},
    }
]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DJANGO_SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')),
        'OPTIONS': {'timeout': 20},
    }
}
if os.getenv('DATABASE_URL'):
    database_url = urlparse(os.environ['DATABASE_URL'])
    if (
        database_url.scheme not in ('postgres', 'postgresql')
        or not database_url.hostname
        or not database_url.path.strip('/')
    ):
        raise ImproperlyConfigured('DATABASE_URL deve apontar para um banco PostgreSQL.')
    database_options = {}
    sslmode = parse_qs(database_url.query).get('sslmode', [None])[0]
    if sslmode:
        database_options['sslmode'] = sslmode
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': database_url.hostname,
            'NAME': unquote(database_url.path[1:]),
            'USER': unquote(database_url.username or ''),
            'PASSWORD': unquote(database_url.password or ''),
            'PORT': database_url.port or 5432,
            'CONN_MAX_AGE': 60,
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': database_options,
        }
    }
elif os.getenv('POSTGRES_HOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': os.environ['POSTGRES_HOST'],
            'NAME': os.getenv('POSTGRES_DB', 'votria'),
            'USER': os.getenv('POSTGRES_USER', 'votria'),
            'PASSWORD': os.environ['POSTGRES_PASSWORD'],
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }
elif not DEBUG:
    raise ImproperlyConfigured('PostgreSQL é obrigatório em produção.')
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'EXCEPTION_HANDLER': 'governance.api.exception_handler',
}
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_TZ = True
FRONTEND_DIST = BASE_DIR.parent / 'frontend' / 'dist'
STATIC_URL = '/assets/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [FRONTEND_DIST / 'assets'] if (FRONTEND_DIST / 'assets').exists() else []
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 43200
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
# Only Render's managed reverse proxy is trusted to supply this header.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if RENDER_HOST else None
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
OIDC_ISSUER = os.getenv('OIDC_ISSUER', '')
OIDC_CLIENT_ID = os.getenv('OIDC_CLIENT_ID', '')
OIDC_CLIENT_SECRET = os.getenv('OIDC_CLIENT_SECRET', '')
OIDC_REQUIRED_ACR = os.getenv('VOTRIA_REQUIRED_ACR', '')
# One institution per deployment: its display name and the email domain every member must use.
VOTRIA_INSTITUTION_NAME = os.getenv('VOTRIA_INSTITUTION_NAME', '').strip()
VOTRIA_ALLOWED_EMAIL_DOMAIN = os.getenv('VOTRIA_ALLOWED_EMAIL_DOMAIN', '').strip().lower().lstrip('@')
if VOTRIA_ALLOWED_EMAIL_DOMAIN and not re.fullmatch(
    r'(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}',
    VOTRIA_ALLOWED_EMAIL_DOMAIN,
):
    raise ImproperlyConfigured('VOTRIA_ALLOWED_EMAIL_DOMAIN must be a single domain such as example.org.')
OIDC_REDIRECT_URI = os.getenv('OIDC_REDIRECT_URI', '')
# Operational data (proxy codes, session identifiers, idempotency receipts) is purged after this period.
VOTRIA_RETENTION_DAYS = int(os.getenv('VOTRIA_RETENTION_DAYS', '365'))

CSRF_TRUSTED_ORIGINS = (
    os.getenv(
        'DJANGO_CSRF_TRUSTED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173' if DEBUG else ''
    ).split(',')
    if DEBUG or os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS')
    else []
)
if RENDER_HOST:
    CSRF_TRUSTED_ORIGINS.append('https://' + RENDER_HOST)
