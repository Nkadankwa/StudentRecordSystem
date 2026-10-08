from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.test import Client

from accounts.models import StudentProfile, User
from . import test_records
from academics.models import Course, Enrollment, Assessment, Score, AttendanceRecord, AttendanceSession


class RecordWorkflowTests(TestCase):
    setUp = test_records.AcademicRecordsTests.setUp
    score = test_records.AcademicRecordsTests.score
    attendance = test_records.AcademicRecordsTests.attendance

    def sign_in(self, user=None):
        self.client.force_login(user or self.teacher.user)

    def test_record_writes_require_csrf(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.teacher.user)
        for route in [reverse('academics:score_entry', args=[self.assessment.pk]),
                      reverse('academics:attendance_new')]:
            self.assertEqual(protected.post(route, {}).status_code, 403)
        self.assertFalse(Score.objects.exists())
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_invalid_score_is_associated_with_error_and_preserves_input(self):
        self.sign_in()
        data = self.rows(); data['form-0-value'] = '-5'; data['form-0-remarks'] = 'Keep this note'
        response = self.client.post(reverse('academics:score_entry', args=[self.assessment.pk]), data)
        self.assertContains(response, 'aria-describedby="id_form-0-value_errors"')
        self.assertContains(response, 'id="id_form-0-value_errors"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'Keep this note')
        self.assertFalse(Score.objects.exists())

    def test_record_pagination_preserves_filters_and_full_attendance_totals(self):
        profiles = []
        for index in range(51):
            user = User.objects.create_user(username=f'page-student-{index}')
            profile = StudentProfile.objects.create(user=user, student_number=f'PAGE-{index:03}', date_of_birth=date(2010, 1, 1))
            profiles.append(profile)
        Enrollment.objects.bulk_create([Enrollment(student=s, course=self.course, term=self.term) for s in profiles])
        Score.objects.bulk_create([Score(student=s, assessment=self.assessment, value=50, updated_by=self.admin) for s in profiles])
        AttendanceRecord.objects.bulk_create([AttendanceRecord(student=s, session=self.session, status='present', updated_by=self.admin) for s in profiles])
        self.sign_in()
        filters = {'course': self.course.pk, 'term': self.term.pk}
        scores = self.client.get(reverse('academics:scores'), filters)
        self.assertEqual(len(scores.context['records']), 50)
        self.assertContains(scores, f'course={self.course.pk}&amp;term={self.term.pk}&amp;page=2')
        attendance = self.client.get(reverse('academics:attendance'), {**filters, 'page': 2})
        self.assertEqual(len(attendance.context['records']), 1)
        self.assertEqual(list(attendance.context['totals'])[0]['present'], 51)

    def second_student(self):
        user = User.objects.create_user(username='workflow-second', first_name='Fictional', last_name='Second')
        profile = StudentProfile.objects.create(user=user, student_number='Z-SECOND', date_of_birth=date(2005,1,1))
        Enrollment.objects.create(student=profile, course=self.course, term=self.term)
        return profile

    def rows(self, attendance=False, students=None, session=None):
        students = students or [self.student]
        data = {'form-TOTAL_FORMS': str(len(students)), 'form-INITIAL_FORMS': str(len(students))}
        for index, student in enumerate(students):
            data[f'form-{index}-student'] = str(student.pk)
            data[f'form-{index}-remarks'] = ''
            data[f'form-{index}-status' if attendance else f'form-{index}-value'] = 'present' if attendance else '90'
        if attendance:
            data.update(assignment=self.assignment.pk, date=str(session.date) if session else '2030-03-01',
                        lesson_label=session.lesson_label if session else 'Workflow lesson')
        route = reverse('academics:attendance_entry', args=[session.pk]) if session else (reverse('academics:attendance_new') if attendance else reverse('academics:score_entry', args=[self.assessment.pk]))
        response = self.client.get(route, {'assignment': self.assignment.pk} if attendance else {})
        data['revision'] = response.context['revision']
        return data

    def other_course_score(self):
        other = Course.objects.create(code='PRIVATE', title='Unassigned course')
        Enrollment.objects.create(student=self.student, course=other, term=self.term)
        assessment = Assessment.objects.create(course=other, term=self.term, title='Private assessment', maximum_score=100, weight=100)
        Score.objects.create(student=self.student, assessment=assessment, value=50, updated_by=self.admin)
        return assessment

    def test_score_views_are_scoped_by_student_and_course_term(self):
        self.score().save()
        other = self.other_course_score()
        self.sign_in()
        response = self.client.get(reverse('academics:scores'))
        self.assertContains(response, self.assessment.title)
        self.assertNotContains(response, other.title)
        self.assertEqual(self.client.get(reverse('academics:score_entry', args=[other.pk])).status_code, 403)
        self.sign_in(self.student.user)
        self.assertContains(self.client.get(reverse('academics:scores')), other.title)
        self.assertEqual(self.client.get(reverse('academics:score_entry', args=[self.assessment.pk])).status_code, 403)

    def test_students_cannot_view_another_students_records(self):
        second = self.second_student()
        Score.objects.create(student=second, assessment=self.assessment, value=50, updated_by=self.admin)
        self.sign_in(self.student.user)
        self.assertNotContains(self.client.get(reverse('academics:scores')), second.student_number)
        self.assertEqual(self.client.get(reverse('academics:record', args=[second.pk])).status_code, 403)

    def test_score_save_records_request_actor(self):
        self.sign_in()
        data = self.rows()
        data['updated_by'] = self.admin.pk
        self.assertEqual(self.client.post(reverse('academics:score_entry', args=[self.assessment.pk]), data).status_code, 302)
        self.assertEqual(Score.objects.get().updated_by, self.teacher.user)
        self.assertEqual(Score.objects.get().value, Decimal('90'))

    def test_invalid_second_score_rolls_back_first_update(self):
        self.score().save()
        second = self.second_student()
        self.sign_in()
        data = self.rows(students=[self.student, second])
        data['form-1-value'] = '101'
        response = self.client.post(reverse('academics:score_entry', args=[self.assessment.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Score must not exceed')
        self.assertEqual(Score.objects.get(student=self.student).value, Decimal('75'))
        self.assertFalse(Score.objects.filter(student=second).exists())

    def test_tampered_student_or_missing_roster_is_rejected(self):
        second = self.second_student()
        self.sign_in()
        data = self.rows()
        response = self.client.post(reverse('academics:score_entry', args=[self.assessment.pk]), data)
        self.assertContains(response, 'roster changed')
        self.assertFalse(Score.objects.exists())
        data = self.rows(students=[self.student, second])
        data['form-1-student'] = str(self.student.pk)
        self.assertContains(self.client.post(reverse('academics:score_entry', args=[self.assessment.pk]), data), 'roster changed')
        self.assertFalse(Score.objects.exists())

    def test_blank_scores_leave_existing_values_unchanged(self):
        self.score().save()
        self.sign_in()
        data = self.rows(); data['form-0-value'] = ''
        self.client.post(reverse('academics:score_entry', args=[self.assessment.pk]), data)
        self.assertEqual(Score.objects.get().value, Decimal('75'))

    def test_score_filters_reject_unassigned_course(self):
        other = self.other_course_score()
        self.sign_in()
        response = self.client.get(reverse('academics:scores'), {'course': other.course_id})
        self.assertTrue(response.context['filter_form'].errors)
        self.assertFalse(response.context['records'].exists())

    def test_empty_record_pages(self):
        self.sign_in(self.student.user)
        self.assertContains(self.client.get(reverse('academics:scores')), 'No scores')
        self.assertContains(self.client.get(reverse('academics:attendance')), 'No attendance records')

    def test_attendance_create_and_update_has_attribution(self):
        self.sign_in()
        response = self.client.post(reverse('academics:attendance_new'), self.rows(attendance=True))
        self.assertEqual(response.status_code, 302)
        record = AttendanceRecord.objects.get()
        self.assertEqual(record.updated_by, self.teacher.user)
        data = self.rows(attendance=True, session=record.session)
        data['form-0-status'] = 'late'
        self.assertEqual(self.client.post(reverse('academics:attendance_entry', args=[record.session_id]), data).status_code, 302)
        record.refresh_from_db(); self.assertEqual(record.status, 'late')

    def test_attendance_requires_explicit_valid_status(self):
        self.sign_in()
        for status in ('', 'invalid'):
            data = self.rows(attendance=True); data['form-0-status'] = status
            response = self.client.post(reverse('academics:attendance_new'), data)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(AttendanceRecord.objects.exists())
        self.assertEqual(AttendanceSession.objects.count(), 1)

    def test_duplicate_session_does_not_create_records(self):
        self.sign_in()
        data = self.rows(attendance=True); data.update(date='2030-02-01', lesson_label='')
        self.assertEqual(self.client.post(reverse('academics:attendance_new'), data).status_code, 200)
        self.assertEqual(AttendanceSession.objects.count(), 1)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_attendance_unassigned_teacher_and_student_are_blocked(self):
        outsider = User.objects.create_user(username='workflow-outsider', role=User.Role.TEACHER)
        self.sign_in(outsider)
        self.assertEqual(self.client.get(reverse('academics:attendance_new'), {'assignment': self.assignment.pk}).status_code, 403)
        self.assertEqual(self.client.get(reverse('academics:attendance_entry', args=[self.session.pk])).status_code, 403)
        self.sign_in(self.student.user)
        self.assertEqual(self.client.get(reverse('academics:attendance_new')).status_code, 403)

    def test_attendance_totals_and_student_visibility(self):
        self.attendance(status='late').save()
        second = self.second_student()
        AttendanceRecord.objects.create(session=self.session, student=second, status='absent', updated_by=self.admin)
        self.sign_in(self.student.user)
        response = self.client.get(reverse('academics:attendance'))
        self.assertNotContains(response, second.student_number)
        total = list(response.context['totals'])[0]
        self.assertEqual(total['late'], 1); self.assertEqual(total['absent'], 0)

    def test_printable_record_scopes_out_unassigned_courses(self):
        self.score().save(); self.attendance().save()
        other = self.other_course_score()
        self.sign_in()
        response = self.client.get(reverse('academics:record', args=[self.student.pk]))
        self.assertContains(response, self.student.student_number)
        self.assertContains(response, 'Course enrolments')
        self.assertNotContains(response, other.title)
        self.sign_in(self.admin)
        self.assertContains(self.client.get(reverse('academics:record', args=[self.student.pk])), other.title)
        self.assertEqual(self.client.get(reverse('academics:record', args=[999999])).status_code, 404)

    def test_admin_model_access_requires_administrator_role(self):
        teacher_user = self.teacher.user
        teacher_user.is_staff = True; teacher_user.save()
        teacher_user.user_permissions.set(Permission.objects.filter(content_type__app_label='academics'))
        self.sign_in(teacher_user)
        self.assertEqual(self.client.get(reverse('admin:academics_course_add')).status_code, 403)

    def test_profile_admin_validation_rejects_role_mismatch(self):
        self.sign_in(self.admin)
        response = self.client.post(reverse('admin:accounts_studentprofile_add'), {'user': self.teacher.user_id,
            'student_number': 'MISMATCH', 'date_of_birth': '2005-01-01', 'nationality': '', 'gender': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StudentProfile.objects.filter(student_number='MISMATCH').exists())

    def test_anonymous_record_routes_require_login(self):
        for name in ('scores', 'attendance', 'attendance_new'):
            self.assertEqual(self.client.get(reverse('academics:'+name)).status_code, 302)


    def test_bulk_attendance_failure_rolls_back_session_and_records(self):
        from django.core.exceptions import ValidationError
        from academics.services import save_attendance, make_revision
        second = self.second_student()
        with self.assertRaises(ValidationError):
            save_attendance(self.teacher.user, self.assignment, {'date': date(2030,3,1), 'lesson_label': 'Rollback fixture'},
                [{'student': self.student.pk, 'status': 'present', 'remarks': ''},
                 {'student': second.pk, 'status': 'invalid', 'remarks': ''}],
                revision=make_revision(self.teacher.user, assignment=self.assignment))
        self.assertFalse(AttendanceRecord.objects.exists())
        self.assertFalse(AttendanceSession.objects.filter(lesson_label='Rollback fixture').exists())


    def test_stale_score_form_cannot_overwrite_newer_result(self):
        self.score().save(); self.sign_in()
        data = self.rows()
        score = Score.objects.get(); score.value = 95; score.save()
        response = self.client.post(reverse('academics:score_entry', args=[self.assessment.pk]), data)
        self.assertContains(response, 'changed since you opened')
        self.assertEqual(Score.objects.get().value, Decimal('95'))

    def test_tampered_or_missing_revision_is_rejected(self):
        self.sign_in(); data = self.rows(); data['revision'] = 'invalid'
        self.assertContains(self.client.post(reverse('academics:score_entry', args=[self.assessment.pk]), data), 'expired or invalid')
        self.assertFalse(Score.objects.exists())

    def test_stale_attendance_form_cannot_overwrite_newer_status(self):
        record = self.attendance(); record.save(); self.sign_in()
        data = self.rows(attendance=True, session=self.session)
        record.status = 'excused'; record.save()
        response = self.client.post(reverse('academics:attendance_entry', args=[self.session.pk]), data)
        self.assertContains(response, 'changed since you opened')
        self.assertEqual(AttendanceRecord.objects.get().status, 'excused')

    def test_private_pages_are_not_cacheable(self):
        self.sign_in()
        response = self.client.get(reverse('academics:scores'))
        self.assertIn('no-store', response['Cache-Control'])
