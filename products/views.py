from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from products.forms import ProductForm, ProductGroupForm
from products.models import Product, ProductGroup
from products.serializers import ProductGroupSerializer, ProductSerializer


class ProductGroupViewSet(viewsets.ModelViewSet):
    queryset = ProductGroup.objects.all().order_by('name')
    serializer_class = ProductGroupSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('inventory', 'group').order_by('name')
    serializer_class = ProductSerializer


def product_list(request):
    group_id = request.GET.get('group')
    query = request.GET.get('q', '').strip()
    products = Product.objects.select_related('inventory', 'group').order_by('name')

    if query:
        products = products.filter(
            models.Q(name__icontains=query)
            | models.Q(sku__icontains=query)
            | models.Q(group__name__icontains=query)
        )

    if group_id:
        if group_id == 'none':
            products = products.filter(group__isnull=True)
        else:
            products = products.filter(group_id=group_id)

    groups = ProductGroup.objects.all().order_by('name')
    return render(
        request,
        'products/list.html',
        {
            'products': products,
            'groups': groups,
            'selected_group': group_id,
            'query': query,
        },
    )


def product_create(request):
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Product added successfully.')
        return redirect('products:list')

    return render(request, 'products/form.html', {'form': form, 'title': 'New Product'})


def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Product updated successfully.')
        return redirect('products:list')

    return render(request, 'products/form.html', {'form': form, 'title': 'Edit Product', 'product': product})


def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" deleted successfully.')
        return redirect('products:list')

    return render(request, 'products/confirm_delete.html', {'product': product})


# ── Product Group Views ───────────────────────────────────────────────────────

def group_list(request):
    groups = ProductGroup.objects.prefetch_related('products').order_by('name')
    return render(request, 'products/group_list.html', {'groups': groups})


def group_create(request):
    form = ProductGroupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        group = form.save()
        messages.success(request, f'Group "{group.name}" created successfully.')
        return redirect('products:group_list')

    return render(
        request,
        'products/group_form.html',
        {'form': form, 'title': 'New Product Group'},
    )


def group_update(request, pk):
    group = get_object_or_404(ProductGroup, pk=pk)
    form = ProductGroupForm(request.POST or None, instance=group)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Group "{group.name}" updated successfully.')
        return redirect('products:group_list')

    return render(
        request,
        'products/group_form.html',
        {'form': form, 'title': f'Edit Group: {group.name}'},
    )


def group_delete(request, pk):
    group = get_object_or_404(ProductGroup, pk=pk)
    if request.method == 'POST':
        name = group.name
        group.delete()
        messages.success(request, f'Group "{name}" deleted.')
        return redirect('products:group_list')

    return render(
        request,
        'products/group_confirm_delete.html',
        {'group': group},
    )
