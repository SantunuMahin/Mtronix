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

    def test_sale_list_with_receipt_triggers_direct_print(self):
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
        self.assertContains(response, f'/sales/{sale.pk}/receipt/')
        self.assertContains(response, 'printReceipt')

    def test_sale_receipt_print_view_renders_successfully(self):
        InventoryService.add_stock(self.product, 2)
        sale = InventoryService.create_sale(
            customer_name='Walk-in',
            items=[{'product': self.product, 'quantity': 2, 'unit_price': '2.00'}],
        )
        response = self.client.get(f'/sales/{sale.pk}/receipt/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MTRONIX')
        self.assertContains(response, 'window.print()')

    def test_sale_receipt_pdf_view_renders_successfully(self):
        product_no_sku = Product.objects.create(
            name='No SKU Item',
            sku=None,
            purchase_price='5.00',
            selling_price='10.00',
        )
        InventoryService.add_stock(self.product, 5)
        InventoryService.add_stock(product_no_sku, 5)
        sale = InventoryService.create_sale(
            customer_name='John Doe',
            items=[
                {'product': self.product, 'quantity': 1, 'unit_price': '2.00'},
                {'product': product_no_sku, 'quantity': 2, 'unit_price': '10.00'},
            ],
        )
        response = self.client.get(f'/sales/{sale.pk}/receipt.pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

    def test_sales_report_pdf_view_renders_successfully(self):
        response = self.client.get('/sales/report/pdf/?period=today')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

    def test_sale_search_by_id_and_customer(self):
        InventoryService.add_stock(self.product, 10)
        s1 = InventoryService.create_sale(
            customer_name='Alice Smith',
            items=[{'product': self.product, 'quantity': 1, 'unit_price': '2.00'}],
        )
        s2 = InventoryService.create_sale(
            customer_name='Bob Jones',
            items=[{'product': self.product, 'quantity': 2, 'unit_price': '2.00'}],
        )

        # Search by number id
        res1 = self.client.get(f'/sales/?q={s1.pk}')
        self.assertContains(res1, 'Alice Smith')
        self.assertNotContains(res1, 'Bob Jones')

        # Search by formatted SALE-0000X
        res2 = self.client.get(f'/sales/?q=SALE-{s2.pk:05d}')
        self.assertContains(res2, 'Bob Jones')
        self.assertNotContains(res2, 'Alice Smith')

        # Search by customer name
        res3 = self.client.get('/sales/?q=Alice')
        self.assertContains(res3, 'Alice Smith')
        self.assertNotContains(res3, 'Bob Jones')
