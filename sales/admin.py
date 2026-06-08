from django.contrib import admin

from sales.models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'total_amount', 'sold_at')
    list_filter = ('sold_at',)
    search_fields = ('customer_name',)
    inlines = [SaleItemInline]
