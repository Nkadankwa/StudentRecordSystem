"""Create a small, clearly fictional local development dataset."""
import os
import secrets
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Permission
from django.db import transaction

from accounts.models import User
from accounts.services import create_account
from academics.models import (AcademicYear, Term, Course, TeachingAssignment, Enrollment,
                              Assessment, Score, AttendanceSession, AttendanceRecord)


class Command(BaseCommand):
    help = 'Create fictional local demo data. Requires DEBUG; never resets existing accounts.'

    def execute(self, *args, **options):
        try:
            return super().execute(*args, **options)
        except ValidationError as error:
            raise CommandError('; '.join(error.messages))

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo data is allowed only with DJANGO_DEBUG=true.')
        roles = User.Role.values
        names = [f'demo-srs-{role}' for role in roles]
        existing = User.objects.filter(username__in=names)
        if existing.exists():
            if existing.count() != len(roles) or any(user.email != f'{user.username}@example.invalid' or user.username != f'demo-srs-{user.role}' for user in existing):
                raise CommandError('Demo account names collide with existing data; no data changed.')
            self.stdout.write('Demo accounts already exist; data and passwords unchanged.')
            return
        if AcademicYear.objects.filter(name='Fictional demo year').exists() or Course.objects.filter(code='DEMO-SRS').exists():
            raise CommandError('Demo academic identifiers already exist; no data changed.')
        password = os.getenv('DEMO_PASSWORD') or secrets.token_urlsafe(24)
        users = {}
        for role in roles:
            username = f'demo-srs-{role}'
            profile = None
            if role == User.Role.STUDENT:
                profile = {'student_number': 'DEMO-SRS-STUDENT', 'date_of_birth': date(2005, 1, 1), 'nationality': 'Fictional'}
            elif role == User.Role.TEACHER:
                profile = {'employee_number': 'DEMO-SRS-TEACHER'}
            users[role] = create_account(username=username, password=password, role=role, profile=profile,
                first_name='Fictional', last_name=role.title(), email=f'{username}@example.invalid',
                is_staff=role == User.Role.ADMINISTRATOR)
        users[User.Role.ADMINISTRATOR].user_permissions.set(Permission.objects.filter(content_type__app_label__in=['accounts', 'academics']))
        year = AcademicYear.objects.create(name='Fictional demo year', start_date=date(2030, 1, 1), end_date=date(2030, 12, 31))
        term = Term.objects.create(academic_year=year, name='Fictional demo term', start_date=year.start_date, end_date=year.end_date)
        course = Course.objects.create(code='DEMO-SRS', title='Fictional demonstration course')
        teacher = users[User.Role.TEACHER].teacher_profile
        student = users[User.Role.STUDENT].student_profile
        TeachingAssignment.objects.create(teacher=teacher, course=course, term=term)
        Enrollment.objects.create(student=student, course=course, term=term, enrollment_date=date(2030, 1, 1))
        assessment = Assessment.objects.create(course=course, term=term, title='Fictional demonstration assessment', maximum_score=Decimal('100'), weight=Decimal('100'))
        Score.objects.create(assessment=assessment, student=student, value=Decimal('80'), updated_by=users[User.Role.TEACHER])
        session = AttendanceSession.objects.create(course=course, term=term, teacher=teacher, date=date(2030, 2, 1), lesson_label='Fictional demonstration lesson')
        AttendanceRecord.objects.create(session=session, student=student, status=AttendanceRecord.Status.PRESENT, updated_by=users[User.Role.TEACHER])
        self.stdout.write('Fictional demo created. Usernames: ' + ', '.join(names))
        if os.getenv('DEMO_PASSWORD'):
            self.stdout.write('Passwords use your DEMO_PASSWORD environment value.')
        else:
            self.stdout.write('Generated local demo password (shown once): ' + password)
