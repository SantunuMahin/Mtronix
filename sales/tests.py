from django.contrib.auth.models import User
from django.test import TestCase

from inventory.services import InventoryService
from products.models import Product
from sales.models import Sale, SaleItem


class SalePageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sales_user', password='pass')
        self.client.force_login(self.user)
        self.product = Product.objects.create(
            name='Cable Tie',
            sku='TIE-001',
            purchase_price='1.00',
            selling_price='2.00',
        )

    def test_sale_list_renders(self):
        response = self.client.get('/sales/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sales')

    def test_sale_create_page_removes_stock(self):
        InventoryService.add_stock(self.product, 4)
        response = self.client.post(
            '/sales/new/',
            {
                'customer_name': 'Walk-in',
                'items-TOTAL_FORMS': '1',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-product': self.product.pk,
                'items-0-quantity': 2,
                'items-0-unit_price': '2.00',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 1)
        self.product.inventory.refresh_from_db()
        self.assertEqual(self.product.inventory.quantity, 2)
