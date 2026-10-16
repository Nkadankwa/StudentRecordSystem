"""Seeded role workflows exercised with real passwords and CSRF enforcement."""
from io import StringIO
import os
import secrets
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from academics.models import Assessment, AttendanceSession, TeachingAssignment, Score, AttendanceRecord


@override_settings(DEBUG=False)
class ReleaseAcceptanceTests(TestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(30)
        with override_settings(DEBUG=True), patch.dict(os.environ, {'DEMO_PASSWORD': self.password}):
            call_command('seed_demo', stdout=StringIO())
        self.student = User.objects.get(role='student').student_profile
        self.assessment = Assessment.objects.get()
        self.session = AttendanceSession.objects.get()
        self.assignment = TeachingAssignment.objects.get()

    def client_for(self, role):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse('accounts:login'))
        response = client.post(reverse('accounts:login'), {
            'username': f'demo-srs-{role}', 'password': self.password,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        })
        self.assertRedirects(response, reverse(f'accounts:{role}_home'))
        return client

    def test_all_roles_can_read_print_and_sign_out(self):
        for role in User.Role.values:
            with self.subTest(role=role):
                client = self.client_for(role)
                for route in [reverse('academics:scores'), reverse('academics:attendance'),
                              reverse('students:detail', args=[self.student.pk])]:
                    self.assertEqual(client.get(route).status_code, 200)
                record = client.get(reverse('academics:record', args=[self.student.pk]))
                self.assertContains(record, 'Print record')
                self.assertContains(record, 'css/print.css')
                self.assertEqual(client.get(reverse('academics:record', args=[999999])).status_code, 404)
                if role == User.Role.STUDENT:
                    self.assertEqual(client.get(reverse('students:list')).status_code, 403)
                    self.assertEqual(client.get(reverse('academics:score_entry', args=[self.assessment.pk])).status_code, 403)
                else:
                    self.assertContains(client.get(reverse('students:list'), {'q': 'not-a-student'}), 'No students match')
                client.post(reverse('accounts:logout'), {'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
                self.assertEqual(client.get(reverse('academics:scores')).status_code, 302)

    def test_only_teacher_can_correct_records_with_csrf_and_reason(self):
        for role, value, status in [('teacher', '72.50', 'late'), ('administrator', '91.25', 'excused')]:
            with self.subTest(role=role):
                client = self.client_for(role)
                url = reverse('academics:score_entry', args=[self.assessment.pk])
                response = client.get(url)
                if role == 'administrator':
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(client.post(url, {'csrfmiddlewaretoken': client.cookies['csrftoken'].value}).status_code, 403)
                    attendance_url = reverse('academics:attendance_entry', args=[self.session.pk])
                    self.assertEqual(client.get(attendance_url).status_code, 403)
                    continue
                score_data = {'revision': response.context['revision'], 'form-TOTAL_FORMS': '1',
                    'form-INITIAL_FORMS': '1', 'form-0-student': self.student.pk, 'form-0-value': value,
                    'form-0-remarks': 'Fictional release verification', 'reason': 'Correcting the submitted score after reviewing original assessment evidence.',
                    'csrfmiddlewaretoken': client.cookies['csrftoken'].value}
                self.assertRedirects(client.post(url, score_data), reverse('academics:scores'))
                score = Score.objects.get()
                self.assertEqual(str(score.value), value)
                self.assertEqual(score.updated_by.role, role)
                url = reverse('academics:attendance_entry', args=[self.session.pk])
                response = client.get(url)
                attendance_data = {'revision': response.context['revision'], 'assignment': self.assignment.pk,
                    'date': self.session.date.isoformat(), 'lesson_label': self.session.lesson_label,
                    'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1', 'form-0-student': self.student.pk,
                    'form-0-status': status, 'form-0-remarks': '', 'reason': 'Correcting attendance after checking the signed class register.',
                    'csrfmiddlewaretoken': client.cookies['csrftoken'].value}
                self.assertRedirects(client.post(url, attendance_data), reverse('academics:attendance'))
                record = AttendanceRecord.objects.get()
                self.assertEqual(record.status, status)
                self.assertEqual(record.updated_by.role, role)
