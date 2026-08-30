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


class InventoryPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inv_user', password='pass')
        self.client.force_login(self.user)

    def test_dashboard_renders(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')

    def test_inventory_list_renders(self):
        response = self.client.get('/inventory/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inventory')

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
