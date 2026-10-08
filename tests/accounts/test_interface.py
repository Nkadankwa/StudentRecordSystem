from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.views.defaults import server_error

from accounts.models import User


@override_settings(DEBUG=False)
class InterfaceTests(TestCase):
    def test_navigation_is_scoped_to_each_role(self):
        for role in User.Role.values:
            user = User.objects.create_user(username=f'interface-{role}', role=role)
            self.client.force_login(user)
            response = self.client.get(reverse(f'accounts:{role}_home'))
            self.assertTemplateUsed(response, f'accounts/{role}_home.html')
            self.assertTemplateUsed(response, 'base.html')
            self.assertContains(response, f'href="{reverse(f"accounts:{role}_home")}"')
            for other_role in User.Role.values:
                if other_role != role:
                    self.assertNotContains(response, f'href="{reverse(f"accounts:{other_role}_home")}"')
            self.assertNotContains(response, f'href="{reverse("admin:index")}"')
            self.assertContains(response, 'Skip to content')
            self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_admin_link_requires_administrator_role_and_staff_flag(self):
        user = User.objects.create_user(username='staff-admin', role=User.Role.ADMINISTRATOR, is_staff=True)
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('accounts:administrator_home')), f'href="{reverse("admin:index")}"')
        user.role = User.Role.TEACHER
        user.save(update_fields=['role'])
        self.assertNotContains(self.client.get(reverse('accounts:teacher_home')), f'href="{reverse("admin:index")}"')

    def test_anonymous_navigation_has_no_role_links(self):
        response = self.client.get(reverse('accounts:login'))
        for role in User.Role.values:
            self.assertNotContains(response, f'href="{reverse(f"accounts:{role}_home")}"')

    def test_custom_forbidden_page(self):
        user = User.objects.create_user(username='student-interface', role=User.Role.STUDENT)
        self.client.force_login(user)
        response = self.client.get(reverse('accounts:teacher_home'))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')
        self.assertContains(response, 'Access denied', status_code=403)

    def test_custom_not_found_page(self):
        response = self.client.get('/nonexistent-test-page/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Page not found', status_code=404)
        self.assertNotContains(response, 'nonexistent-test-page', status_code=404)

    def test_server_error_renders_without_request_context(self):
        response = server_error(RequestFactory().get('/'))
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, 'Something went wrong', status_code=500)
        self.assertNotContains(response, 'Traceback', status_code=500)
