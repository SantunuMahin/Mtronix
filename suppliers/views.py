from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from suppliers.forms import SupplierForm
from suppliers.models import Supplier
from suppliers.serializers import SupplierSerializer


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('name')
    serializer_class = SupplierSerializer


def supplier_list(request):
    suppliers = Supplier.objects.order_by('name')
    return render(request, 'suppliers/list.html', {'suppliers': suppliers})


def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('suppliers:list')

    return render(request, 'suppliers/form.html', {'form': form, 'title': 'New Supplier'})


def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('suppliers:list')

    return render(request, 'suppliers/form.html', {'form': form, 'title': 'Edit Supplier'})
