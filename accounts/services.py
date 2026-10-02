"""Explicit account creation; no signals create hidden or incomplete profiles."""
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .models import StudentProfile, TeacherProfile, User


@transaction.atomic
def create_account(*, username, password, role, profile=None, **user_fields):
    """Create a validated account and required role profile in one transaction.

    Student profile data includes student_number and date_of_birth; teacher data
    includes employee_number. Names and email belong to the user.
    """
    profile_models = {
        User.Role.STUDENT: StudentProfile,
        User.Role.TEACHER: TeacherProfile,
    }
    if role not in User.Role.values:
        raise ValidationError({'role': 'Select a valid role.'})
    if role == User.Role.ADMINISTRATOR and profile is not None:
        raise ValidationError('Administrators do not have a separate role profile.')
    if role in profile_models and profile is None:
        raise ValidationError('Profile data is required for students and teachers.')
    user = User(username=username, role=role, **user_fields)
    if password is not None:
        validate_password(password, user=user)
    user.set_password(password)
    user.full_clean()
    user.save()
    if role in profile_models:
        role_profile = profile_models[role](user=user, **profile)
        role_profile.full_clean()
        role_profile.save()
    return user
