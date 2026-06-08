from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from products.forms import ProductForm
from products.models import Product
from products.serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('name')
    serializer_class = ProductSerializer


def product_list(request):
    products = Product.objects.select_related('inventory').order_by('name')
    return render(request, 'products/list.html', {'products': products})


def product_create(request):
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('products:list')

    return render(request, 'products/form.html', {'form': form, 'title': 'New Product'})


def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('products:list')

    return render(request, 'products/form.html', {'form': form, 'title': 'Edit Product'})
