import secrets
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import StudentProfile, TeacherProfile, User
from .services import create_account


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountTests(TestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)

    def student(self, username='student', number='S001'):
        return create_account(
            username=username, password=self.password, role=User.Role.STUDENT,
            first_name='Ada', last_name='Lee',
            profile={'student_number': number, 'date_of_birth': date(2005, 5, 10)},
        )

    def test_three_roles_share_one_authentication_model(self):
        student = self.student()
        teacher = create_account(
            username='teacher', password=self.password, role=User.Role.TEACHER,
            profile={'employee_number': 'T001'},
        )
        administrator = create_account(
            username='administrator', password=self.password,
            role=User.Role.ADMINISTRATOR, is_staff=True,
        )
        self.assertIs(get_user_model(), User)
        self.assertEqual(student.student_profile.user, student)
        self.assertEqual(teacher.teacher_profile.user, teacher)
        self.assertTrue(student.check_password(self.password))
        self.assertNotEqual(student.password, self.password)
        self.assertFalse(StudentProfile.objects.filter(user=administrator).exists())
        self.assertFalse(TeacherProfile.objects.filter(user=administrator).exists())

    def test_profile_display_names(self):
        self.assertEqual(str(self.student().student_profile), 'S001 — Ada Lee')
        teacher = create_account(
            username='teacher', password=None, role=User.Role.TEACHER,
            profile={'employee_number': 'T001'},
        )
        self.assertEqual(str(teacher.teacher_profile), 'T001 — teacher')

    def test_age_changes_on_birthday(self):
        profile = StudentProfile(date_of_birth=date(2005, 5, 10))
        with patch('accounts.models.timezone.localdate', return_value=date(2026, 5, 9)):
            self.assertEqual(profile.age, 20)
        with patch('accounts.models.timezone.localdate', return_value=date(2026, 5, 10)):
            self.assertEqual(profile.age, 21)

    def test_invalid_role_rejected_by_validation_and_database(self):
        with self.assertRaises(ValidationError):
            create_account(username='invalid', password=None, role='invalid')
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username='invalid', role='invalid')

    def test_superuser_is_administrator(self):
        user = User.objects.create_superuser('superuser', password=self.password)
        self.assertEqual(user.role, User.Role.ADMINISTRATOR)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        with self.assertRaises(ValueError):
            User.objects.create_superuser('wrong-role', role=User.Role.STUDENT)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(role=User.Role.TEACHER)

    def test_profile_requires_matching_role(self):
        user = User.objects.create_user('teacher', role=User.Role.TEACHER)
        profile = StudentProfile(user=user, student_number='S001', date_of_birth=date(2005, 5, 10))
        with self.assertRaises(ValidationError) as error:
            profile.full_clean()
        self.assertIn('user', error.exception.message_dict)
        student = self.student()
        with self.assertRaises(ValidationError):
            TeacherProfile(user=student, employee_number='T001').full_clean()

    def test_role_change_rejects_existing_profile(self):
        student = self.student()
        student.role = User.Role.TEACHER
        with self.assertRaises(ValidationError):
            student.full_clean()

    def test_profile_is_one_to_one_and_deleted_with_user(self):
        student = self.student()
        with self.assertRaises(IntegrityError), transaction.atomic():
            StudentProfile.objects.create(
                user=student, student_number='S002', date_of_birth=date(2005, 5, 10),
            )
        student.delete()
        self.assertFalse(StudentProfile.objects.exists())

    def test_invalid_profile_rolls_back_new_user(self):
        self.student()
        with self.assertRaises(ValidationError):
            self.student(username='duplicate', number='S001')
        self.assertFalse(User.objects.filter(username='duplicate').exists())

    def test_profiles_are_required_only_for_students_and_teachers(self):
        for role in (User.Role.STUDENT, User.Role.TEACHER):
            with self.subTest(role=role), self.assertRaises(ValidationError):
                create_account(username='missing', password=None, role=role)
        with self.assertRaises(ValidationError):
            create_account(username='admin', password=None, role=User.Role.ADMINISTRATOR, profile={})

    def test_future_birth_date_rejected(self):
        student = self.student()
        profile = student.student_profile
        profile.date_of_birth = timezone.localdate() + timedelta(days=1)
        with self.assertRaises(ValidationError) as error:
            profile.full_clean()
        self.assertIn('date_of_birth', error.exception.message_dict)
