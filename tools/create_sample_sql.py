"""Generate fictional SQLite INSERTs in a disposable database, never the live DB."""
import argparse
from datetime import date, timedelta
import os
from pathlib import Path
import secrets
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def generate(destination, preview=None):
    with tempfile.TemporaryDirectory(prefix='.release-check-sql-', dir=ROOT) as scratch:
        os.environ.update(DJANGO_SETTINGS_MODULE='config.settings', DJANGO_DEBUG='true',
            DJANGO_SECRET_KEY=secrets.token_urlsafe(50), DJANGO_ALLOWED_HOSTS='testserver',
            DB_ENGINE='sqlite', DB_NAME=str(Path(scratch) / 'sample.sqlite3'))
        import django
        django.setup()
        from django.core.management import call_command
        from django.db import connection
        from django.test import Client
        from django.utils import timezone
        from accounts.models import User
        from accounts.services import create_account
        from academics.models import (AcademicYear, Term, Course, TeachingAssignment, Enrollment,
                                      Assessment, Score, AttendanceSession, AttendanceRecord)
        call_command('migrate', verbosity=0)
        objects, keys = [], {}

        def add(obj, **identity):
            objects.append(obj)
            keys[(type(obj), obj.pk)] = identity
            return obj

        def literal(value):
            if value is None:
                return 'NULL'
            if isinstance(value, bool):
                return '1' if value else '0'
            if isinstance(value, (int, float)):
                return str(value)
            return "'" + str(value).replace("'", "''") + "'"

        def reference(model, pk):
            terms = []
            for name, value in keys[(model, pk)].items():
                field = model._meta.get_field(name)
                sql = reference(field.related_model, value) if field.is_relation else literal(value)
                terms.append(f'"{field.column}" = {sql}')
            return f'(SELECT "id" FROM "{model._meta.db_table}" WHERE ' + ' AND '.join(terms) + ')'

        today = timezone.localdate()
        year_name = f'{today.year} Academic year'
        year = add(AcademicYear.objects.create(name=year_name, start_date=date(today.year, 1, 1),
                   end_date=date(today.year, 12, 31), is_active=True), name=year_name)
        semester = 1 if today.month <= 6 else 2
        term_name = f'Semester {semester}'
        term = add(Term.objects.create(academic_year=year, name=term_name,
                   start_date=date(today.year, 1 if semester == 1 else 7, 1),
                   end_date=date(today.year, 6, 30) if semester == 1 else year.end_date),
                   academic_year=year.pk, name=term_name)
        admin = add(create_account(username='evelyn.hart', password=None, role='administrator',
                    first_name='Evelyn', last_name='Hart', email='evelyn.hart@example.invalid',
                    is_staff=True), username='evelyn.hart')
        teachers = []
        for number, (first_name, last_name) in enumerate([('Nadia', 'Rahman'), ('Oliver', 'Brooks')], 1):
            username = f'{first_name}.{last_name}'.lower()
            user = add(create_account(username=username, password=None, role='teacher',
                first_name=first_name, last_name=last_name,
                email=f'{first_name.lower()}.{last_name.lower()}@example.invalid',
                profile={'employee_number': f'EMP-{number:03}'}),
                username=username)
            teachers.append(add(user.teacher_profile, employee_number=f'EMP-{number:03}'))
        students = []
        names = [
            ('Iris', 'Chen'), ('Mateo', 'Silva'), ('Amara', 'Okafor'), ('Noah', 'Bennett'),
            ('Leila', 'Hassan'), ('Ethan', 'Park'), ('Sofia', 'Moretti'), ('Arjun', 'Mehta'),
            ('Chloe', 'Dubois'), ('Luca', 'Romano'), ('Maya', 'Patel'), ('Daniel', 'Reyes'),
            ('Zara', 'Ali'), ('Felix', 'Weber'), ('Aisha', 'Mensah'), ('Oscar', 'Lindberg'),
            ('Hana', 'Sato'), ('Lucas', 'Ferreira'), ('Nora', 'Walsh'), ('Rafael', 'Costa'),
            ('Anika', 'Sharma'), ('Julian', "O'Connell"), ('Elena', 'Petrova'), ('Theo', 'Martin'),
        ]
        nationalities = ['Chinese', 'Brazilian', 'Nigerian', 'Canadian', 'Egyptian', 'South Korean',
            'Italian', 'Indian', 'French', 'Italian', 'Indian', 'Mexican', 'Pakistani', 'German',
            'Ghanaian', 'Swedish', 'Japanese', 'Portuguese', 'Irish', 'Brazilian', 'Indian',
            'Irish', 'Bulgarian', 'Australian']
        for number, (first_name, last_name) in enumerate(names, 1):
            student_number = f'STU-{today.year}-{number:03}'
            username = f'{first_name}.{last_name}'.lower().replace("'", '')
            user = add(create_account(username=username, password=None, role='student',
                first_name=first_name, last_name=last_name,
                email=f'{username}@example.invalid', profile={'student_number': student_number,
                'date_of_birth': date(today.year-18-(number%3), 1+(number%12), 1+(number*7%27)),
                'nationality': nationalities[number-1], 'gender': 'Female' if number % 2 else 'Male'}),
                username=username)
            students.append(add(user.student_profile, student_number=student_number))
        courses = [
            ('MTH101', 'Mathematics', 'Algebra, functions and introductory statistics.',
             ['Linear equations quiz', 'Statistics investigation'],
             ['Quadratic functions', 'Probability distributions', 'Linear equations', 'Descriptive statistics']),
            ('CSC101', 'Computer science', 'Programming fundamentals and computational thinking.',
             ['Python fundamentals quiz', 'Library catalogue project'],
             ['Functions and scope', 'Lists and dictionaries', 'Loops and conditions', 'Problem decomposition']),
            ('ENG101', 'English language', 'Reading comprehension, academic writing and oral communication.',
             ['Reading comprehension test', 'Persuasive essay'],
             ['Persuasive writing', 'Close reading', 'Essay structure', 'Oral presentations']),
        ]
        for number, (code, title, description, assessment_titles, lessons) in enumerate(courses):
            teacher = teachers[number % 2]
            course = add(Course.objects.create(code=code, title=title, description=description), code=code)
            add(TeachingAssignment.objects.create(teacher=teacher, course=course, term=term),
                teacher=teacher.pk, course=course.pk, term=term.pk, section='')
            for student in students:
                add(Enrollment.objects.create(student=student, course=course, term=term,
                    enrollment_date=term.start_date),
                    student=student.pk, course=course.pk, term=term.pk)
            for label in assessment_titles:
                assessment = add(Assessment.objects.create(course=course, term=term, title=label,
                    maximum_score=100, weight=50, due_date=today), course=course.pk, term=term.pk, title=label)
                for index, student in enumerate(students):
                    add(Score.objects.create(student=student, assessment=assessment, value=55+(index*7+number)%45,
                        updated_by=teacher.user), student=student.pk, assessment=assessment.pk)
            for day in range(4):
                session_date = max(term.start_date, today-timedelta(days=day))
                session = add(AttendanceSession.objects.create(course=course, term=term, teacher=teacher,
                    date=session_date, lesson_label=lessons[day]), course=course.pk, term=term.pk,
                    date=session_date, lesson_label=lessons[day])
                for index, student in enumerate(students):
                    add(AttendanceRecord.objects.create(student=student, session=session,
                        status=['present', 'present', 'present', 'late', 'excused', 'absent'][(index+day)%6],
                        updated_by=teacher.user), student=student.pk, session=session.pk)
        lines = ['-- Fictional SQLite sample data. Run migrations first. Import once; duplicates fail.',
                 '-- No preset passwords. Use manage.py changepassword after import.',
                 'PRAGMA foreign_keys=ON;', 'BEGIN IMMEDIATE;']
        for obj in objects:
            columns, values = [], []
            for field in obj._meta.concrete_fields:
                if field.primary_key:
                    continue
                columns.append(f'"{field.column}"')
                value = getattr(obj, field.attname)
                if field.name == 'password':
                    value = '!'
                if not field.is_relation:
                    value = field.get_db_prep_value(value, connection)
                values.append(reference(field.related_model, value) if field.is_relation and value is not None else literal(value))
            lines.append(f'INSERT INTO "{obj._meta.db_table}" ({", ".join(columns)}) VALUES ({", ".join(values)});')
        lines.append('INSERT INTO accounts_user_user_permissions (user_id, permission_id) SELECT '
            + reference(User, admin.pk) + ', p.id FROM auth_permission p JOIN django_content_type c ON p.content_type_id=c.id '
            + "WHERE c.app_label IN ('accounts', 'academics');")
        lines.append('COMMIT;')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        if preview:
            preview.mkdir(parents=True, exist_ok=True)
            # Fictional preview only: mirror the permissions granted by the SQL.
            from django.contrib.auth.models import Permission
            admin.user_permissions.set(Permission.objects.filter(content_type__app_label__in=['accounts', 'academics']))
            for user in [admin, teachers[0].user, students[0].user]:
                client = Client(); client.force_login(user)
                response = client.get(f'/accounts/home/{user.role}/')
                assert response.status_code == 200
                html = response.content.decode()
                for filename in ['app.css', 'dashboard.css', 'print.css']:
                    media = ' media="print"' if filename == 'print.css' else ''
                    html = html.replace(f'<link rel="stylesheet" href="/static/css/{filename}"{media}>',
                        f'<style{media}>{(ROOT/"static/css"/filename).read_text()}</style>')
                (preview/f'{user.role}.html').write_text(html, encoding='utf-8')
        connection.close()
        print('Created fictional SQL: 24 students, 2 teachers, 3 courses, 144 scores and 288 attendance records.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'data/sample-data.sqlite.sql')
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    generate(args.output, args.preview)
