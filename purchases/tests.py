from django.contrib.auth.models import User
from django.test import TestCase

from inventory.models import Inventory
from products.models import Product
from purchases.models import Purchase
from suppliers.models import Supplier


class PurchasePageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='purch_user', password='pass', is_superuser=True)
        self.client.force_login(self.user)
        self.product = Product.objects.create(
            name='Adapter',
            sku='ADP-002',
            purchase_price='4.00',
            selling_price='8.00',
        )
        self.supplier = Supplier.objects.create(name='Acme Supply', phone='123456789')

    def test_purchase_list_renders(self):
        response = self.client.get('/purchases/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Purchases')

    def test_purchase_create_page_adds_stock(self):
        response = self.client.post(
            '/purchases/new/',
            {
                'supplier': self.supplier.pk,
                'product': self.product.pk,
                'quantity': 5,
                'unit_price': '4.00',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Purchase.objects.count(), 1)
        self.assertEqual(Inventory.objects.get(product=self.product).quantity, 5)

        from inventory.models import StockMovement
        sm = StockMovement.objects.filter(product=self.product).first()
        self.assertIsNotNone(sm)
        self.assertEqual(sm.movement_type, StockMovement.MOVEMENT_PURCHASE)
        self.assertEqual(sm.quantity, 5)
        self.assertEqual(sm.user, self.user)

    def test_purchase_syncs_product_purchase_price_and_filters(self):
        from decimal import Decimal
        self.client.post(
            '/purchases/new/',
            {
                'supplier': self.supplier.pk,
                'product': self.product.pk,
                'quantity': 3,
                'unit_price': '6.50',
            },
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.purchase_price, Decimal('6.50'))

        res = self.client.get(f'/purchases/?q=Adapter&supplier={self.supplier.pk}')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Adapter')
        self.assertContains(res, '19.50')
