from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from inventory.forms import StockAdjustmentForm
from inventory.models import Inventory
from inventory.serializers import InventorySerializer
from inventory.services import InventoryService
from products.models import Product
from purchases.models import Purchase
from sales.models import Sale, SaleItem


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
