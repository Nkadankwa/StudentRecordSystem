from pathlib import Path
from collections import Counter
import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q
from django.core.exceptions import ValidationError


class Command(BaseCommand):
    help = 'Load the bundled fictional SQLite sample dataset once (development only).'

    def add_arguments(self, parser):
        parser.add_argument('--refresh-names', action='store_true', help='Replace generic names/profile details in existing sample accounts; preserve passwords and records.')
        parser.add_argument('--refresh-data', action='store_true', help='Remove legacy placeholder labels and identifiers from the existing fictional dataset.')

    @transaction.atomic
    def refresh_names(self, source, all_data=False):
        from accounts.models import User
        # Read the bundled fixture in memory; never parse or copy private DB rows.
        fixture = sqlite3.connect(':memory:')
        fixture.row_factory = sqlite3.Row
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
                for (schema,) in cursor.fetchall():
                    fixture.execute(schema)
            fixture.executescript(source.read_text(encoding='utf-8'))
            changed = 0
            numbers = Counter()
            for row in fixture.execute('SELECT * FROM accounts_user ORDER BY id'):
                numbers[row['role']] += 1
                number = numbers[row['role']]
                legacy = 'sample-srs-administrator' if row['role'] == 'administrator' else (
                    f'sample-srs-student-{number:03}' if row['role'] == 'student' else f'sample-srs-teacher-{number}')
                matches = User.objects.filter(Q(username=row['username']) | Q(username=legacy))
                if matches.count() > 1:
                    raise CommandError('A fictional login name conflicts with another account. No records changed.')
                user = matches.first()
                if user is None:
                    continue
                if user.role != row['role']:
                    raise CommandError('A dataset login belongs to a different role. No records changed.')
                generic = user.first_name == 'Sample'
                fields = []
                if generic:
                    for field in ('first_name', 'last_name', 'email'):
                        setattr(user, field, row[field])
                        fields.append(field)
                if all_data and user.username == legacy:
                    user.username = row['username']
                    fields.append('username')
                if fields:
                    user.save(update_fields=fields)
                    changed += 1
                if user.role == User.Role.STUDENT and hasattr(user, 'student_profile'):
                    profile_data = fixture.execute('SELECT * FROM accounts_studentprofile WHERE user_id = ?', [row['id']]).fetchone()
                    profile = user.student_profile
                    profile_fields = []
                    if profile_data and generic:
                        for field in ('date_of_birth', 'nationality', 'gender'):
                            setattr(profile, field, profile_data[field])
                            profile_fields.append(field)
                    if profile_data and all_data and profile.student_number.startswith('SAMPLE-'):
                        profile.student_number = profile_data['student_number']
                        profile_fields.append('student_number')
                    if profile_fields:
                        profile.full_clean()
                        profile.save(update_fields=profile_fields)
                if all_data and user.role == 'teacher' and hasattr(user, 'teacher_profile'):
                    profile = user.teacher_profile
                    if profile.employee_number.startswith('SAMPLE-'):
                        profile.employee_number = f'EMP-{number:03}'
                        profile.full_clean()
                        profile.save(update_fields=['employee_number'])
            if all_data:
                self.refresh_labels(fixture)
            self.stdout.write(self.style.SUCCESS(f'Refreshed {changed} fictional accounts{ " and dataset labels" if all_data else ""}. Passwords and academic records preserved.'))
        finally:
            fixture.close()

    def refresh_labels(self, fixture):
        from academics.models import AcademicYear, Term, Course, Assessment, AttendanceSession

        def update(obj, values):
            for field, value in values.items():
                setattr(obj, field, value)
            obj.full_clean()
            obj.save(update_fields=list(values))

        for row in fixture.execute('SELECT * FROM academics_academicyear'):
            year = AcademicYear.objects.filter(name=f'SAMPLE {row["start_date"][:4]}').first()
            if year:
                update(year, {'name': row['name']})
            else:
                year = AcademicYear.objects.filter(name=row['name']).first()
            if year:
                term = Term.objects.filter(academic_year=year, name='Sample term').first()
                if term:
                    name = fixture.execute('SELECT name FROM academics_term WHERE academic_year_id = ?', [row['id']]).fetchone()[0]
                    update(term, {'name': name})
        for number, row in enumerate(fixture.execute('SELECT * FROM academics_course ORDER BY id'), 1):
            course = Course.objects.filter(code=f'SAMPLE-{number}').first()
            if course:
                update(course, {field: row[field] for field in ('code', 'title', 'description')})
            else:
                course = Course.objects.filter(code=row['code']).first()
            if not course:
                continue
            assessments = fixture.execute('SELECT title FROM academics_assessment WHERE course_id = ? ORDER BY id', [row['id']]).fetchall()
            for old, new in zip(('Sample Quiz', 'Sample Coursework'), assessments):
                for assessment in Assessment.objects.filter(course=course, title=old):
                    update(assessment, {'title': new['title']})
            lessons = fixture.execute('SELECT lesson_label FROM academics_attendancesession WHERE course_id = ? ORDER BY id', [row['id']]).fetchall()
            for day, lesson in enumerate(lessons, 1):
                for session in AttendanceSession.objects.filter(course=course, lesson_label=f'Sample lesson {day}'):
                    update(session, {'lesson_label': lesson['lesson_label']})

    def handle(self, *args, **options):
        if not settings.DEBUG or connection.vendor != 'sqlite':
            raise CommandError('Sample SQL requires DEBUG and SQLite.')
        source = Path(settings.BASE_DIR) / 'data/sample-data.sqlite.sql'
        connection.ensure_connection()
        if options['refresh_names'] or options['refresh_data']:
            try:
                self.refresh_names(source, all_data=options['refresh_data'])
            except (ValidationError, sqlite3.Error, OSError) as error:
                raise CommandError('Fictional data refresh failed validation. No records changed; check identifier conflicts.') from error
            return
        try:
            connection.connection.executescript(source.read_text(encoding='utf-8'))
        except (sqlite3.Error, OSError) as error:
            if connection.connection.in_transaction:
                connection.connection.rollback()
            if isinstance(error, sqlite3.IntegrityError):
                raise CommandError('Dataset identifiers already exist or violate a database constraint. No rows changed. For the earlier dataset, use load_sample_sql --refresh-data, or sign in to use the existing data.') from error
            raise CommandError('Sample import failed; no rows changed. Check that migrations ran and data/sample-data.sqlite.sql exists.') from error
        self.stdout.write(self.style.SUCCESS('Fictional sample data imported. Set account passwords with changepassword.'))
