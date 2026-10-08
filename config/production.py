"""Production settings. Supply deployment values through the environment."""
from urllib.parse import urlsplit

from .settings import *  # noqa: F403

DEBUG = False
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Production requires explicit DJANGO_ALLOWED_HOSTS.')
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('Production requires a strong generated DJANGO_SECRET_KEY.')

CSRF_TRUSTED_ORIGINS = [item.strip() for item in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if item.strip()]
for origin in CSRF_TRUSTED_ORIGINS:
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or '*' in origin:
        raise ImproperlyConfigured('CSRF trusted origins must be explicit HTTPS origins without paths.')

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
try:
    SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '31536000'))
except ValueError:
    raise ImproperlyConfigured('DJANGO_HSTS_SECONDS must be a positive integer.')
if SECURE_HSTS_SECONDS <= 0:
    raise ImproperlyConfigured('DJANGO_HSTS_SECONDS must be a positive integer.')
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# Enable only when your trusted proxy strips incoming forwarding headers.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if env_bool('DJANGO_TRUST_PROXY', False) else None
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Notifications are deferred; configure an SMTP service before sending mail.
MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.smtp.EmailBackend', 'OPTIONS': {
    'host': os.getenv('SMTP_HOST', 'localhost'),
    'port': int(os.getenv('SMTP_PORT', '587')),
    'username': os.getenv('SMTP_USER', ''),
    'password': os.getenv('SMTP_PASSWORD', ''),
    'use_tls': True,
    'timeout': 10,
}}}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {'safe_request': {'()': 'config.security.SafeRequestLogFilter'}},
    'formatters': {'safe': {'format': '%(levelname)s %(message)s'}},
    'handlers': {'safe_console': {'class': 'logging.StreamHandler', 'filters': ['safe_request'], 'formatter': 'safe'}},
    'loggers': {
        'django.request': {'handlers': ['safe_console'], 'level': 'WARNING', 'propagate': False},
        'django.security': {'handlers': ['safe_console'], 'level': 'WARNING', 'propagate': False},
        'django.server': {'handlers': ['safe_console'], 'level': 'WARNING', 'propagate': False},
    },
}
