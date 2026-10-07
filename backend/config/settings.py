import os, secrets
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
DEMO_MODE = os.getenv('MENSA_DEMO_MODE', 'true' if DEBUG else 'false').lower() == 'true'
if DEMO_MODE and not DEBUG:
    raise ImproperlyConfigured('Simulação não pode ser habilitada em produção.')
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY é obrigatório.')
    secret_path = BASE_DIR / '.local-secret'
    if not secret_path.exists():
        secret_path.write_text(secrets.token_urlsafe(64))
    SECRET_KEY = secret_path.read_text().strip()
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.staticfiles','rest_framework','governance']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware']
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3','OPTIONS':{'timeout':20}}}
if os.getenv('POSTGRES_HOST'):
    DATABASES = {'default':{'ENGINE':'django.db.backends.postgresql','HOST':os.environ['POSTGRES_HOST'],'NAME':os.getenv('POSTGRES_DB','mensa'),'USER':os.getenv('POSTGRES_USER','mensa'),'PASSWORD':os.environ['POSTGRES_PASSWORD'],'PORT':os.getenv('POSTGRES_PORT','5432')}}
elif not DEBUG:
    raise ImproperlyConfigured('PostgreSQL é obrigatório em produção.')
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'],'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],'EXCEPTION_HANDLER':'governance.api.exception_handler'}
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_TZ = True
STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 43200
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
OIDC_ISSUER = os.getenv('OIDC_ISSUER','')
OIDC_CLIENT_ID = os.getenv('OIDC_CLIENT_ID','')
OIDC_CLIENT_SECRET = os.getenv('OIDC_CLIENT_SECRET','')
OIDC_REQUIRED_ACR = os.getenv('OIDC_REQUIRED_ACR','urn:mensa:mfa')
OIDC_REDIRECT_URI = os.getenv('OIDC_REDIRECT_URI','')

CSRF_TRUSTED_ORIGINS = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173' if DEBUG else '').split(',') if DEBUG or os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS') else []
