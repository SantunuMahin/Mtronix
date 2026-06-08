from django.contrib import admin

from purchases.models import Purchase


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('product', 'supplier', 'quantity', 'unit_price', 'purchased_at')
    list_filter = ('supplier', 'purchased_at')
    search_fields = ('product__name', 'product__sku', 'supplier__name')
