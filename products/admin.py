from django.contrib import admin

from products.models import Product, ProductGroup


@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_count', 'created_at')
    search_fields = ('name', 'description')

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'sku', 'purchase_price', 'selling_price', 'low_stock_threshold')
    list_filter = ('group',)
    search_fields = ('name', 'sku', 'group__name')
