from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import StudentProfile, TeacherProfile, User
from .models import (AcademicYear, Term, Course, TeachingAssignment, Enrollment,
                     Assessment, Score, AttendanceSession, AttendanceRecord)


class AcademicRecordsTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(name='Fixture year', start_date=date(2030, 1, 1), end_date=date(2030, 12, 31))
        self.term = Term.objects.create(academic_year=self.year, name='Fixture term', start_date=date(2030, 1, 1), end_date=date(2030, 6, 30))
        self.course = Course.objects.create(code='TEST', title='Fixture course')
        self.admin = User.objects.create_superuser(username='fixture-admin', password=None)
        teacher_user = User.objects.create_user(username='fixture-teacher', role=User.Role.TEACHER)
        self.teacher = TeacherProfile.objects.create(user=teacher_user, employee_number='T-FIXTURE')
        student_user = User.objects.create_user(username='fixture-student', role=User.Role.STUDENT)
        self.student = StudentProfile.objects.create(user=student_user, student_number='S-FIXTURE', date_of_birth=date(2010, 1, 1))
        self.assignment = TeachingAssignment.objects.create(teacher=self.teacher, course=self.course, term=self.term)
        self.enrollment = Enrollment.objects.create(student=self.student, course=self.course, term=self.term)
        self.assessment = Assessment.objects.create(course=self.course, term=self.term, title='Fixture assessment', maximum_score=Decimal('100'), weight=Decimal('25'))
        self.session = AttendanceSession.objects.create(course=self.course, term=self.term, teacher=self.teacher, date=date(2030, 2, 1))

    def score(self, **changes):
        values = dict(assessment=self.assessment, student=self.student, value=Decimal('75'), updated_by=self.teacher.user)
        values.update(changes)
        return Score(**values)

    def attendance(self, **changes):
        values = dict(session=self.session, student=self.student, status=AttendanceRecord.Status.PRESENT, updated_by=self.teacher.user)
        values.update(changes)
        return AttendanceRecord(**values)

    def test_assignment_and_enrollment_duplicates_rejected(self):
        with self.assertRaises(ValidationError):
            TeachingAssignment.objects.create(teacher=self.teacher, course=self.course, term=self.term, section='  ')
        with self.assertRaises(ValidationError):
            Enrollment.objects.create(student=self.student, course=self.course, term=self.term)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.bulk_create([Enrollment(student=self.student, course=self.course, term=self.term)])
        TeachingAssignment.objects.create(teacher=self.teacher, course=self.course, term=self.term, section='Another section')

    def test_assignment_query_identifies_assigned_students(self):
        students = StudentProfile.objects.filter(enrollments__course__teaching_assignments__teacher=self.teacher, enrollments__term=self.term, enrollments__course=self.course).distinct()
        self.assertEqual(list(students), [self.student])

    def test_profiles_must_keep_matching_role(self):
        User.objects.filter(pk=self.teacher.user_id).update(role=User.Role.STUDENT)
        teacher = TeacherProfile.objects.get(pk=self.teacher.pk)
        with self.assertRaises(ValidationError):
            TeachingAssignment(teacher=teacher, course=self.course, term=self.term, section='Invalid').save()
        User.objects.filter(pk=self.student.user_id).update(role=User.Role.TEACHER)
        student = StudentProfile.objects.get(pk=self.student.pk)
        with self.assertRaises(ValidationError):
            Enrollment(student=student, course=self.course, term=self.term).save()

    def test_enrollment_status_constraints(self):
        self.enrollment.status = 'unknown'
        with self.assertRaises(ValidationError):
            self.enrollment.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.filter(pk=self.enrollment.pk).update(status='unknown')

    def test_assessment_limits_and_weights(self):
        for maximum, weight in [(0, 25), (-1, 25), (100, -1), (100, 101)]:
            with self.subTest(maximum=maximum, weight=weight), self.assertRaises(ValidationError):
                Assessment.objects.create(course=self.course, term=self.term, title='Invalid', maximum_score=maximum, weight=weight)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Assessment.objects.filter(pk=self.assessment.pk).update(maximum_score=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Assessment.objects.filter(pk=self.assessment.pk).update(weight=101)

    def test_score_bounds_and_duplicate(self):
        for value in (Decimal('-0.01'), Decimal('100.01')):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.score(value=value).save()
        self.score(value=0).save()
        with self.assertRaises(ValidationError):
            self.score().save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Score.objects.bulk_create([self.score()])
        Score.objects.all().delete()
        self.score(value=100).save()

    def test_scores_require_enrollment(self):
        self.enrollment.delete()
        with self.assertRaises(ValidationError):
            self.score().save()

    def test_withdrawn_students_cannot_receive_new_records(self):
        self.enrollment.status = Enrollment.Status.WITHDRAWN
        self.enrollment.save()
        for record in (self.score(), self.attendance()):
            with self.subTest(record=type(record).__name__), self.assertRaises(ValidationError):
                record.save()

    def test_updater_must_be_admin_or_assigned_teacher(self):
        outsider = User.objects.create_user(username='fixture-outsider', role=User.Role.TEACHER)
        for record in (self.score(updated_by=outsider), self.attendance(updated_by=self.student.user)):
            with self.assertRaises(ValidationError):
                record.save()
        self.score(updated_by=self.admin).save()
        self.attendance(updated_by=self.admin).save()

    def test_updates_record_actor_and_timestamps(self):
        record = self.score()
        record.save()
        created, updated = record.created_at, record.updated_at
        record.value = Decimal('80')
        record.updated_by = self.admin
        with patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(minutes=1)):
            record.save()
        record.refresh_from_db()
        self.assertEqual(record.created_at, created)
        self.assertGreater(record.updated_at, updated)
        self.assertEqual(record.updated_by, self.admin)

    def test_existing_scores_protect_assessment_definition(self):
        self.score().save()
        self.assessment.maximum_score = Decimal('50')
        with self.assertRaises(ValidationError):
            self.assessment.save()
        self.assessment.maximum_score = Decimal('100')
        self.assessment.course = Course.objects.create(code='OTHER', title='Other fixture course')
        with self.assertRaises(ValidationError):
            self.assessment.save()

    def test_session_requires_assignment_and_valid_date(self):
        self.session.date = date(2031, 1, 1)
        with self.assertRaises(ValidationError):
            self.session.save()
        self.session.date = date(2030, 2, 1)
        self.assignment.delete()
        with self.assertRaises(ValidationError):
            self.session.save()

    def test_session_duplicate_and_different_lessons(self):
        with self.assertRaises(ValidationError):
            AttendanceSession.objects.create(course=self.course, term=self.term, teacher=self.teacher, date=self.session.date)
        AttendanceSession.objects.create(course=self.course, term=self.term, teacher=self.teacher, date=self.session.date, lesson_label='Second lesson')

    def test_attendance_statuses_and_duplicates(self):
        for status in AttendanceRecord.Status.values:
            record = self.attendance(status=status)
            record.save()
            record.delete()
        record = self.attendance()
        record.save()
        with self.assertRaises(ValidationError):
            self.attendance().save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttendanceRecord.objects.bulk_create([self.attendance()])
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttendanceRecord.objects.filter(pk=record.pk).update(status='unknown')
        record.status = 'unknown'
        with self.assertRaises(ValidationError):
            record.save()

    def test_attendance_requires_enrollment(self):
        self.enrollment.delete()
        with self.assertRaises(ValidationError):
            self.attendance().save()

    def test_sessions_with_records_cannot_move_course(self):
        self.attendance().save()
        self.session.course = Course.objects.create(code='OTHER', title='Other fixture course')
        TeachingAssignment.objects.create(teacher=self.teacher, course=self.session.course, term=self.term)
        with self.assertRaises(ValidationError):
            self.session.save()

    def test_admin_records_current_actor_and_rejects_invalid_score(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:academics_score_add'), {'assessment': self.assessment.pk, 'student': self.student.pk, 'value': '101', 'remarks': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Score.objects.exists())
        response = self.client.post(reverse('admin:academics_score_add'), {'assessment': self.assessment.pk, 'student': self.student.pk, 'value': '90', 'remarks': '', 'updated_by': self.student.user_id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Score.objects.get().updated_by, self.admin)
        response = self.client.post(reverse('admin:academics_attendancerecord_add'), {'session': self.session.pk, 'student': self.student.pk, 'status': 'present', 'remarks': ''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AttendanceRecord.objects.get().updated_by, self.admin)


    def test_malformed_decimals_raise_validation_errors(self):
        for value in ('not-a-number', Decimal('NaN'), Decimal('Infinity')):
            with self.subTest(value=str(value)), self.assertRaises(ValidationError):
                self.score(value=value).save()
