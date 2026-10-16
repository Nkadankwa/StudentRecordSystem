import json

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User, WorkspaceLayout


class LayoutTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='layout-admin', role='administrator')
        self.other = User.objects.create_user(username='layout-other', role='administrator')
        self.url = reverse('accounts:save_layout')
        self.payload = {'page': 'administrator_home', 'hidden': ['quick-setup', 'recent-assessments'], 'collapsed': ['enrolled']}
        self.client.force_login(self.admin)

    def save(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type='application/json')

    def test_preferences_persist_per_user_and_page_and_reset(self):
        self.assertEqual(self.save(self.payload).status_code, 200)
        home = self.client.get(reverse('accounts:administrator_home'))
        self.assertEqual(home.context['workspace_layout']['hidden'], ['quick-setup', 'recent-assessments'])
        self.assertEqual(home.context['workspace_layout']['collapsed'], ['enrolled'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('accounts:administrator_home')).context['workspace_layout']['hidden'], [])
        self.save({**self.payload, 'hidden': ['directory']})
        self.assertEqual(WorkspaceLayout.objects.get(user=self.admin).preferences['hidden'], self.payload['hidden'])
        self.client.force_login(self.admin)
        self.save({'page': 'administrator_home', 'hidden': [], 'collapsed': []})
        self.assertEqual(WorkspaceLayout.objects.get(user=self.admin).preferences, {'hidden': [], 'collapsed': []})

    def test_forged_pages_widgets_and_user_fields_are_rejected(self):
        for payload in [[], {'page': []}, {**self.payload, 'hidden': ['<script>']},
                        {**self.payload, 'user': self.other.pk}, {**self.payload, 'collapsed': 'enrolled'}]:
            self.assertEqual(self.save(payload).status_code, 400)
        self.assertEqual(self.save({**self.payload, 'page': 'unknown'}).status_code, 403)
        self.assertFalse(WorkspaceLayout.objects.exists())
        teacher = User.objects.create_user(username='layout-teacher', role='teacher')
        self.client.force_login(teacher)
        self.assertEqual(self.save(self.payload).status_code, 403)
        self.assertEqual(self.save({'page': 'teacher_home', 'hidden': ['assigned-students'], 'collapsed': ['metric-1']}).status_code, 200)

    def test_save_requires_authenticated_post_and_csrf(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        anonymous = Client()
        self.assertEqual(anonymous.post(self.url).status_code, 302)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        self.assertEqual(protected.post(self.url, json.dumps(self.payload), content_type='application/json').status_code, 403)
        self.assertFalse(WorkspaceLayout.objects.exists())

    def test_summary_cards_have_native_collapse_and_layout_widgets(self):
        response = self.client.get(reverse('accounts:administrator_home'))
        self.assertContains(response, '<details open class="layout-metric"', count=4)
        self.assertContains(response, 'data-layout-widget="quick-setup"')
        self.assertContains(response, 'data-layout-widget="recent-assessments"')
