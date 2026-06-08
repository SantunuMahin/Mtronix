from django.contrib.auth.models import User
from django.test import TestCase

from suppliers.models import Supplier


class SupplierPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='supp_user', password='pass')
        self.client.force_login(self.user)

    def test_supplier_list_renders(self):
        response = self.client.get('/suppliers/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Suppliers')

    def test_supplier_create_page_creates_supplier(self):
        response = self.client.post(
            '/suppliers/new/',
            {'name': 'Acme Supply', 'phone': '123456789', 'email': '', 'address': ''},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Supplier.objects.filter(name='Acme Supply').exists())
