from django.contrib import admin
from sales.models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    fields = ('product', 'custom_name', 'quantity', 'unit_price', 'total_amount')
    readonly_fields = ('total_amount',)
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer_name',
        'customer_phone',
        'payment_status',
        'paid_amount',
        'effective_paid_amount',
        'due_amount',
        'total_amount',
        'sold_at',
    )
    list_filter = ('payment_status', 'sold_at')
    search_fields = (
        'customer_name',
        'customer_phone',
        'customer_address',
        'items__product__name',
        'items__custom_name',
    )
    inlines = [SaleItemInline]
