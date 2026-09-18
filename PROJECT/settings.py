import json
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from django.contrib.messages import constants as messages

BASE_DIR = Path(__file__).resolve().parent.parent
SECRETS_FILE = BASE_DIR / 'secrets.json'


def load_secrets():
    try:
        with SECRETS_FILE.open(encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise ImproperlyConfigured("Create secrets.json in project root") from exc


creds = load_secrets()


def get_secret(key, default=None):
    if key in creds:
        return creds[key]
    if default is not None:
        return default
    raise ImproperlyConfigured(f'Missing "{key}" in secrets.json')


SECRET_KEY = get_secret('SECRET_KEY')
DEBUG = get_secret('DEBUG', False)
ALLOWED_HOSTS = get_secret('ALLOWED_HOSTS', [])


def _build_default_csrf_trusted_origins(hosts):
    trusted_origins = []
    for host in hosts:
        host = str(host).strip()
        if not host or host == '*':
            continue
        if '://' in host:
            trusted_origins.append(host)
            continue
        trusted_origins.append(f'https://{host}')
        trusted_origins.append(f'http://{host}')
    return list(dict.fromkeys(trusted_origins))


CSRF_TRUSTED_ORIGINS = get_secret(
    'CSRF_TRUSTED_ORIGINS',
    _build_default_csrf_trusted_origins(ALLOWED_HOSTS),
)

if get_secret('USE_REVERSE_PROXY_SSL_HEADER', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'widget_tweaks',
    'apps.core',
    'apps.accounts',
    'apps.documents',
    'apps.notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'PROJECT.urls'

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
                'django.template.context_processors.media',
                'django.template.context_processors.i18n',
                'apps.notifications.context_processors.unread_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'PROJECT.wsgi.application'


# Database
DATABASES = {
    'default': get_secret('DATABASE')
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'ar'
LANGUAGES = [
    ('ar', 'العربية'),
    ('en', 'English'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True


# Static & media files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Authentication
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'documents:dashboard'
LOGOUT_REDIRECT_URL = 'core:home'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days


# Email — used for expiry reminders and account emails
_email_cfg = get_secret('EMAIL', {})
_email_noreply = _email_cfg.get('NOREPLY', {})
EMAIL_BACKEND = _email_cfg.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = _email_noreply.get('HOST', '')
EMAIL_PORT = int(_email_noreply.get('PORT', 465))
EMAIL_HOST_USER = _email_noreply.get('USER', '')
EMAIL_HOST_PASSWORD = _email_noreply.get('PASSWORD', '')
EMAIL_USE_SSL = str(_email_cfg.get('EMAIL_USE_SSL', 'True')).lower() == 'true'
EMAIL_USE_TLS = False
EMAIL_TIMEOUT = int(_email_cfg.get('EMAIL_TIMEOUT', 10))
DEFAULT_FROM_EMAIL = f'MyBox <{EMAIL_HOST_USER}>'

# Base URL used to build absolute links in emails sent from outside a request
# (e.g. the send_expiry_reminders command), where there's no request to derive it from.
SITE_URL = get_secret('SITE_URL', 'http://localhost:8000')


MESSAGE_TAGS = {
    messages.DEBUG: 'alert-secondary',
    messages.INFO: 'alert-info',
    messages.SUCCESS: 'alert-success',
    messages.WARNING: 'alert-warning',
    messages.ERROR: 'alert-danger',
}


# Expiry reminders — how many days ahead of a document's expiry_date to notify.
# Each value fires its own reminder once (see apps.notifications management
# command send_expiry_reminders, run daily via cron/scheduler).
EXPIRY_REMINDER_DAYS = [30, 15, 7, 1]
