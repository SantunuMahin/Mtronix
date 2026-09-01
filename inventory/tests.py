from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from inventory.models import Inventory
from inventory.services import InventoryService
from products.models import Product
from purchases.models import Purchase
from purchases.serializers import PurchaseSerializer
from sales.models import Sale, SaleItem
from sales.serializers import SaleSerializer
from suppliers.models import Supplier


class InventoryServiceTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='USB Cable',
            sku='USB-001',
            purchase_price='2.50',
            selling_price='5.00',
        )

    def test_product_creation_creates_inventory(self):
        self.assertEqual(self.product.inventory.quantity, 0)

    def test_add_stock_increases_inventory(self):
        InventoryService.add_stock(self.product, 10)

        self.assertEqual(Inventory.objects.get(product=self.product).quantity, 10)

    def test_remove_stock_deducts_inventory(self):
        InventoryService.add_stock(self.product, 10)
        InventoryService.remove_stock(self.product, 4)

        self.assertEqual(Inventory.objects.get(product=self.product).quantity, 6)

    def test_remove_stock_rejects_overselling(self):
        with self.assertRaises(ValueError):
            InventoryService.remove_stock(self.product, 1)

    def test_create_purchase_records_purchase_and_adds_stock(self):
        supplier = Supplier.objects.create(name='Local Supplier', phone='123456789')

        purchase = InventoryService.create_purchase(
            supplier=supplier,
            product=self.product,
            quantity=3,
            unit_price='2.50',
        )

        self.assertEqual(Purchase.objects.get(pk=purchase.pk).quantity, 3)
        self.assertEqual(Inventory.objects.get(product=self.product).quantity, 3)

    def test_create_sale_records_items_and_removes_stock(self):
        InventoryService.add_stock(self.product, 5)

        sale = InventoryService.create_sale(
            customer_name='Walk-in',
            items=[
                {
                    'product': self.product,
                    'quantity': 2,
                    'unit_price': '5.00',
                }
            ],
        )

        self.assertEqual(SaleItem.objects.get(sale=sale).quantity, 2)
        self.assertEqual(Inventory.objects.get(product=self.product).quantity, 3)

    def test_create_sale_rolls_back_when_stock_is_short(self):
        with self.assertRaises(ValueError):
            InventoryService.create_sale(
                items=[
                    {
                        'product': self.product,
                        'quantity': 2,
                        'unit_price': '5.00',
                    }
                ],
            )

        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)


    def test_stock_movement_logged_on_add_and_remove(self):
        InventoryService.add_stock(self.product, 20, reason='Supplier Shipment', notes='Batch #881')
        self.assertEqual(self.product.stock_movements.count(), 1)
        m = self.product.stock_movements.first()
        self.assertEqual(m.movement_type, 'ADD')
        self.assertEqual(m.quantity, 20)
        self.assertEqual(m.previous_quantity, 0)
        self.assertEqual(m.new_quantity, 20)
        self.assertEqual(m.reason, 'Supplier Shipment')
        self.assertEqual(m.notes, 'Batch #881')

        InventoryService.remove_stock(self.product, 5, reason='Damaged item', notes='Cracked casing')
        self.assertEqual(self.product.stock_movements.count(), 2)
        m2 = self.product.stock_movements.first()
        self.assertEqual(m2.movement_type, 'REMOVE')
        self.assertEqual(m2.quantity, -5)
        self.assertEqual(m2.previous_quantity, 20)
        self.assertEqual(m2.new_quantity, 15)

    def test_set_stock_logs_correction(self):
        InventoryService.add_stock(self.product, 10)
        inv = InventoryService.set_stock(self.product, 25, reason='Physical audit count')
        self.assertEqual(inv.quantity, 25)
        self.assertEqual(Inventory.objects.get(product=self.product).quantity, 25)
        m = self.product.stock_movements.first()
        self.assertEqual(m.movement_type, 'CORRECTION')
        self.assertEqual(m.quantity, 15)
        self.assertEqual(m.previous_quantity, 10)
        self.assertEqual(m.new_quantity, 25)


class InventoryPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inv_user', password='pass')
        self.client.force_login(self.user)
        self.product = Product.objects.create(
            name='12V 100W Driver',
            sku='DRV-100',
            purchase_price='200.00',
            selling_price='350.00',
            low_stock_threshold=5,
        )

    def test_dashboard_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')

    def test_inventory_list_renders_and_filters(self):
        response = self.client.get('/inventory/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inventory & Stock Control')
        self.assertContains(response, '12V 100W Driver')

        # Test search query
        resp_search = self.client.get('/inventory/?q=DRV-100')
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, '12V 100W Driver')

        # Test status filter out of stock
        resp_out = self.client.get('/inventory/?status=out')
        self.assertEqual(resp_out.status_code, 200)
        self.assertContains(resp_out, '12V 100W Driver')

    def test_inventory_logs_view_renders(self):
        InventoryService.add_stock(self.product, 15, user=self.user, reason='Initial stock')
        response = self.client.get('/inventory/logs/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stock Movement Audit Logs')
        self.assertContains(response, 'Initial stock')

    def test_inventory_add_stock_view_get_and_post(self):
        inv = self.product.inventory
        get_resp = self.client.get(f'/inventory/{inv.pk}/add/')
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Add Stock')

        post_resp = self.client.post(
            f'/inventory/{inv.pk}/add/',
            {'quantity': 10, 'reason': 'Supplier delivery', 'notes': 'Invoice #999'}
        )
        self.assertEqual(post_resp.status_code, 302)
        inv.refresh_from_db()
        self.assertEqual(inv.quantity, 10)

    def test_inventory_remove_stock_view_get_and_post(self):
        inv = self.product.inventory
        InventoryService.add_stock(self.product, 20)
        get_resp = self.client.get(f'/inventory/{inv.pk}/remove/')
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Deduct Stock')

        post_resp = self.client.post(
            f'/inventory/{inv.pk}/remove/',
            {'quantity': 5, 'reason': 'Damaged unit', 'notes': 'Burnt resistor'}
        )
        self.assertEqual(post_resp.status_code, 302)
        inv.refresh_from_db()
        self.assertEqual(inv.quantity, 15)

    def test_inventory_stock_report_pdf_renders(self):
        response = self.client.get('/inventory/report/pdf/?type=stock')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

    def test_inventory_new_products_report_pdf_renders(self):
        response = self.client.get('/inventory/report/pdf/?type=new_products&period=today')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

    def test_inventory_updated_stock_report_pdf_renders(self):
        response = self.client.get('/inventory/report/pdf/?type=updated_stock&period=today')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)


class StockMovementSerializerTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Adapter',
            sku='ADP-001',
            purchase_price='4.00',
            selling_price='8.00',
        )
        self.supplier = Supplier.objects.create(name='Acme Supply', phone='123456789')

    def test_purchase_create_adds_stock(self):
        serializer = PurchaseSerializer(
            data={
                'supplier': self.supplier.id,
                'product': self.product.id,
                'quantity': 7,
                'unit_price': '4.00',
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(Purchase.objects.count(), 1)
        self.assertEqual(Inventory.objects.get(product=self.product).quantity, 7)

    def test_purchase_rejects_zero_quantity_without_creating_record(self):
        serializer = PurchaseSerializer(
            data={
                'supplier': self.supplier.id,
                'product': self.product.id,
                'quantity': 0,
                'unit_price': '4.00',
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(Purchase.objects.count(), 0)

    def test_sale_create_removes_stock(self):
        InventoryService.add_stock(self.product, 7)
        serializer = SaleSerializer(
            data={
                'customer_name': 'Walk-in',
                'items': [
                    {
                        'product': self.product.id,
                        'quantity': 3,
                        'unit_price': '8.00',
                    }
                ]
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(Inventory.objects.get(product=self.product).quantity, 4)

    def test_sale_create_rejects_out_of_stock_without_creating_record(self):
        serializer = SaleSerializer(
            data={
                'items': [
                    {
                        'product': self.product.id,
                        'quantity': 3,
                        'unit_price': '8.00',
                    }
                ]
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(ValidationError):
            serializer.save()

        self.assertEqual(Sale.objects.count(), 0)
