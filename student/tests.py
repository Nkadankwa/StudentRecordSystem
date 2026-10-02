from datetime import date

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse

from accounts.models import StudentProfile, TeacherProfile, User
from accounts.policies import visible_students
from academics.models import AcademicYear, Term, Course, TeachingAssignment, Enrollment


class StudentAccessTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='test-admin', role=User.Role.ADMINISTRATOR)
        self.teacher_user = User.objects.create_user(username='test-teacher', role=User.Role.TEACHER)
        self.teacher = TeacherProfile.objects.create(user=self.teacher_user, employee_number='TEST-T')
        self.student_user = User.objects.create_user(username='test-student', role=User.Role.STUDENT, first_name='Fictional', last_name='Learner')
        self.student = StudentProfile.objects.create(user=self.student_user, student_number='TEST-S', date_of_birth=date(2005, 1, 1))
        self.other_user = User.objects.create_user(username='test-other', role=User.Role.STUDENT, first_name='Other')
        self.other = StudentProfile.objects.create(user=self.other_user, student_number='OTHER-S', date_of_birth=date(2005, 1, 1))
        year = AcademicYear.objects.create(name='Fixture year', start_date=date(2030, 1, 1), end_date=date(2030, 12, 31))
        self.term = Term.objects.create(academic_year=year, name='Fixture term', start_date=year.start_date, end_date=year.end_date)
        self.course = Course.objects.create(code='FIXTURE', title='Fixture course')
        TeachingAssignment.objects.create(teacher=self.teacher, course=self.course, term=self.term)
        self.enrollment = Enrollment.objects.create(student=self.student, course=self.course, term=self.term)

    def detail(self, student):
        return reverse('students:detail', args=[student.pk])

    def test_anonymous_users_redirect_to_login(self):
        for url in (self.detail(self.student), reverse('students:list'), reverse('students:me')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('accounts:login'), response.url)
        self.assertFalse(visible_students(AnonymousUser()).exists())

    def test_student_can_only_view_self(self):
        self.client.force_login(self.student_user)
        self.assertContains(self.client.get(self.detail(self.student)), 'TEST-S')
        self.assertEqual(self.client.get(self.detail(self.other)).status_code, 403)
        self.assertEqual(self.client.get(reverse('students:list')).status_code, 403)
        self.assertRedirects(self.client.get(reverse('students:me')), self.detail(self.student))

    def test_teacher_only_sees_assigned_students(self):
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.get(self.detail(self.student)).status_code, 200)
        self.assertEqual(self.client.get(self.detail(self.other)).status_code, 403)
        response = self.client.get(reverse('students:list'))
        self.assertContains(response, 'TEST-S')
        self.assertNotContains(response, 'OTHER-S')

    def test_matching_course_in_different_term_is_not_visible(self):
        second_term = Term.objects.create(academic_year=self.term.academic_year, name='Other term', start_date=self.term.start_date, end_date=self.term.end_date)
        Enrollment.objects.create(student=self.other, course=self.course, term=second_term)
        self.assertFalse(visible_students(self.teacher_user).filter(pk=self.other.pk).exists())

    def test_withdrawn_student_not_visible_to_teacher(self):
        self.enrollment.status = Enrollment.Status.WITHDRAWN
        self.enrollment.save()
        self.assertFalse(visible_students(self.teacher_user).exists())

    def test_administrator_can_view_all_students(self):
        self.client.force_login(self.admin)
        for student in (self.student, self.other):
            self.assertEqual(self.client.get(self.detail(student)).status_code, 200)
        self.assertEqual(self.client.get(reverse('students:list')).context['page_obj'].paginator.count, 2)

    def test_nonexistent_student_has_safe_404(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('students:detail', args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_search_matches_number_and_name_prefix(self):
        self.client.force_login(self.admin)
        for query in ('test-', 'fiction', 'learn'):
            response = self.client.get(reverse('students:list'), {'q': query})
            self.assertEqual(list(response.context['page_obj']), [self.student])

    def test_teacher_search_does_not_expose_unassigned_student(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('students:list'), {'q': 'OTHER'})
        self.assertContains(response, 'No students match')
        self.assertNotContains(response, 'OTHER-S')

    def test_invalid_search_shows_error_without_results(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('students:list'), {'q': 'x' * 101})
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(response.context['page_obj'].paginator.count, 0)

    def test_pagination_and_invalid_pages(self):
        for i in range(23):
            user = User.objects.create_user(username=f'fixture-page-{i}')
            StudentProfile.objects.create(user=user, student_number=f'PAGE-{i:02}', date_of_birth=date(2005, 1, 1))
        self.client.force_login(self.admin)
        first = self.client.get(reverse('students:list'))
        self.assertEqual(len(first.context['page_obj']), 20)
        self.assertEqual(len(self.client.get(reverse('students:list'), {'page': 2}).context['page_obj']), 5)
        self.assertEqual(self.client.get(reverse('students:list'), {'page': 'bad'}).status_code, 200)
        self.assertEqual(self.client.get(reverse('students:list'), {'page': 999}).context['page_obj'].number, 2)

    def test_private_login_fields_are_not_displayed(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.detail(self.student))
        self.assertNotContains(response, self.student_user.password)
        self.assertNotContains(response, 'last_login')
