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

    def test_sale_create_with_phone_address_and_payment_status(self):
        InventoryService.add_stock(self.product, 5)
        response = self.client.post(
            '/sales/new/',
            {
                'customer_name': 'Rahim Uddin',
                'customer_phone': '01711223344',
                'customer_address': 'Dhanmondi, Dhaka',
                'payment_status': 'UNPAID',
                'items-TOTAL_FORMS': '1',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-product': self.product.pk,
                'items-0-quantity': 3,
                'items-0-unit_price': '2.00',
            },
        )
        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.get(customer_name='Rahim Uddin')
        self.assertEqual(sale.customer_phone, '01711223344')
        self.assertEqual(sale.customer_address, 'Dhanmondi, Dhaka')
        self.assertEqual(sale.payment_status, 'UNPAID')
        self.assertFalse(sale.is_paid)
        self.assertEqual(sale.total_amount, 6.00)

    def test_sale_toggle_payment_status(self):
        InventoryService.add_stock(self.product, 2)
        sale = InventoryService.create_sale(
            customer_name='Karim',
            payment_status='UNPAID',
            items=[{'product': self.product, 'quantity': 1, 'unit_price': '2.00'}],
        )
        self.assertEqual(sale.payment_status, 'UNPAID')

        # Toggle to PAID
        res = self.client.post(f'/sales/{sale.pk}/toggle-status/')
        self.assertEqual(res.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.payment_status, 'PAID')

        # Toggle back to UNPAID
        res2 = self.client.post(f'/sales/{sale.pk}/toggle-status/')
        self.assertEqual(res2.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.payment_status, 'UNPAID')

    def test_sales_list_status_filtering(self):
        InventoryService.add_stock(self.product, 10)
        s_paid = InventoryService.create_sale(
            customer_name='Paid Customer',
            payment_status='PAID',
            items=[{'product': self.product, 'quantity': 1, 'unit_price': '2.00'}],
        )
        s_unpaid = InventoryService.create_sale(
            customer_name='Unpaid Customer',
            payment_status='UNPAID',
            items=[{'product': self.product, 'quantity': 2, 'unit_price': '2.00'}],
        )

        # Filter: paid
        res_paid = self.client.get('/sales/?status=paid')
        self.assertContains(res_paid, 'Paid Customer')
        self.assertNotContains(res_paid, 'Unpaid Customer')

        # Filter: unpaid
        res_unpaid = self.client.get('/sales/?status=unpaid')
        self.assertContains(res_unpaid, 'Unpaid Customer')
        self.assertNotContains(res_unpaid, 'Paid Customer')

    def test_customer_statement_html_view(self):
        InventoryService.add_stock(self.product, 10)
        InventoryService.create_sale(
            customer_name='Sultana',
            customer_phone='01800112233',
            customer_address='Mirpur 10, Dhaka',
            payment_status='UNPAID',
            items=[{'product': self.product, 'quantity': 2, 'unit_price': '2.00'}],
        )
        response = self.client.get('/sales/statement/?customer=Sultana')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sultana')
        self.assertContains(response, '01800112233')
        self.assertContains(response, 'Account Statement')

    def test_customer_statement_pdf_generation(self):
        InventoryService.add_stock(self.product, 10)
        s1 = InventoryService.create_sale(
            customer_name='Sultana',
            customer_phone='01800112233',
            customer_address='Mirpur 10, Dhaka',
            payment_status='PAID',
            items=[{'product': self.product, 'quantity': 1, 'unit_price': '2.00'}],
        )
        s2 = InventoryService.create_sale(
            customer_name='Sultana',
            customer_phone='01800112233',
            customer_address='Mirpur 10, Dhaka',
            payment_status='UNPAID',
            items=[{'product': self.product, 'quantity': 3, 'unit_price': '2.00'}],
        )

        # Download all statement PDF for customer
        response = self.client.get('/sales/statement/pdf/?customer=Sultana')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

        # Download selective statement PDF by IDs
        res_selective = self.client.get(f'/sales/statement/pdf/?ids={s1.pk},{s2.pk}')
        self.assertEqual(res_selective.status_code, 200)
        self.assertEqual(res_selective['Content-Type'], 'application/pdf')
        self.assertTrue(len(res_selective.content) > 0)

    def test_sale_create_with_partial_half_payment(self):
        InventoryService.add_stock(self.product, 10)
        response = self.client.post(
            '/sales/new/',
            {
                'customer_name': 'Hasan Ali',
                'customer_phone': '01999887766',
                'customer_address': 'Farmgate, Dhaka',
                'payment_status': 'PARTIAL',
                'paid_amount': '3.00',  # Out of 6.00 total (half payment)
                'items-TOTAL_FORMS': '1',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-product': self.product.pk,
                'items-0-quantity': 3,
                'items-0-unit_price': '2.00',
            },
        )
        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.get(customer_name='Hasan Ali')
        self.assertEqual(sale.payment_status, 'PARTIAL')
        self.assertTrue(sale.is_partial)
        self.assertFalse(sale.is_paid)
        self.assertFalse(sale.is_unpaid)
        self.assertEqual(sale.total_amount, 6.00)
        self.assertEqual(sale.effective_paid_amount, 3.00)
        self.assertEqual(sale.due_amount, 3.00)

        # Check receipt HTML displays partial payment & balance due
        res_receipt = self.client.get(f'/sales/{sale.pk}/receipt/')
        self.assertEqual(res_receipt.status_code, 200)
        self.assertContains(res_receipt, 'PARTIAL PAYMENT')
        self.assertContains(res_receipt, 'BALANCE DUE')
        self.assertContains(res_receipt, '3.00')

        # Check receipt PDF renders with partial payment
        res_pdf = self.client.get(f'/sales/{sale.pk}/receipt.pdf')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertTrue(len(res_pdf.content) > 0)

    def test_partial_payment_status_filter_in_sales_list(self):
        InventoryService.add_stock(self.product, 20)
        s_paid = InventoryService.create_sale(
            customer_name='Paid Cust',
            payment_status='PAID',
            items=[{'product': self.product, 'quantity': 1, 'unit_price': '2.00'}],
        )
        s_part = InventoryService.create_sale(
            customer_name='Partial Cust',
            payment_status='PARTIAL',
            paid_amount=2.00,
            items=[{'product': self.product, 'quantity': 2, 'unit_price': '2.00'}],
        )
        s_unpaid = InventoryService.create_sale(
            customer_name='Unpaid Cust',
            payment_status='UNPAID',
            items=[{'product': self.product, 'quantity': 1, 'unit_price': '2.00'}],
        )

        res_part = self.client.get('/sales/?status=partial')
        self.assertContains(res_part, 'Partial Cust')
        self.assertNotContains(res_part, 'Paid Cust')
        self.assertNotContains(res_part, 'Unpaid Cust')

    def test_sale_create_with_unknown_custom_product(self):
        # Create a sale with an unlisted / custom product (no product catalog ID)
        response = self.client.post(
            '/sales/new/',
            {
                'customer_name': 'Kamal Hossain',
                'customer_phone': '01811223344',
                'payment_status': 'PAID',
                'items-TOTAL_FORMS': '1',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-product': '',  # No catalog product
                'items-0-custom_name': 'Special Soldering Flux 50g',
                'items-0-quantity': 2,
                'items-0-unit_price': '150.00',
            },
        )
        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.get(customer_name='Kamal Hossain')
        self.assertEqual(sale.total_amount, 300.00)
        self.assertEqual(sale.items.count(), 1)
        item = sale.items.first()
        self.assertIsNone(item.product)
        self.assertEqual(item.custom_name, 'Special Soldering Flux 50g')
        self.assertEqual(item.display_name, 'Special Soldering Flux 50g')
        self.assertEqual(item.total_amount, 300.00)

        # Verify receipt HTML renders custom product
        res_receipt = self.client.get(f'/sales/{sale.pk}/receipt/')
        self.assertEqual(res_receipt.status_code, 200)
        self.assertContains(res_receipt, 'Special Soldering Flux 50g')
        self.assertContains(res_receipt, 'Custom Item')

        # Verify receipt PDF renders custom product
        res_pdf = self.client.get(f'/sales/{sale.pk}/receipt.pdf')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')

        # Verify search in sales list by custom product name
        res_search = self.client.get('/sales/?q=Soldering+Flux')
        self.assertContains(res_search, 'Kamal Hossain')
        self.assertContains(res_search, 'Special Soldering Flux 50g')

    def test_sale_with_mixed_catalog_and_custom_products(self):
        InventoryService.add_stock(self.product, 5)
        response = self.client.post(
            '/sales/new/',
            {
                'customer_name': 'Mixed Buyer',
                'payment_status': 'PAID',
                'items-TOTAL_FORMS': '2',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-product': self.product.pk,
                'items-0-custom_name': '',
                'items-0-quantity': 2,
                'items-0-unit_price': '2.00',
                'items-1-product': '',
                'items-1-custom_name': 'Rare Resistor Pack',
                'items-1-quantity': 1,
                'items-1-unit_price': '25.00',
            },
        )
        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.get(customer_name='Mixed Buyer')
        self.assertEqual(sale.total_amount, 29.00)
        self.assertEqual(sale.items.count(), 2)

        # Inventory for catalog product should be decremented properly
        inv = Inventory.objects.get(product=self.product)
        self.assertEqual(inv.quantity, 3)

    def test_customer_lookup_api_by_name_and_phone(self):
        InventoryService.add_stock(self.product, 20)
        s1 = InventoryService.create_sale(
            customer_name='Mahin Khan',
            customer_phone='01788990011',
            customer_address='Mirpur, Dhaka',
            payment_status='PAID',
            items=[{'product': self.product, 'quantity': 2, 'unit_price': '10.00'}],
        )
        s2 = InventoryService.create_sale(
            customer_name='Mahin Khan',
            customer_phone='01788990011',
            customer_address='Mirpur, Dhaka',
            payment_status='PARTIAL',
            paid_amount='15.00',
            items=[{'product': self.product, 'quantity': 3, 'unit_price': '10.00'}],
        )

        # Lookup by name
        res_name = self.client.get('/sales/customer-lookup/?q=Mahin')
        self.assertEqual(res_name.status_code, 200)
        data = res_name.json()
        self.assertTrue(len(data['results']) >= 1)
        cust = data['results'][0]
        self.assertEqual(cust['customer_name'], 'Mahin Khan')
        self.assertEqual(cust['customer_phone'], '01788990011')
        self.assertEqual(cust['total_orders'], 2)
        self.assertEqual(cust['total_spent'], 50.00)
        self.assertEqual(cust['total_paid'], 35.00)
        self.assertEqual(cust['total_due'], 15.00)
        self.assertEqual(len(cust['recent_sales']), 2)

        # Lookup by phone
        res_phone = self.client.get('/sales/customer-lookup/?q=0178899')
        self.assertEqual(res_phone.status_code, 200)
        phone_data = res_phone.json()
        self.assertTrue(len(phone_data['results']) >= 1)
        self.assertEqual(phone_data['results'][0]['customer_name'], 'Mahin Khan')

        # Lookup with empty query returns empty list
        res_empty = self.client.get('/sales/customer-lookup/?q=')
        self.assertEqual(res_empty.status_code, 200)
        self.assertEqual(res_empty.json()['results'], [])

    def test_sale_create_page_context_contains_customers_catalog(self):
        InventoryService.add_stock(self.product, 5)
        InventoryService.create_sale(
            customer_name='Recurring Buyer',
            customer_phone='01611223344',
            items=[{'product': self.product, 'quantity': 1, 'unit_price': '2.00'}],
        )
        response = self.client.get('/sales/new/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('customers_catalog', response.context)
        self.assertTrue(any(c['customer_name'] == 'Recurring Buyer' for c in response.context['customers_catalog']))
        self.assertContains(response, 'customer-history-box')
        self.assertContains(response, 'cust-name-dropdown')

    def test_returning_customer_previous_orders_in_receipt_html_and_pdf(self):
        InventoryService.add_stock(self.product, 20)
        
        # First order
        s1 = InventoryService.create_sale(
            customer_name='Shakib Al Hasan',
            customer_phone='01777889900',
            payment_status='PARTIAL',
            paid_amount='50.00',
            items=[{'product': self.product, 'quantity': 10, 'unit_price': '10.00'}], # Total 100, Due 50
        )

        # Second (new) order
        s2 = InventoryService.create_sale(
            customer_name='Shakib Al Hasan',
            customer_phone='01777889900',
            payment_status='PAID',
            items=[{'product': self.product, 'quantity': 2, 'unit_price': '10.00'}], # Total 20, Due 0
        )

        # S1 (first order) receipt should have signatures at bottom
        res_s1 = self.client.get(f'/sales/{s1.pk}/receipt/')
        self.assertEqual(res_s1.status_code, 200)
        self.assertContains(res_s1, "Customer's Signature")
        self.assertContains(res_s1, "Authorized Signature")

        # S2 (new second order) receipt should contain returning customer badge and signature options
        res_s2 = self.client.get(f'/sales/{s2.pk}/receipt/')
        self.assertEqual(res_s2.status_code, 200)
        self.assertContains(res_s2, 'Returning Customer (Order #2)')
        self.assertContains(res_s2, "Customer's Signature")
        self.assertContains(res_s2, "Authorized Signature")

        # S2 PDF receipt should also render successfully with signatures
        res_pdf = self.client.get(f'/sales/{s2.pk}/receipt.pdf')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertTrue(len(res_pdf.content) > 1000)

    def test_sale_item_preserves_product_name_on_save(self):
        prod = Product.objects.create(
            name='Display Panel 14 inch',
            sku='PNL-14',
            purchase_price='30.00',
            selling_price='50.00',
        )
        InventoryService.add_stock(prod, 5)
        sale = InventoryService.create_sale(
            customer_name='Display Tech',
            items=[{'product': prod, 'quantity': 1, 'unit_price': '50.00'}],
        )
        item = sale.items.first()
        self.assertEqual(item.custom_name, 'Display Panel 14 inch')
        self.assertEqual(item.display_name, 'Display Panel 14 inch')

        # If product is deleted, display_name still returns original name
        prod.delete()
        item.refresh_from_db()
        self.assertIsNone(item.product)
        self.assertEqual(item.display_name, 'Display Panel 14 inch')

    def test_pos_sale_logs_authenticated_user_in_stock_movement(self):
        from inventory.models import StockMovement
        InventoryService.add_stock(self.product, 10, user=self.user)
        response = self.client.post(
            '/sales/new/',
            {
                'customer_name': 'Walk-in Buyer',
                'items-TOTAL_FORMS': '1',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '1',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-product': self.product.pk,
                'items-0-quantity': 3,
                'items-0-unit_price': '2.00',
            },
        )
        self.assertEqual(response.status_code, 302)
        sm = StockMovement.objects.filter(product=self.product, movement_type=StockMovement.MOVEMENT_SALE).first()
        self.assertIsNotNone(sm)
        self.assertEqual(sm.quantity, -3)
        self.assertEqual(sm.user, self.user)





