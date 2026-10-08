import secrets

from django.contrib.auth import SESSION_KEY
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AuthenticationTests(TestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)
        self.users = {
            role: User.objects.create_user(username=f'test-{role}', password=self.password, role=role)
            for role in User.Role.values
        }
        self.login_url = reverse('accounts:login')

    def sign_in(self, role=User.Role.STUDENT, **extra):
        return self.client.post(self.login_url, {
            'username': self.users[role].username, 'password': self.password, **extra,
        })

    def test_login_form_has_labels_autocomplete_and_csrf(self):
        response = self.client.get(self.login_url)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'for="id_username"')
        self.assertContains(response, 'for="id_password"')
        self.assertContains(response, 'autocomplete="current-password"')

    def test_each_role_logs_in_and_reaches_its_home(self):
        for role in User.Role.values:
            with self.subTest(role=role):
                self.client.logout()
                response = self.sign_in(role)
                self.assertRedirects(response, reverse(f'accounts:{role}_home'))
                self.assertEqual(int(self.client.session[SESSION_KEY]), self.users[role].pk)

    def test_invalid_and_unknown_credentials_have_same_message(self):
        for username in (self.users[User.Role.STUDENT].username, 'unknown-test-account'):
            with self.subTest(username=username):
                response = self.client.post(self.login_url, {
                    'username': username, 'password': secrets.token_urlsafe(24),
                })
                self.assertContains(response, 'Unable to sign in. Check your username and password.')
                self.assertNotIn(SESSION_KEY, self.client.session)

    def test_blank_fields_have_accessible_errors(self):
        response = self.client.post(self.login_url, {'username': '', 'password': ''})
        self.assertContains(response, 'This field is required.', count=2)
        self.assertContains(response, 'aria-invalid="true"', count=2)
        self.assertContains(response, 'aria-describedby="id_username_errors"')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_inactive_user_cannot_log_in(self):
        user = self.users[User.Role.STUDENT]
        user.is_active = False
        user.save(update_fields=['is_active'])
        response = self.sign_in()
        self.assertContains(response, 'Unable to sign in. Check your username and password.')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_all_home_routes_require_login(self):
        routes = ['home', 'accounts:home'] + [f'accounts:{role}_home' for role in User.Role.values]
        for route in routes:
            with self.subTest(route=route):
                url = reverse(route)
                self.assertRedirects(self.client.get(url), f'{self.login_url}?next={url}', fetch_redirect_response=False)

    def test_roles_cannot_visit_other_role_homes(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            for target_role in User.Role.values:
                with self.subTest(role=role, target_role=target_role):
                    response = self.client.get(reverse(f'accounts:{target_role}_home'))
                    self.assertEqual(response.status_code, 200 if role == target_role else 403)

    def test_home_routes_dispatch_by_role(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            for route in ('home', 'accounts:home'):
                self.assertRedirects(self.client.get(reverse(route)), reverse(f'accounts:{role}_home'))

    def test_safe_next_is_honored_and_external_next_is_rejected(self):
        target = reverse('accounts:student_home')
        self.assertRedirects(self.sign_in(next=target), target)
        self.client.logout()
        self.assertRedirects(self.sign_in(next='https://outside.example/'), target)
        self.client.logout()
        self.assertRedirects(self.sign_in(next='//outside.example/'), target)

    def test_logout_requires_post_and_clears_session(self):
        self.sign_in()
        logout_url = reverse('accounts:logout')
        self.assertEqual(self.client.get(logout_url).status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)
        self.assertRedirects(self.client.post(logout_url), self.login_url)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse('accounts:student_home')).status_code, 302)

    def test_login_and_logout_enforce_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.login_url)
        data = {'username': self.users[User.Role.STUDENT].username, 'password': self.password}
        self.assertEqual(client.post(self.login_url, data).status_code, 403)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.login_url, data, HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertEqual(client.post(reverse('accounts:logout')).status_code, 403)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(reverse('accounts:logout'), HTTP_X_CSRFTOKEN=token).status_code, 302)
