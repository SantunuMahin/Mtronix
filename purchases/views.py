from django.db import transaction
from django.shortcuts import redirect, render
from rest_framework import viewsets

from inventory.services import InventoryService
from purchases.forms import PurchaseForm
from purchases.models import Purchase
from purchases.serializers import PurchaseSerializer


class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.select_related('supplier', 'product').order_by('-purchased_at')
    serializer_class = PurchaseSerializer


def purchase_list(request):
    purchases = Purchase.objects.select_related('supplier', 'product').order_by('-purchased_at')
    return render(request, 'purchases/list.html', {'purchases': purchases})


def purchase_create(request):
    form = PurchaseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                purchase = form.save()
                InventoryService.add_stock(purchase.product, purchase.quantity)
            return redirect('purchases:list')
        except ValueError as exc:
            form.add_error('quantity', str(exc))

    return render(request, 'purchases/form.html', {'form': form, 'title': 'New Purchase'})
