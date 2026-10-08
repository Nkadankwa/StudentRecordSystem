import os
import secrets
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from academics.models import Score, AttendanceRecord, Enrollment


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DemoDataTests(TestCase):
    def test_seed_creates_all_roles_and_academic_records_and_is_idempotent(self):
        password = secrets.token_urlsafe(24)
        with patch.dict(os.environ, {'DEMO_PASSWORD': password}):
            call_command('seed_demo', stdout=StringIO())
        self.assertEqual(set(User.objects.values_list('role', flat=True)), set(User.Role.values))
        self.assertTrue(User.objects.get(username='demo-srs-administrator').has_perm('academics.add_course'))
        self.assertEqual(Score.objects.count(), 1)
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertTrue(User.objects.get(username='demo-srs-student').check_password(password))
        call_command('seed_demo', stdout=StringIO())
        self.assertEqual(User.objects.count(), 3)
        self.assertTrue(User.objects.get(username='demo-srs-student').check_password(password))

    @override_settings(DEBUG=False)
    def test_seed_refuses_production(self):
        with self.assertRaises(CommandError):
            call_command('seed_demo', stdout=StringIO())
        self.assertFalse(User.objects.exists())

    def test_seed_refuses_username_collision(self):
        existing = User.objects.create_user(username='demo-srs-student')
        with self.assertRaises(CommandError):
            call_command('seed_demo', stdout=StringIO())
        self.assertEqual(User.objects.count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.email, '')

    def test_generated_password_is_not_hardcoded(self):
        out = StringIO()
        with patch.dict(os.environ):
            os.environ.pop('DEMO_PASSWORD', None)
            call_command('seed_demo', stdout=out)
        password = out.getvalue().split('shown once): ')[1].strip()
        self.assertTrue(User.objects.get(username='demo-srs-student').check_password(password))


    def test_weak_environment_password_rolls_back_all_data(self):
        with patch.dict(os.environ, {'DEMO_PASSWORD': secrets.choice('abc')}):
            with self.assertRaises(CommandError):
                call_command('seed_demo', stdout=StringIO())
        self.assertFalse(User.objects.exists())
        self.assertFalse(Enrollment.objects.exists())
