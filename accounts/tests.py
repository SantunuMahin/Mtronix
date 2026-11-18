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

    def test_logout_get_not_allowed(self):
        self.client.login(username='testuser', password='SecurePass99!')
        response = self.client.get('/accounts/logout/')
        self.assertEqual(response.status_code, 405)

    def test_logout_post_redirects_to_login(self):
        self.client.login(username='testuser', password='SecurePass99!')
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertRedirects(response, '/accounts/login/')

    def test_login_open_redirect_blocked(self):
        response = self.client.post('/accounts/login/?next=https://evil.example.com', {
            'username': 'testuser',
            'password': 'SecurePass99!',
        })
        self.assertRedirects(response, '/')


class RBACEnforcementTests(TestCase):
    """Verify RBAC decorators enforce role restrictions on views."""

    def setUp(self):
        self.storekeeper = User.objects.create_user(username='sk', password='pass1234')
        self.sales_user = User.objects.create_user(username='sales', password='pass1234')
        self.sales_user.profile.role = UserProfile.SALES
        self.sales_user.profile.save()
        self.admin_user = User.objects.create_user(username='adm', password='pass1234')
        self.admin_user.profile.role = UserProfile.ADMIN
        self.admin_user.profile.save()
        self.manager_user = User.objects.create_user(username='mgr', password='pass1234')
        self.manager_user.profile.role = UserProfile.MANAGER
        self.manager_user.profile.save()

    def test_storekeeper_denied_sales_list(self):
        self.client.force_login(self.storekeeper)
        response = self.client.get('/sales/')
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Restricted Area', status_code=403)

    def test_storekeeper_denied_sales_api_returns_403_json(self):
        self.client.force_login(self.storekeeper)
        response = self.client.get('/sales/barcode-lookup/?code=123')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['success'], False)

    def test_storekeeper_denied_product_create(self):
        self.client.force_login(self.storekeeper)
        response = self.client.get('/products/new/')
        self.assertEqual(response.status_code, 403)

    def test_sales_user_allowed_sales_list_but_denied_admin_and_purchases(self):
        self.client.force_login(self.sales_user)
        self.assertEqual(self.client.get('/sales/').status_code, 200)
        self.assertEqual(self.client.get('/products/new/').status_code, 403)
        self.assertEqual(self.client.get('/purchases/').status_code, 403)
        self.assertEqual(self.client.get('/suppliers/').status_code, 403)
        self.assertEqual(self.client.get('/accounts/users/').status_code, 403)

    def test_admin_has_full_access_including_sales_and_users(self):
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get('/sales/').status_code, 200)
        self.assertEqual(self.client.get('/products/new/').status_code, 200)
        self.assertEqual(self.client.get('/purchases/').status_code, 200)
        self.assertEqual(self.client.get('/suppliers/').status_code, 200)
        self.assertEqual(self.client.get('/accounts/users/').status_code, 200)

    def test_manager_has_operational_access_but_not_staff_admin(self):
        self.client.force_login(self.manager_user)
        self.assertEqual(self.client.get('/sales/').status_code, 200)
        self.assertEqual(self.client.get('/products/new/').status_code, 200)
        self.assertEqual(self.client.get('/purchases/').status_code, 200)
        self.assertEqual(self.client.get('/accounts/users/').status_code, 403)

    def test_admin_can_create_user_and_change_role(self):
        self.client.force_login(self.admin_user)
        res = self.client.post('/accounts/users/', {
            'username': 'new_seller',
            'full_name': 'New Seller',
            'email': 'seller@example.com',
            'password': 'StrongPassword123!',
            'role': UserProfile.SALES,
        })
        self.assertRedirects(res, '/accounts/users/')
        created = User.objects.get(username='new_seller')
        self.assertEqual(created.profile.role, UserProfile.SALES)

        role_res = self.client.post(f'/accounts/users/{created.pk}/role/', {'role': UserProfile.MANAGER})
        self.assertRedirects(role_res, '/accounts/users/')
        created.profile.refresh_from_db()
        self.assertEqual(created.profile.role, UserProfile.MANAGER)

    def test_dashboard_hides_sales_actions_for_storekeeper(self):
        self.client.force_login(self.storekeeper)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'New Sale (POS)')

        self.client.force_login(self.sales_user)
        response_sales = self.client.get('/')
        self.assertEqual(response_sales.status_code, 200)
        self.assertContains(response_sales, 'New Sale (POS)')

    def test_api_endpoints_require_authentication(self):
        anon_res = self.client.get('/api/products/')
        self.assertIn(anon_res.status_code, (302, 401, 403))

        self.client.force_login(self.sales_user)
        auth_res = self.client.get('/api/products/')
        self.assertEqual(auth_res.status_code, 200)


class OfflineReadinessTests(TestCase):
    """Verify zero external CDN/font URLs and local PWA/SW endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(username='offline_owner', password='pass1234')
        self.user.profile.role = UserProfile.SYSTEMOWNER
        self.user.profile.save()

    def test_service_worker_and_login_have_no_external_cdns(self):
        sw_res = self.client.get('/sw.js')
        self.assertEqual(sw_res.status_code, 200)
        self.assertIn('mtronix-offline', sw_res.content.decode())

        login_res = self.client.get('/accounts/login/')
        self.assertEqual(login_res.status_code, 200)
        self.assertNotIn('fonts.googleapis.com', login_res.content.decode())

    def test_dashboard_uses_local_chartjs_and_no_cdns(self):
        self.client.force_login(self.user)
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('js/chart.umd.min.js', html)
        self.assertNotIn('cdn.jsdelivr.net', html)
        self.assertNotIn('cdnjs.cloudflare.com', html)
        self.assertNotIn('fonts.googleapis.com', html)


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
