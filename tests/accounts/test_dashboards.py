from django.test import TestCase
from django.urls import reverse
from tests.academics import test_records
from accounts.models import User
from academics.models import Course, Enrollment, Assessment, Score


class DashboardTests(TestCase):
    setUp = test_records.AcademicRecordsTests.setUp

    def test_each_role_gets_its_own_actions_and_scoped_counts(self):
        private = Course.objects.create(code='ROLE-PRIVATE', title='Unassigned role course')
        Enrollment.objects.create(student=self.student, course=private, term=self.term)
        private_assessment = Assessment.objects.create(course=private, term=self.term, title='Unassigned role assessment', maximum_score=100)
        Score.objects.create(student=self.student, assessment=private_assessment, value=50, updated_by=self.admin)
        self.client.force_login(self.teacher.user)
        teacher = self.client.get(reverse('accounts:teacher_home'))
        self.assertEqual(dict(teacher.context['dashboard_counts'])['Assigned classes'], 1)
        self.assertEqual(dict(teacher.context['dashboard_counts'])['Scores recorded'], 0)
        self.assertContains(teacher, 'View class roster')
        self.assertContains(teacher, 'Enter scores')
        self.assertNotContains(teacher, 'Unassigned role assessment')
        self.assertNotContains(teacher, reverse('accounts:setup'))
        self.client.force_login(self.student.user)
        student = self.client.get(reverse('accounts:student_home'))
        self.assertEqual(dict(student.context['dashboard_counts'])['My courses'], 2)
        self.assertEqual(dict(student.context['dashboard_counts'])['My scores'], 1)
        self.assertContains(student, 'Unassigned role assessment')
        self.assertContains(student, 'My attendance history')
        self.assertNotContains(student, 'Take attendance')
        self.assertNotContains(student, 'Enter scores')
        self.client.force_login(self.admin)
        administrator = self.client.get(reverse('accounts:administrator_home'))
        self.assertEqual(dict(administrator.context['dashboard_counts'])['Scores recorded'], 1)
        self.assertContains(administrator, 'Unassigned role assessment')
        self.assertContains(administrator, reverse('accounts:setup'))

    def test_teacher_actions_and_roster_are_scoped(self):
        other = Course.objects.create(code='UNASSIGNED', title='Private course')
        Enrollment.objects.create(student=self.student, course=other, term=self.term)
        Assessment.objects.create(course=other, term=self.term, title='Private assessment', maximum_score=100, weight=100)
        self.client.force_login(self.teacher.user)
        response = self.client.get(reverse('accounts:teacher_home'))
        self.assertContains(response, f'?assignment={self.assignment.pk}')
        self.assertContains(response, self.assessment.title)
        self.assertNotContains(response, 'Private assessment')
        self.assertNotContains(response, 'Private course')
        self.assertEqual(list(response.context['assignments'])[0].roster_count, 1)

    def test_student_sees_live_scores_and_no_edit_actions(self):
        Score.objects.create(student=self.student, assessment=self.assessment, value=87, updated_by=self.admin)
        self.client.force_login(self.student.user)
        response = self.client.get(reverse('accounts:student_home'))
        self.assertContains(response, '87.00')
        self.assertContains(response, self.course.code)
        self.assertContains(response, reverse('academics:record', args=[self.student.pk]))
        self.assertNotContains(response, reverse('academics:score_entry', args=[self.assessment.pk]))

    def test_setup_links_require_model_permissions(self):
        limited = User.objects.create_user(username='limited-dashboard-admin', role='administrator', is_staff=True)
        self.client.force_login(limited)
        self.assertNotContains(self.client.get(reverse('accounts:administrator_home')), reverse('admin:academics_course_add'))
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:administrator_home'))
        self.assertContains(response, reverse('admin:academics_course_add'))
        self.assertContains(response, reverse('admin:accounts_user_add'))

    def test_administrator_directory_uses_recorded_percentages_and_search(self):
        Score.objects.create(student=self.student, assessment=self.assessment, value=self.assessment.maximum_score / 2, updated_by=self.admin)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:administrator_home'), {'q': self.student.student_number, 'term': self.term.pk})
        row = response.context['directory_page'][0]
        self.assertEqual(row.pk, self.student.pk)
        self.assertAlmostEqual(row.score_mean, 50)
        self.assertIsNone(row.present_rate)
        self.assertEqual(len(row.directory_courses), 1)
        self.assertContains(response, '50.0%')
        self.assertEqual(response.context['directory_page'].paginator.per_page, 5)
        response = self.client.get(reverse('accounts:administrator_home'), {'q': 'NO-SUCH-STUDENT'})
        self.assertEqual(response.context['directory_page'].paginator.count, 0)
        self.assertContains(response, 'No students match these filters.')

    def test_invalid_directory_term_does_not_return_unfiltered_students(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:administrator_home'), {'term': 'invalid'})
        self.assertEqual(response.context['directory_page'].paginator.count, 0)
        self.assertTrue(response.context['directory_form'].errors)

    def test_directory_page_size_is_bounded_and_assets_are_versioned(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:administrator_home'), {'size': '25'})
        self.assertEqual(response.context['directory_page'].paginator.per_page, 25)
        self.assertContains(response, '/static/css/stitch.css?v=')
        self.assertContains(response, '/static/css/app.css?v=')
        response = self.client.get(reverse('accounts:administrator_home'), {'size': '100000'})
        self.assertEqual(response.context['directory_page'].paginator.per_page, 5)
