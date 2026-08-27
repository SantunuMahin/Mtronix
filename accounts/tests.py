from django.test import TestCase
from django.contrib.auth.models import User
from accounts.models import UserProfile


class UserProfileSignalTests(TestCase):
    """UserProfile is auto-created when a User is saved."""

    def test_profile_created_on_user_creation(self):
        user = User.objects.create_user(username='alice', password='testpass123')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_profile_default_role_is_storekeeper(self):
        user = User.objects.create_user(username='bob', password='testpass123')
        self.assertEqual(user.profile.role, UserProfile.STOREKEEPER)

    def test_profile_helper_properties(self):
        user = User.objects.create_user(username='carol', password='testpass123')
        user.profile.role = UserProfile.ADMIN
        user.profile.save()
        self.assertTrue(user.profile.is_admin)
        self.assertFalse(user.profile.is_manager)
        self.assertFalse(user.profile.is_storekeeper)

    def test_sales_role_helper_property(self):
        user = User.objects.create_user(username='salesperson', password='testpass123')
        user.profile.role = UserProfile.SALES
        user.profile.save()

        self.assertTrue(user.profile.is_sales)


class LoginViewTests(TestCase):
    """Login / logout flow tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='SecurePass99!',
        )

    def test_login_page_renders(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign In')

    def test_valid_login_redirects_to_dashboard(self):
        response = self.client.post('/accounts/login/', {
            'username': 'testuser',
            'password': 'SecurePass99!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, '/')

    def test_invalid_login_shows_error(self):
        response = self.client.post('/accounts/login/', {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')

    def test_logout_redirects_to_login(self):
        self.client.login(username='testuser', password='SecurePass99!')
        response = self.client.get('/accounts/logout/', follow=True)
        self.assertRedirects(response, '/accounts/login/')


class LoginRequiredMiddlewareTests(TestCase):
    """Unauthenticated users are redirected to login."""

    def test_anonymous_dashboard_redirects_to_login(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_anonymous_sales_redirects_to_login(self):
        response = self.client.get('/sales/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_login_page_is_publicly_accessible(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)

    def test_unknown_app_page_redirects_to_login(self):
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
