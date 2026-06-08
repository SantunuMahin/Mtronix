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


class InventoryPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inv_user', password='pass')
        self.client.force_login(self.user)

    def test_dashboard_renders(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mtronix Inventory Dashboard')

    def test_inventory_list_renders(self):
        response = self.client.get('/inventory/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inventory')


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
