import csv
from decimal import Decimal

from django.contrib import messages
from django.db import models
from django.http import HttpResponse
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
    group_id = request.GET.get('group', '').strip()
    status_filter = request.GET.get('status', 'all').lower()
    sort_by = request.GET.get('sort', 'name_asc').lower()
    query = request.GET.get('q', '').strip()

    # Base query
    base_qs = Product.objects.select_related('inventory', 'group')

    # Calculate overall catalog summary metrics across ALL products
    all_catalog_products = list(base_qs)
    total_products_count = len(all_catalog_products)
    total_stock_units = sum(p.total_stock for p in all_catalog_products)
    total_retail_valuation = sum(p.total_stock * p.selling_price for p in all_catalog_products)
    total_cost_valuation = sum(p.total_stock * p.purchase_price for p in all_catalog_products)
    potential_profit = max(Decimal('0.00'), total_retail_valuation - total_cost_valuation)
    avg_catalog_margin = round(((total_retail_valuation - total_cost_valuation) / total_retail_valuation * 100), 1) if total_retail_valuation > 0 else 0.0

    low_stock_count = sum(1 for p in all_catalog_products if 0 < p.total_stock <= p.low_stock_threshold)
    out_of_stock_count = sum(1 for p in all_catalog_products if p.total_stock == 0)
    in_stock_count = sum(1 for p in all_catalog_products if p.total_stock > p.low_stock_threshold)

    # Filter by search
    qs = base_qs
    if query:
        qs = qs.filter(
            models.Q(name__icontains=query)
            | models.Q(sku__icontains=query)
            | models.Q(group__name__icontains=query)
        )

    # Filter by group
    if group_id:
        if group_id == 'none':
            qs = qs.filter(group__isnull=True)
        elif group_id.isdigit():
            qs = qs.filter(group_id=int(group_id))

    product_items = list(qs)

    # Calculate margins and statuses for each item
    for p in product_items:
        p.unit_profit = p.selling_price - p.purchase_price
        p.margin_pct = round((float(p.unit_profit) / float(p.selling_price) * 100), 1) if p.selling_price > 0 else 0.0
        p.markup_pct = round((float(p.unit_profit) / float(p.purchase_price) * 100), 1) if p.purchase_price > 0 else (100.0 if p.selling_price > 0 else 0.0)
        p.stock_val = p.total_stock * p.selling_price
        
        # Stock status
        if p.total_stock == 0:
            p.stock_status_code = 'out'
            p.stock_status_label = 'Out of Stock'
        elif p.total_stock <= p.low_stock_threshold:
            p.stock_status_code = 'low'
            p.stock_status_label = 'Low Stock'
        else:
            p.stock_status_code = 'ok'
            p.stock_status_label = 'In Stock'

    # Filter by stock level status
    if status_filter == 'out':
        product_items = [p for p in product_items if p.stock_status_code == 'out']
    elif status_filter == 'low':
        product_items = [p for p in product_items if p.stock_status_code == 'low']
    elif status_filter == 'in_stock':
        product_items = [p for p in product_items if p.stock_status_code == 'ok']

    # Sorting
    if sort_by == 'name_desc':
        product_items.sort(key=lambda p: p.name.lower(), reverse=True)
    elif sort_by == 'price_asc':
        product_items.sort(key=lambda p: p.selling_price)
    elif sort_by == 'price_desc':
        product_items.sort(key=lambda p: p.selling_price, reverse=True)
    elif sort_by == 'stock_asc':
        product_items.sort(key=lambda p: p.total_stock)
    elif sort_by == 'stock_desc':
        product_items.sort(key=lambda p: p.total_stock, reverse=True)
    elif sort_by == 'margin_desc':
        product_items.sort(key=lambda p: p.margin_pct, reverse=True)
    else:  # 'name_asc' default
        product_items.sort(key=lambda p: p.name.lower())

    groups = ProductGroup.objects.all().order_by('name')

    return render(
        request,
        'products/list.html',
        {
            'products': product_items,
            'groups': groups,
            'selected_group': group_id,
            'status_filter': status_filter,
            'sort_by': sort_by,
            'query': query,
            # KPI stats
            'total_products_count': total_products_count,
            'total_stock_units': total_stock_units,
            'total_retail_valuation': total_retail_valuation,
            'total_cost_valuation': total_cost_valuation,
            'potential_profit': potential_profit,
            'avg_catalog_margin': avg_catalog_margin,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'in_stock_count': in_stock_count,
        },
    )


def product_export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="mtronix-products-catalog.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Product ID',
        'Product Name',
        'Category / Group',
        'SKU / Barcode',
        'Purchase Price (BDT)',
        'Selling Price (BDT)',
        'Unit Profit (BDT)',
        'Margin %',
        'Current Stock (Units)',
        'Low Stock Limit',
        'Stock Status',
        'Total Cost Value (BDT)',
        'Total Retail Value (BDT)',
    ])

    products = Product.objects.select_related('inventory', 'group').order_by('name')
    for p in products:
        unit_profit = p.selling_price - p.purchase_price
        margin = round(((unit_profit / p.selling_price) * 100), 1) if p.selling_price > 0 else 0
        stock = p.total_stock
        cost_val = stock * p.purchase_price
        retail_val = stock * p.selling_price
        status = 'Out of Stock' if stock == 0 else ('Low Stock' if stock <= p.low_stock_threshold else 'In Stock')

        writer.writerow([
            p.pk,
            p.name,
            p.group.name if p.group else 'Unassigned',
            p.sku or '—',
            f'{p.purchase_price:.2f}',
            f'{p.selling_price:.2f}',
            f'{unit_profit:.2f}',
            f'{margin}%',
            stock,
            p.low_stock_threshold,
            status,
            f'{cost_val:.2f}',
            f'{retail_val:.2f}',
        ])

    return response


def product_create(request):
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Product "{product.name}" created successfully.')
        return redirect('products:list')

    return render(request, 'products/form.html', {'form': form, 'title': 'New Product'})


def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Product "{product.name}" updated successfully.')
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
    groups = list(ProductGroup.objects.prefetch_related('products__inventory').order_by('name'))
    
    total_groups_count = len(groups)
    total_categorized_products = 0
    total_groups_valuation = Decimal('0.00')

    for g in groups:
        prods = list(g.products.all())
        g.product_count = len(prods)
        g.total_stock = sum(p.total_stock for p in prods)
        g.total_retail_value = sum(p.total_stock * p.selling_price for p in prods)
        g.total_cost_value = sum(p.total_stock * p.purchase_price for p in prods)
        g.potential_profit = max(Decimal('0.00'), g.total_retail_value - g.total_cost_value)
        g.avg_price = (sum(p.selling_price for p in prods) / len(prods)) if prods else Decimal('0.00')
        
        total_categorized_products += g.product_count
        total_groups_valuation += g.total_retail_value

    # Top valued group
    top_group = max(groups, key=lambda g: g.total_retail_value, default=None) if groups else None

    return render(
        request,
        'products/group_list.html',
        {
            'groups': groups,
            'total_groups_count': total_groups_count,
            'total_categorized_products': total_categorized_products,
            'total_groups_valuation': total_groups_valuation,
            'top_group': top_group,
        },
    )


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
        group = form.save()
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
