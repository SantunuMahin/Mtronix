from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from rest_framework import mixins, viewsets

from accounts.decorators import inventory_write_required
from accounts.permissions import InventoryWritePermission
from inventory.services import InventoryService
from purchases.forms import PurchaseForm
from purchases.models import Purchase
from purchases.serializers import PurchaseSerializer
from suppliers.models import Supplier


class PurchaseViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Purchase.objects.select_related('supplier', 'product').order_by('-purchased_at')
    serializer_class = PurchaseSerializer
    permission_classes = [InventoryWritePermission]


@inventory_write_required
def purchase_list(request):
    query = request.GET.get('q', '').strip()
    supplier_id = request.GET.get('supplier', '').strip()

    qs = Purchase.objects.select_related('supplier', 'product').order_by('-purchased_at')

    if supplier_id and supplier_id.isdigit():
        qs = qs.filter(supplier_id=int(supplier_id))

    if query:
        qs = qs.filter(
            models.Q(product__name__icontains=query)
            | models.Q(product__sku__icontains=query)
            | models.Q(supplier__name__icontains=query)
        )

    aggregates = qs.aggregate(
        total_units=Coalesce(models.Sum('quantity'), 0),
        total_spend=Coalesce(
            models.Sum(
                models.F('quantity') * models.F('unit_price'),
                output_field=models.DecimalField(max_digits=14, decimal_places=2),
            ),
            Decimal('0.00'),
        ),
    )

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'purchases/list.html',
        {
            'purchases': page_obj.object_list,
            'page_obj': page_obj,
            'query': query,
            'selected_supplier': supplier_id,
            'suppliers': Supplier.objects.order_by('name'),
            'total_purchases_count': paginator.count,
            'total_units_purchased': aggregates['total_units'],
            'total_spend': aggregates['total_spend'],
        },
    )


@inventory_write_required
def purchase_create(request):
    form = PurchaseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = request.user if request.user.is_authenticated else None
            purchase = InventoryService.create_purchase(user=user, **form.cleaned_data)
            messages.success(
                request,
                f'Recorded purchase of {purchase.quantity} x "{purchase.product.name}" (BDT {purchase.total_amount:.2f}).',
            )
            return redirect('purchases:list')
        except ValueError as exc:
            form.add_error('quantity', str(exc))

    return render(request, 'purchases/form.html', {'form': form, 'title': 'New Purchase'})
