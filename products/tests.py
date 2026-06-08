from django.contrib.auth.models import User
from django.test import TestCase

from products.models import Product
from products.serializers import ProductSerializer


class ProductSerializerTests(TestCase):
    def test_current_stock_is_zero_when_inventory_row_is_missing(self):
        product = Product.objects.create(
            name='Loose Part',
            sku='PART-001',
            purchase_price='1.00',
            selling_price='2.00',
        )
        product.inventory.delete()

        self.assertEqual(ProductSerializer(product).data['current_stock'], 0)


class ProductPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='prod_user', password='pass')
        self.client.force_login(self.user)

    def test_product_list_renders(self):
        response = self.client.get('/products/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Products')

    def test_product_create_page_creates_product(self):
        response = self.client.post(
            '/products/new/',
            {
                'name': 'HDMI Cable',
                'sku': 'HDMI-001',
                'purchase_price': '3.00',
                'selling_price': '7.00',
                'low_stock_threshold': 5,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(sku='HDMI-001').exists())
