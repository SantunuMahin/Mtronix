from django.contrib.auth.models import User
from django.test import TestCase

from inventory.models import Inventory
from products.models import Product, ProductGroup
from products.serializers import ProductSerializer


class ProductSerializerTests(TestCase):
    def test_current_stock_is_zero_when_inventory_row_is_missing(self):
        product = Product.objects.create(
            name='Loose Part',
            sku='PART-001',
            purchase_price='1.00',
            selling_price='2.00',
        )
        Inventory.objects.filter(product=product).delete()

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

    def test_product_create_page_creates_product_without_sku(self):
        response = self.client.post(
            '/products/new/',
            {
                'name': 'USB Type-C Cable',
                'sku': '',
                'purchase_price': '2.00',
                'selling_price': '5.00',
                'low_stock_threshold': 5,
            },
        )

        self.assertEqual(response.status_code, 302)
        p1 = Product.objects.get(name='USB Type-C Cable')
        self.assertIsNone(p1.sku)
        self.assertEqual(str(p1), 'USB Type-C Cable')

    def test_multiple_products_without_sku_can_coexist(self):
        p1 = Product.objects.create(name='Item 1', sku='', purchase_price='1.00', selling_price='2.00')
        p2 = Product.objects.create(name='Item 2', sku=None, purchase_price='2.00', selling_price='4.00')
        p3 = Product.objects.create(name='Item 3', sku='   ', purchase_price='3.00', selling_price='6.00')

        self.assertIsNone(p1.sku)
        self.assertIsNone(p2.sku)
        self.assertIsNone(p3.sku)
        self.assertEqual(str(p1), 'Item 1')
        self.assertEqual(str(p2), 'Item 2')
        self.assertEqual(str(p3), 'Item 3')

    def test_product_with_sku_str_representation(self):
        p = Product.objects.create(name='RAM 8GB', sku='RAM-8GB-01', purchase_price='20.00', selling_price='30.00')
        self.assertEqual(p.sku, 'RAM-8GB-01')
        self.assertEqual(str(p), 'RAM 8GB (RAM-8GB-01)')

    def test_product_create_with_group(self):
        grp = ProductGroup.objects.create(name='Electronics', description='Electronic components')
        response = self.client.post(
            '/products/new/',
            {
                'name': 'LED 50W Driver',
                'group': grp.pk,
                'sku': 'DRV-50W',
                'purchase_price': '10.00',
                'selling_price': '15.00',
                'low_stock_threshold': 5,
            },
        )
        self.assertEqual(response.status_code, 302)
        prod = Product.objects.get(name='LED 50W Driver')
        self.assertEqual(prod.group, grp)
        self.assertEqual(str(grp), 'Electronics')

    def test_product_list_filter_by_group(self):
        grp1 = ProductGroup.objects.create(name='Switches')
        grp2 = ProductGroup.objects.create(name='Cables')
        p1 = Product.objects.create(name='Toggle Switch', group=grp1, purchase_price='1.00', selling_price='2.00')
        p2 = Product.objects.create(name='Power Cable', group=grp2, purchase_price='3.00', selling_price='5.00')
        p3 = Product.objects.create(name='Loose Screw', group=None, purchase_price='0.10', selling_price='0.50')

        # Filter by grp1
        res1 = self.client.get(f'/products/?group={grp1.pk}')
        self.assertContains(res1, 'Toggle Switch')
        self.assertNotContains(res1, 'Power Cable')
        self.assertNotContains(res1, 'Loose Screw')

        # Filter by unassigned
        res_none = self.client.get('/products/?group=none')
        self.assertContains(res_none, 'Loose Screw')
        self.assertNotContains(res_none, 'Toggle Switch')
        self.assertNotContains(res_none, 'Power Cable')

    def test_group_crud_pages(self):
        # Group List
        res_list = self.client.get('/products/groups/')
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, 'Product Groups')

        # Group Create
        res_create = self.client.post(
            '/products/groups/new/',
            {'name': 'Sensors', 'description': 'All types of sensors'},
        )
        self.assertEqual(res_create.status_code, 302)
        grp = ProductGroup.objects.get(name='Sensors')
        self.assertEqual(grp.description, 'All types of sensors')

        # Group Update
        res_update = self.client.post(
            f'/products/groups/{grp.pk}/edit/',
            {'name': 'Sensors & Modules', 'description': 'Updated description'},
        )
        self.assertEqual(res_update.status_code, 302)
        grp.refresh_from_db()
        self.assertEqual(grp.name, 'Sensors & Modules')

        # Group Delete
        res_delete = self.client.post(f'/products/groups/{grp.pk}/delete/')
        self.assertEqual(res_delete.status_code, 302)
        self.assertFalse(ProductGroup.objects.filter(pk=grp.pk).exists())

    def test_product_delete_view(self):
        p = Product.objects.create(name='Obsolete Item', purchase_price='1.00', selling_price='2.00')
        res = self.client.post(f'/products/{p.pk}/delete/')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=p.pk).exists())
