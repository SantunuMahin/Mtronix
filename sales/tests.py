from django.contrib.auth.models import User
from django.test import TestCase

from inventory.models import Inventory
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
        self.assertEqual(response.url, f'/sales/?receipt={Sale.objects.get().pk}')
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(Inventory.objects.get(product=self.product).quantity, 2)

    def test_sale_list_with_receipt_opens_pdf_in_new_page(self):
        InventoryService.add_stock(self.product, 1)
        sale = InventoryService.create_sale(
            customer_name='Walk-in',
            items=[
                {
                    'product': self.product,
                    'quantity': 1,
                    'unit_price': '2.00',
                }
            ],
        )
        response = self.client.get(f'/sales/?receipt={sale.pk}')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'/sales/{sale.pk}/receipt.pdf')
        self.assertContains(response, 'window.open')
