import calendar
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import viewsets
import pytz

from inventory.forms import StockAdjustmentForm
from inventory.models import Inventory
from inventory.pdf import (
    BD_TZ,
    build_inventory_stock_pdf,
    build_new_products_pdf,
    build_stock_updates_pdf,
)
from inventory.serializers import InventorySerializer
from inventory.services import InventoryService
from products.models import Product
from purchases.models import Purchase
from sales.models import Sale, SaleItem


def _get_date_range_for_period(period):
    now = timezone.now().astimezone(BD_TZ)
    midnight = {'hour': 0, 'minute': 0, 'second': 0, 'microsecond': 0}
    end_of_day = {'hour': 23, 'minute': 59, 'second': 59, 'microsecond': 999999}

    if period == "today":
        start = now.replace(**midnight)
        end = now.replace(**end_of_day)
        label = f"Today ({start.strftime('%b %d, %Y')})"
    elif period == "month":
        start = now.replace(day=1, **midnight)
        last_day = calendar.monthrange(now.year, now.month)[1]
        end = now.replace(day=last_day, **end_of_day)
        label = f"This Month ({start.strftime('%B %Y')})"
    elif period == "year":
        start = now.replace(month=1, day=1, **midnight)
        end = now.replace(month=12, day=31, **end_of_day)
        label = f"This Year ({start.strftime('%Y')})"
    else:
        start = None
        end = None
        label = "All Time"

    return start, end, label


class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Inventory.objects.select_related('product').order_by('product__name')
    serializer_class = InventorySerializer


def dashboard(request):
    inventory = Inventory.objects.select_related('product').order_by('product__name')
    low_stock = inventory.filter(quantity__lte=models.F('product__low_stock_threshold'))
    context = {
        'total_products': Product.objects.count(),
        'current_inventory': inventory,
        'low_stock': low_stock,
        'recent_sales': SaleItem.objects.select_related('product', 'sale').order_by('-sale__sold_at')[:5],
        'recent_purchases': Purchase.objects.select_related('product', 'supplier').order_by('-purchased_at')[:5],
    }
    return render(request, 'inventory/dashboard.html', context)


def inventory_list(request):
    inventory = Inventory.objects.select_related('product').order_by('product__name')
    return render(request, 'inventory/list.html', {'inventory': inventory})


def inventory_add_stock(request, pk):
    inventory = get_object_or_404(Inventory.objects.select_related('product'), pk=pk)
    form = StockAdjustmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        InventoryService.add_stock(inventory.product, form.cleaned_data['quantity'])
        return redirect('inventory:list')

    return render(
        request,
        'inventory/adjust.html',
        {'form': form, 'inventory': inventory, 'title': 'Add Stock', 'action_label': 'Add Stock'},
    )


def inventory_remove_stock(request, pk):
    inventory = get_object_or_404(Inventory.objects.select_related('product'), pk=pk)
    form = StockAdjustmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            InventoryService.remove_stock(inventory.product, form.cleaned_data['quantity'])
            return redirect('inventory:list')
        except ValueError as exc:
            form.add_error('quantity', str(exc))

    return render(
        request,
        'inventory/adjust.html',
        {'form': form, 'inventory': inventory, 'title': 'Remove Stock', 'action_label': 'Remove Stock'},
    )


def inventory_report_pdf(request):
    report_type = request.GET.get('type', 'stock')
    period = request.GET.get('period', 'today' if report_type != 'stock' else 'all')
    start_date, end_date, period_label = _get_date_range_for_period(period)

    if report_type == 'new_products':
        products_qs = Product.objects.select_related('inventory').all()
        if start_date and end_date:
            products_qs = products_qs.filter(created_at__range=(start_date, end_date))
        products_qs = products_qs.order_by('-created_at')

        items = [
            {
                'name': p.name,
                'sku': p.sku,
                'purchase_price': float(p.purchase_price),
                'selling_price': float(p.selling_price),
                'current_stock': p.total_stock,
                'created_at': timezone.localtime(p.created_at, BD_TZ).strftime('%d %b %I:%M %p') if p.created_at else '—',
            }
            for p in products_qs
        ]
        total_units = sum(i['current_stock'] for i in items)
        total_cost = sum(i['purchase_price'] * i['current_stock'] for i in items)
        report_data = {
            'period_label': period_label,
            'generated_at': timezone.now().astimezone(BD_TZ).strftime('%d %b %Y, %I:%M %p'),
            'total_new_products': len(items),
            'total_units': total_units,
            'total_cost': total_cost,
            'products': items,
        }
        pdf_bytes = build_new_products_pdf(report_data)
        filename = f'inventory-new-products-{period}.pdf'

    elif report_type == 'updated_stock':
        inv_qs = Inventory.objects.select_related('product').all()
        if start_date and end_date:
            inv_qs = inv_qs.filter(updated_at__range=(start_date, end_date))
        inv_qs = inv_qs.order_by('-updated_at')

        items = [
            {
                'name': inv.product.name,
                'sku': inv.product.sku,
                'quantity': inv.quantity,
                'low_stock_threshold': inv.product.low_stock_threshold,
                'total_value': float(inv.product.purchase_price * inv.quantity),
                'updated_at': timezone.localtime(inv.updated_at, BD_TZ).strftime('%d %b %I:%M %p') if inv.updated_at else '—',
            }
            for inv in inv_qs
        ]
        total_units = sum(i['quantity'] for i in items)
        total_value = sum(i['total_value'] for i in items)
        report_data = {
            'period_label': period_label,
            'generated_at': timezone.now().astimezone(BD_TZ).strftime('%d %b %Y, %I:%M %p'),
            'total_updated_items': len(items),
            'total_units': total_units,
            'total_value': total_value,
            'items': items,
        }
        pdf_bytes = build_stock_updates_pdf(report_data)
        filename = f'inventory-stock-updates-{period}.pdf'

    else:  # 'stock' or full stock summary
        inv_qs = Inventory.objects.select_related('product').order_by('product__name')
        items = [
            {
                'name': inv.product.name,
                'sku': inv.product.sku,
                'purchase_price': float(inv.product.purchase_price),
                'selling_price': float(inv.product.selling_price),
                'quantity': inv.quantity,
                'low_stock_threshold': inv.product.low_stock_threshold,
                'total_value': float(inv.product.purchase_price * inv.quantity),
            }
            for inv in inv_qs
        ]
        total_units = sum(i['quantity'] for i in items)
        total_value = sum(i['total_value'] for i in items)
        low_stock_count = sum(1 for i in items if i['quantity'] <= i['low_stock_threshold'])
        report_data = {
            'period_label': 'Complete Stock Inventory',
            'generated_at': timezone.now().astimezone(BD_TZ).strftime('%d %b %Y, %I:%M %p'),
            'total_products': len(items),
            'total_units': total_units,
            'total_value': total_value,
            'low_stock_count': low_stock_count,
            'items': items,
        }
        pdf_bytes = build_inventory_stock_pdf(report_data)
        filename = 'inventory-current-stock.pdf'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
