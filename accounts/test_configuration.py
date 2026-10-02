import os
import secrets
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class ConfigurationTests(SimpleTestCase):
    def load_configuration(self, overrides=None):
        env = {key: value for key, value in os.environ.items() if not key.startswith(('DJANGO_', 'DB_'))}
        env.update(DJANGO_SECRET_KEY=secrets.token_urlsafe(50), DJANGO_ALLOWED_HOSTS='localhost')
        env.update(overrides or {})
        # Exercise defaults in isolation without loading the developer's private .env.
        script = (
            'from unittest.mock import patch\n'
            'with patch("dotenv.load_dotenv"):\n'
            '    from config import settings\n'
            '    assert settings.DEBUG is False\n'
            '    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"\n'
            '    assert settings.TIME_ZONE == "Asia/Shanghai"\n'
        )
        return subprocess.run(
            [sys.executable, '-c', script], env=env, cwd=settings.BASE_DIR,
            capture_output=True, text=True, timeout=15,
        )

    def test_clean_configuration_defaults_to_sqlite_and_debug_off(self):
        result = self.load_configuration()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_or_placeholder_secret_fails(self):
        for key in ('', 'replace-with-a-generated-secret-key'):
            with self.subTest(key=key):
                result = self.load_configuration({'DJANGO_SECRET_KEY': key})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Set DJANGO_SECRET_KEY', result.stderr)

    def test_debug_off_requires_explicit_hosts(self):
        for hosts in ('', '*'):
            with self.subTest(hosts=hosts):
                result = self.load_configuration({'DJANGO_ALLOWED_HOSTS': hosts})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Set explicit DJANGO_ALLOWED_HOSTS', result.stderr)

    def test_invalid_boolean_or_database_backend_fails(self):
        for overrides, message in (
            ({'DJANGO_DEBUG': 'invalid'}, 'must be a boolean'),
            ({'DB_ENGINE': 'invalid'}, 'DB_ENGINE must be'),
            ({'DB_ENGINE': 'mysql'}, 'MySQL requires'),
        ):
            with self.subTest(overrides=overrides):
                result = self.load_configuration(overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
