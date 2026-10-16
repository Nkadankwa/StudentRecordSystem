from io import StringIO
import secrets
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase, override_settings
from accounts.models import User, StudentProfile
from academics.models import Score, AttendanceRecord, Course, AcademicYear, Term, Assessment, AttendanceSession


@override_settings(DEBUG=True)
class SampleSQLTests(TransactionTestCase):
    def test_refresh_changes_placeholder_names_without_resetting_accounts_or_records(self):
        call_command('load_sample_sql', stdout=StringIO())
        student = User.objects.get(username='iris.chen')
        student.username = 'sample-srs-student-001'
        student.first_name, student.last_name = 'Sample', 'Student 01'
        student.set_password(secrets.token_urlsafe(24))
        student.save()
        stored_password = student.password
        profile_id = student.student_profile.pk
        call_command('load_sample_sql', refresh_names=True, stdout=StringIO())
        student.refresh_from_db()
        self.assertEqual((student.first_name, student.last_name), ('Iris', 'Chen'))
        self.assertEqual(student.password, stored_password)
        self.assertEqual(student.student_profile.pk, profile_id)
        self.assertEqual(Score.objects.count(), 144)
        self.assertEqual(AttendanceRecord.objects.count(), 288)
        output = StringIO()
        call_command('load_sample_sql', refresh_names=True, stdout=output)
        self.assertIn('Refreshed 0', output.getvalue())

    def test_import_preserves_existing_data_and_rejects_duplicate_run_atomically(self):
        existing = User.objects.create_user(username='existing-sql-user')
        call_command('load_sample_sql', stdout=StringIO())
        self.assertTrue(User.objects.filter(pk=existing.pk, username='existing-sql-user').exists())
        self.assertEqual(StudentProfile.objects.count(), 24)
        self.assertEqual(Score.objects.count(), 144)
        self.assertEqual(AttendanceRecord.objects.count(), 288)
        self.assertFalse(User.objects.get(username='evelyn.hart').has_usable_password())
        self.assertTrue(User.objects.get(username='evelyn.hart').has_perm('academics.add_course'))
        self.assertEqual(Score.objects.first().updated_by.role, 'teacher')
        with self.assertRaises(CommandError):
            call_command('load_sample_sql', stdout=StringIO())
        self.assertEqual(Score.objects.count(), 144)
        self.assertEqual(User.objects.count(), 28)

    def test_refresh_removes_legacy_labels_and_identifiers_without_changing_relationships(self):
        call_command('load_sample_sql', stdout=StringIO())
        student = User.objects.get(username='iris.chen')
        student.username = 'sample-srs-student-001'
        student.set_password(secrets.token_urlsafe(24))
        student.save()
        password = student.password
        profile = student.student_profile
        number = profile.student_number
        profile.student_number = 'SAMPLE-001'; profile.save()
        course = Course.objects.get(code='MTH101')
        course.code = 'SAMPLE-1'; course.save()
        assessment = Assessment.objects.filter(course=course).order_by('pk').first()
        assessment.title = 'Sample Quiz'; assessment.save()
        session = AttendanceSession.objects.filter(course=course).order_by('pk').first()
        session.lesson_label = 'Sample lesson 1'; session.save()
        year = AcademicYear.objects.get()
        year.name = f'SAMPLE {year.start_date.year}'; year.save()
        term = Term.objects.get(); term.name = 'Sample term'; term.save()
        ids = list(Score.objects.values_list('pk', 'student_id', 'assessment_id'))
        call_command('load_sample_sql', refresh_data=True, stdout=StringIO())
        student.refresh_from_db(); profile.refresh_from_db(); course.refresh_from_db()
        assessment.refresh_from_db(); session.refresh_from_db(); year.refresh_from_db(); term.refresh_from_db()
        self.assertEqual(student.username, 'iris.chen')
        self.assertEqual(student.password, password)
        self.assertEqual(profile.student_number, number)
        self.assertEqual(course.code, 'MTH101')
        self.assertEqual(assessment.title, 'Linear equations quiz')
        self.assertEqual(session.lesson_label, 'Quadratic functions')
        self.assertNotIn('Sample', term.name)
        self.assertNotIn('SAMPLE', year.name)
        self.assertEqual(list(Score.objects.values_list('pk', 'student_id', 'assessment_id')), ids)
        self.assertEqual(AttendanceRecord.objects.count(), 288)

    @override_settings(DEBUG=False)
    def test_production_import_is_rejected(self):
        with self.assertRaises(CommandError):
            call_command('load_sample_sql', stdout=StringIO())
