"""Repeatable synthetic benchmark and backup drill; never opens the local database."""
import argparse
from contextlib import closing
from datetime import date
import json
import os
import re
from pathlib import Path
import secrets
import sqlite3
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(directory, review_dir=None):
    os.environ.update(DJANGO_SETTINGS_MODULE='config.settings', DJANGO_DEBUG='true',
        DJANGO_SECRET_KEY=secrets.token_urlsafe(50), DJANGO_ALLOWED_HOSTS='testserver',
        DB_ENGINE='sqlite', DB_NAME=str(directory / 'benchmark.sqlite3'))
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connection
    from django.test import Client
    from django.test.utils import CaptureQueriesContext
    from accounts.models import User, StudentProfile, TeacherProfile
    from academics.models import (AcademicYear, Term, Course, TeachingAssignment,
        Enrollment, Assessment, Score, AttendanceSession, AttendanceRecord)

    call_command('migrate', verbosity=0)
    admin = User.objects.create_superuser(username='benchmark-admin', password=None)
    teacher = TeacherProfile.objects.create(user=User.objects.create_user(username='benchmark-teacher',
        role=User.Role.TEACHER), employee_number='BENCH-T')
    # Bulk insertion is confined to this controlled fixture, never record-entry code.
    users = User.objects.bulk_create([User(username=f'benchmark-student-{i}', password='!',
        first_name='Fictional', last_name=f'Student {i}', role=User.Role.STUDENT) for i in range(100)])
    students = StudentProfile.objects.bulk_create([StudentProfile(user=u, student_number=f'BENCH-{i:04}',
        date_of_birth=date(2010, 1, 1)) for i, u in enumerate(users)])
    year = AcademicYear.objects.create(name='Benchmark 2030', start_date=date(2030, 1, 1), end_date=date(2030, 12, 31))
    terms = [Term.objects.create(academic_year=year, name=f'Term {i}', start_date=start, end_date=end)
        for i, start, end in [(1, date(2030, 1, 1), date(2030, 6, 30)), (2, date(2030, 7, 1), date(2030, 12, 31))]]
    courses = [Course.objects.create(code=f'BENCH{i}', title=f'Fictional course {i}') for i in range(5)]
    for term in terms:
        for course in courses:
            TeachingAssignment.objects.create(teacher=teacher, course=course, term=term)
            Enrollment.objects.bulk_create([Enrollment(student=s, course=course, term=term) for s in students])
            assessment = Assessment.objects.create(course=course, term=term, title='Fictional assessment', maximum_score=100, weight=100)
            session = AttendanceSession.objects.create(course=course, term=term, teacher=teacher, date=term.start_date)
            Score.objects.bulk_create([Score(student=s, assessment=assessment, value=80, updated_by=teacher.user) for s in students])
            AttendanceRecord.objects.bulk_create([AttendanceRecord(student=s, session=session, status='present', updated_by=teacher.user) for s in students])

    client = Client(); client.force_login(teacher.user)
    routes = {'student_lookup': '/students/?q=BENCH-', 'scores': '/academics/scores/', 'attendance': '/academics/attendance/'}
    results = {}
    for name, url in routes.items():
        assert client.get(url).status_code == 200
        timings, counts = [], []
        for _ in range(3):
            with CaptureQueriesContext(connection) as queries:
                start = time.perf_counter()
                response = client.get(url)
                timings.append(time.perf_counter() - start)
            assert response.status_code == 200
            counts.append(len(queries))
        results[name] = {'median_seconds': round(statistics.median(timings), 4), 'queries': max(counts)}
        assert max(timings) < 2, f'{name} exceeded the two-second target'
        assert max(counts) <= 15, f'{name} exceeded the query budget'

    backup = directory / 'snapshot.sqlite3'
    call_command('backup_sqlite', str(backup), verbosity=0)
    restored = directory / 'restored.sqlite3'
    with closing(sqlite3.connect(backup)) as source, closing(sqlite3.connect(restored)) as destination:
        source.backup(destination)
        assert destination.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        for table, expected in [('accounts_studentprofile', 100), ('academics_score', 1000), ('academics_attendancerecord', 1000)]:
            assert destination.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == expected
    # Reopen the restored snapshot through Django and verify related record reads.
    connection.close()
    connection.settings_dict['NAME'] = str(restored)
    assert Score.objects.select_related('student__user', 'assessment__course').count() == 1000
    assert client.get('/academics/scores/').status_code == 200

    if review_dir:
        review_dir.mkdir(parents=True, exist_ok=True)
        routes.update(record=f'/academics/records/{students[0].pk}/', entry=f'/academics/scores/{assessment.pk}/entry/',
            dashboard='/accounts/home/teacher/', detail=f'/students/{students[0].pk}/')
        responses = {name: client.get(url) for name, url in routes.items()}
        responses['login'] = Client().get('/accounts/login/')
        revision = re.search(r'name="revision" value="([^"]+)"', responses['entry'].content.decode()).group(1)
        invalid = {'revision': revision, 'form-TOTAL_FORMS': '100', 'form-INITIAL_FORMS': '100'}
        for i, student in enumerate(students):
            invalid.update({f'form-{i}-student': str(student.pk), f'form-{i}-value': '-5' if i == 0 else '', f'form-{i}-remarks': ''})
        responses['error'] = client.post(routes['entry'], invalid)
        for name, response in responses.items():
            assert response.status_code == 200, name
            html = response.content.decode()
            for css, media in [('app.css', ''), ('print.css', ' media="print"')]:
                html = html.replace(f'<link rel="stylesheet" href="/static/css/{css}"{media}>',
                    f'<style{media}>{(ROOT / "static/css" / css).read_text()}</style>')
            (review_dir / f'{name}.html').write_text(html, encoding='utf-8')
    connection.close()
    return {'dataset': {'students': 100, 'courses': 5, 'terms': 2, 'enrollments': 1000, 'scores': 1000, 'attendance_records': 1000},
        'environment': {'python': sys.version.split()[0], 'django': django.get_version(), 'database': 'SQLite',
            'method': 'Django test client, teacher role, one warmup and three timed requests; 20 students or 50 academic records/page'},
        'requests': results, 'backup_restore': 'Passed: integrity, counts and restored Django request'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--review-dir', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='srs-benchmark-', dir=ROOT) as scratch:
        report = run(Path(scratch), args.review_dir)
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf-8')
    print(text)
