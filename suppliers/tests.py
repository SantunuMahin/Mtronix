from django.contrib.auth.models import User
from django.test import TestCase

from suppliers.models import Supplier


class SupplierPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='supp_user', password='pass', is_superuser=True)
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

    def test_supplier_search_and_delete_protection(self):
        from products.models import Product
        from purchases.models import Purchase
        s1 = Supplier.objects.create(name='Alpha Electronics', phone='01711111111')
        s2 = Supplier.objects.create(name='Beta Traders', phone='01722222222')
        prod = Product.objects.create(name='Resistor 10k', sku='RES-10K', selling_price='1.00')
        Purchase.objects.create(supplier=s1, product=prod, quantity=10, unit_price='0.50')

        res = self.client.get('/suppliers/?q=Alpha')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Alpha Electronics')
        self.assertNotContains(res, 'Beta Traders')

        # Protected supplier cannot be deleted
        del_protected = self.client.post(f'/suppliers/{s1.pk}/delete/', follow=True)
        self.assertEqual(del_protected.status_code, 200)
        self.assertTrue(Supplier.objects.filter(pk=s1.pk).exists())
        self.assertContains(del_protected, 'Cannot delete')

        # Unlinked supplier can be deleted
        del_free = self.client.post(f'/suppliers/{s2.pk}/delete/', follow=True)
        self.assertEqual(del_free.status_code, 200)
        self.assertFalse(Supplier.objects.filter(pk=s2.pk).exists())
