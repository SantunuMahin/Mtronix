from django.contrib import admin

from products.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'purchase_price', 'selling_price', 'low_stock_threshold')
    search_fields = ('name', 'sku')
