import logging
import os
import secrets
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase
from config.security import SafeRequestLogFilter


class ProductionTests(SimpleTestCase):
    def environment(self):
        env = dict(os.environ)
        env.update(DJANGO_SETTINGS_MODULE='config.production', DJANGO_SECRET_KEY=secrets.token_urlsafe(50),
            DJANGO_DEBUG='false', DJANGO_ALLOWED_HOSTS='deployment.example.invalid',
            DJANGO_CSRF_TRUSTED_ORIGINS='https://deployment.example.invalid', DJANGO_TRUST_PROXY='false', DB_ENGINE='sqlite')
        return env

    def test_production_deployment_checks_pass(self):
        result = subprocess.run([sys.executable, 'manage.py', 'check', '--deploy', '--settings=config.production'],
            env=self.environment(), cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('no issues', result.stdout)

    def test_production_disables_debug_even_when_environment_enables_it(self):
        env = self.environment(); env['DJANGO_DEBUG'] = 'true'
        script = 'from config import production as p; assert not p.DEBUG; assert p.SESSION_COOKIE_SECURE and p.CSRF_COOKIE_SECURE; assert p.SECURE_SSL_REDIRECT; assert p.SECURE_PROXY_SSL_HEADER is None'
        result = subprocess.run([sys.executable, '-c', script], env=env, cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_request_logs_remove_private_details(self):
        record = logging.LogRecord('django.request', logging.ERROR, '', 1, 'private request body and password', (), None)
        record.request = object(); record.status_code = 500
        SafeRequestLogFilter().filter(record)
        self.assertEqual(record.getMessage(), 'HTTP request event (status 500)')
        self.assertIsNone(record.exc_info)
        self.assertFalse(hasattr(record, 'request'))

    def test_unsafe_origins_and_weak_keys_fail_closed(self):
        for variable, value in [('DJANGO_CSRF_TRUSTED_ORIGINS', 'http://deployment.example.invalid'),
                                ('DJANGO_SECRET_KEY', 'weak-key'), ('DJANGO_ALLOWED_HOSTS', '*')]:
            env = self.environment(); env[variable] = value
            result = subprocess.run([sys.executable, '-c', 'import config.production'], env=env,
                cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('ImproperlyConfigured', result.stderr)
