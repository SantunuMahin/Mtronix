from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.db.models import ProtectedError
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from accounts.decorators import inventory_write_required, management_required
from accounts.permissions import InventoryWritePermission
from suppliers.forms import SupplierForm
from suppliers.models import Supplier
from suppliers.serializers import SupplierSerializer


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('name')
    serializer_class = SupplierSerializer
    permission_classes = [InventoryWritePermission]


@inventory_write_required
def supplier_list(request):
    query = request.GET.get('q', '').strip()
    qs = Supplier.objects.annotate(
        purchase_count=models.Count('purchases'),
        total_spend=Coalesce(
            models.Sum(
                models.F('purchases__quantity') * models.F('purchases__unit_price'),
                output_field=models.DecimalField(max_digits=14, decimal_places=2),
            ),
            Decimal('0.00'),
        ),
    ).order_by('name')

    if query:
        qs = qs.filter(
            models.Q(name__icontains=query)
            | models.Q(phone__icontains=query)
            | models.Q(email__icontains=query)
        )

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'suppliers/list.html',
        {
            'suppliers': page_obj.object_list,
            'page_obj': page_obj,
            'query': query,
            'total_suppliers_count': paginator.count,
        },
    )


@inventory_write_required
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        supplier = form.save()
        messages.success(request, f'Supplier "{supplier.name}" created successfully.')
        return redirect('suppliers:list')

    return render(request, 'suppliers/form.html', {'form': form, 'title': 'New Supplier'})


@inventory_write_required
def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == 'POST' and form.is_valid():
        supplier = form.save()
        messages.success(request, f'Supplier "{supplier.name}" updated successfully.')
        return redirect('suppliers:list')

    return render(request, 'suppliers/form.html', {'form': form, 'title': f'Edit Supplier: {supplier.name}'})


@management_required
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        name = supplier.name
        try:
            supplier.delete()
            messages.success(request, f'Supplier "{name}" deleted successfully.')
        except ProtectedError:
            messages.error(
                request,
                f'Cannot delete "{name}" because it has linked purchase history.',
            )
        return redirect('suppliers:list')

    return render(request, 'suppliers/confirm_delete.html', {'supplier': supplier})
