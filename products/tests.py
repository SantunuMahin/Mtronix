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

    def test_automatic_inventory_creation_on_product_create(self):
        product = Product.objects.create(
            name='Resistor 10k',
            sku='RES-10K',
            purchase_price='0.05',
            selling_price='0.10',
        )
        self.assertTrue(hasattr(product, 'inventory'))
        self.assertEqual(product.inventory.quantity, 0)


class ProductPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='prod_user', password='pass', is_superuser=True)
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

    def test_product_list_search_by_name_and_sku(self):
        p1 = Product.objects.create(name='Arduino Uno R3', sku='MCU-001', purchase_price='5.00', selling_price='8.00')
        p2 = Product.objects.create(name='ESP32 DevKit', sku='MCU-002', purchase_price='4.00', selling_price='7.00')
        p3 = Product.objects.create(name='Breadboard 830', sku='BRD-830', purchase_price='2.00', selling_price='3.50')

        # Search by name
        res_name = self.client.get('/products/?q=Arduino')
        self.assertContains(res_name, 'Arduino Uno R3')
        self.assertNotContains(res_name, 'ESP32 DevKit')
        self.assertNotContains(res_name, 'Breadboard 830')

        # Search by SKU
        res_sku = self.client.get('/products/?q=MCU-002')
        self.assertContains(res_sku, 'ESP32 DevKit')
        self.assertNotContains(res_sku, 'Arduino Uno R3')


class ProductBarcodeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='barcode_user', password='pass', is_superuser=True)
        self.client.force_login(self.user)
        self.group = ProductGroup.objects.create(name='Power Supplies')
        self.product = Product.objects.create(
            name='12V 5A Power Adapter',
            sku='PS12-5A',
            group=self.group,
            purchase_price='8.00',
            selling_price='14.50',
            low_stock_threshold=5,
        )
        self.product.inventory.quantity = 15
        self.product.inventory.save()

    def test_single_barcode_label_view_renders_correctly(self):
        res = self.client.get(f'/products/{self.product.pk}/barcode/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '12V 5A Power Adapter')
        self.assertContains(res, 'PS12-5A')
        self.assertContains(res, '<svg')
        self.assertContains(res, '50mm')
        self.assertContains(res, '30mm')

    def test_single_barcode_label_view_404_for_nonexistent_product(self):
        res = self.client.get('/products/99999/barcode/')
        self.assertEqual(res.status_code, 404)

    def test_single_barcode_generates_identifier_if_sku_is_empty(self):
        p_no_sku = Product.objects.create(
            name='Loose Wire Spool',
            sku='',
            purchase_price='1.00',
            selling_price='2.00',
        )
        res = self.client.get(f'/products/{p_no_sku.pk}/barcode/')
        self.assertEqual(res.status_code, 200)
        p_no_sku.refresh_from_db()
        self.assertTrue(p_no_sku.sku.startswith('MTX-'))
        self.assertContains(res, p_no_sku.sku)
        self.assertContains(res, '<svg')

    def test_batch_barcode_view_renders_all_products(self):
        p2 = Product.objects.create(
            name='USB-C Hub',
            sku='HUB-C01',
            purchase_price='12.00',
            selling_price='22.00',
        )
        res = self.client.get('/products/barcode/batch/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '12V 5A Power Adapter')
        self.assertContains(res, 'USB-C Hub')
        self.assertContains(res, '<svg')
        self.assertContains(res, 'Batch Barcode Label Printing')

    def test_batch_barcode_view_filter_by_group(self):
        other_grp = ProductGroup.objects.create(name='Cables')
        p_cable = Product.objects.create(
            name='Cat6 Patch Cable',
            sku='CBL-CAT6',
            group=other_grp,
            purchase_price='2.00',
            selling_price='4.00',
        )
        res = self.client.get(f'/products/barcode/batch/?group={self.group.pk}')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '12V 5A Power Adapter')
        self.assertNotContains(res, 'Cat6 Patch Cable')

    def test_api_generate_sku(self):
        res = self.client.get('/products/api/generate-sku/?name=Soldering+Iron&group=Tools')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('success'))
        self.assertIn('sku', data)
        self.assertTrue(data['sku'].startswith('TOOL') or data['sku'].startswith('SOLD') or data['sku'].startswith('MTX'))

    def test_api_preview_barcode(self):
        res = self.client.get('/products/api/barcode-preview/?code=PS12-5A')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('success'))
        self.assertIn('<svg', data['svg'])
        self.assertTrue(data['data_uri'].startswith('data:image/svg+xml'))

    def test_api_preview_barcode_empty_code(self):
        res = self.client.get('/products/api/barcode-preview/?code=')
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data.get('success'))

    def test_product_create_page_prefills_sku_from_get_param(self):
        res = self.client.get('/products/new/?sku=SCANNED-9988')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'value="SCANNED-9988"')


class BarcodeGenerationTests(TestCase):
    def test_generate_code128_svg_with_show_text_false(self):
        from products.barcode import generate_code128_svg
        svg = generate_code128_svg('SALE-00030', height=32, show_text=False)
        self.assertIn('<svg', svg)
        self.assertNotIn('<text', svg)

    def test_generate_code128_svg_with_include_text_false(self):
        from products.barcode import generate_code128_svg
        svg = generate_code128_svg('SALE-00030', height=32, include_text=False)
        self.assertIn('<svg', svg)
        self.assertNotIn('<text', svg)

    def test_generate_code128_svg_default_includes_text(self):
        from products.barcode import generate_code128_svg
        svg = generate_code128_svg('SALE-00030', height=32)
        self.assertIn('<svg', svg)
        self.assertIn('<text', svg)
        self.assertIn('SALE-00030', svg)

    def test_generate_code128_data_uri_with_show_text(self):
        from products.barcode import generate_code128_data_uri
        uri = generate_code128_data_uri('MTX-12345', show_text=False)
        self.assertTrue(uri.startswith('data:image/svg+xml;base64,'))

    def test_generate_unique_product_sku(self):
        from products.barcode import generate_unique_product_sku
        sku = generate_unique_product_sku(prefix="MTX")
        self.assertTrue(sku.startswith("MTX-"))
        self.assertEqual(len(sku), 9)  # MTX- + 5 digits


class ProductDeleteProtectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin_prod', password='pass', is_superuser=True)
        self.client.force_login(self.user)

    def test_delete_product_with_purchase_shows_error_instead_of_500(self):
        from suppliers.models import Supplier
        from purchases.models import Purchase
        supplier = Supplier.objects.create(name='Test Supplier', phone='01700000000')
        product = Product.objects.create(
            name='Protected Capacitor',
            sku='CAP-PROT-1',
            purchase_price='5.00',
            selling_price='10.00',
        )
        Purchase.objects.create(supplier=supplier, product=product, quantity=5, unit_price='5.00')
        response = self.client.post(f'/products/{product.pk}/delete/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertContains(response, 'Cannot delete')

