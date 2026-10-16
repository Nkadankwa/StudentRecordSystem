from django.test import TestCase
from django.urls import reverse
from tests.academics import test_records
from accounts.models import User, TeacherProfile
from academics.models import TeachingAssignment, Course, Enrollment


class WorkspaceTests(TestCase):
    setUp = test_records.AcademicRecordsTests.setUp

    def test_teacher_assignment_roster_excludes_other_teachers(self):
        other = TeacherProfile.objects.create(user=User.objects.create_user(username='other-workspace-teacher', role='teacher'), employee_number='OTHER-WORKSPACE')
        foreign = TeachingAssignment.objects.create(teacher=other, course=self.course, term=self.term, section='Other')
        self.client.force_login(self.teacher.user)
        response = self.client.get(reverse('academics:assignments'))
        self.assertContains(response, reverse('academics:roster', args=[self.assignment.pk]))
        self.assertNotContains(response, reverse('academics:roster', args=[foreign.pk]))
        self.assertEqual(self.client.get(reverse('academics:roster', args=[foreign.pk])).status_code, 403)
        self.assertContains(self.client.get(reverse('academics:roster', args=[self.assignment.pk])), self.student.student_number)

    def test_catalog_and_setup_are_administrator_only(self):
        for user in [self.student.user, self.teacher.user]:
            self.client.force_login(user)
            for route in ['academics:catalog', 'accounts:setup']:
                self.assertEqual(self.client.get(reverse(route)).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('academics:catalog')), self.course.code)
        self.assertContains(self.client.get(reverse('accounts:setup')), reverse('admin:academics_course_add'))

    def test_profile_course_summary_remains_scoped(self):
        private = Course.objects.create(code='PRIVATE-WORKSPACE', title='Private course')
        Enrollment.objects.create(student=self.student, course=private, term=self.term)
        self.client.force_login(self.teacher.user)
        response = self.client.get(reverse('students:detail', args=[self.student.pk]))
        self.assertNotContains(response, 'PRIVATE-WORKSPACE')
        self.assertEqual(dict(response.context['profile_counts'])['Enrolled courses'], 1)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('students:detail', args=[self.student.pk])), 'PRIVATE-WORKSPACE')

    def test_attendance_radios_have_no_default_and_show_validation_associations(self):
        self.client.force_login(self.teacher.user)
        route = reverse('academics:attendance_new')
        response = self.client.get(route, {'assignment': self.assignment.pk})
        self.assertContains(response, 'type="radio"', count=4)
        self.assertNotContains(response, 'checked')
        data = {'assignment': self.assignment.pk, 'date': '2030-03-01', 'lesson_label': 'Radio verification',
            'revision': response.context['revision'], 'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 1,
            'form-0-student': self.student.pk, 'form-0-status': '', 'form-0-remarks': ''}
        invalid = self.client.post(route, data)
        self.assertContains(invalid, 'id="id_form-0-status_errors"')
        self.assertContains(invalid, 'aria-describedby="id_form-0-status_errors"')
