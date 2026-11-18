import csv
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.db.models import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import viewsets

from accounts.decorators import management_required
from accounts.permissions import ManagementWritePermission
from products.forms import ProductForm, ProductGroupForm
from products.models import Product, ProductGroup
from products.serializers import ProductGroupSerializer, ProductSerializer


class ProductGroupViewSet(viewsets.ModelViewSet):
    queryset = ProductGroup.objects.all().order_by('name')
    serializer_class = ProductGroupSerializer
    permission_classes = [ManagementWritePermission]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('inventory', 'group').order_by('name')
    serializer_class = ProductSerializer
    permission_classes = [ManagementWritePermission]


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

    paginator = Paginator(product_items, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'products/list.html',
        {
            'products': page_obj.object_list,
            'page_obj': page_obj,
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


@management_required
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


@management_required
def product_create(request):
    initial = {}
    if request.method != 'POST':
        sku_param = request.GET.get('sku', '').strip()
        if sku_param:
            initial['sku'] = sku_param
    form = ProductForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Product "{product.name}" created successfully.')
        return redirect('products:list')

    return render(request, 'products/form.html', {'form': form, 'title': 'New Product'})


@management_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Product "{product.name}" updated successfully.')
        return redirect('products:list')

    return render(request, 'products/form.html', {'form': form, 'title': 'Edit Product', 'product': product})


@management_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        try:
            product.delete()
            messages.success(request, f'Product "{name}" deleted successfully.')
        except ProtectedError:
            messages.error(
                request,
                f'Cannot delete "{name}" because it has linked purchase history.'
            )
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


@management_required
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


@management_required
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


@management_required
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


# ─── Barcode Printing & Generation Views ──────────────────────────────

def product_barcode_label(request, pk):
    """
    Render a printable barcode label sheet for a single product.
    Allows user to select quantity of stickers and format (thermal label or A4 sheet).
    """
    from products.barcode import generate_code128_svg, generate_code128_data_uri, generate_unique_product_sku

    product = get_object_or_404(Product.objects.select_related('inventory', 'group'), pk=pk)

    # If product has no SKU/Barcode, auto-generate and save one so it can be scanned
    if not product.sku:
        product.sku = generate_unique_product_sku()
        product.save(update_fields=['sku'])
        messages.info(request, f'Generated unique barcode/SKU: {product.sku}')

    try:
        copies = max(1, min(200, int(request.GET.get('copies', 1))))
    except ValueError:
        copies = 1

    layout = request.GET.get('layout', 'thermal')
    if layout not in ('thermal', 'a4_24', 'a4_30'):
        layout = 'thermal'

    barcode_svg = generate_code128_svg(product.sku, height=45, module_width=1.7)
    barcode_data_uri = generate_code128_data_uri(product.sku, height=45, module_width=1.7)

    labels = [
        {
            'product': product,
            'barcode_svg': barcode_svg,
            'barcode_data_uri': barcode_data_uri,
        }
        for _ in range(copies)
    ]

    return render(
        request,
        'products/barcode_label.html',
        {
            'product': product,
            'labels': labels,
            'copies': copies,
            'layout': layout,
            'barcode_svg': barcode_svg,
        },
    )


def product_barcode_batch_print(request):
    """
    Batch print barcode labels for multiple selected or all products.
    """
    from products.barcode import generate_code128_svg, generate_code128_data_uri, generate_unique_product_sku

    ids_str = request.GET.get('ids', '').strip()
    group_id = request.GET.get('group', '').strip()
    mode = request.GET.get('mode', 'fixed')  # 'fixed' or 'stock'
    layout = request.GET.get('layout', 'a4_30')  # 'thermal', 'a4_24', 'a4_30'

    try:
        copies_per_item = max(1, min(50, int(request.GET.get('copies', 1))))
    except ValueError:
        copies_per_item = 1

    qs = Product.objects.select_related('inventory', 'group').order_by('name')

    if ids_str:
        id_list = [int(i.strip()) for i in ids_str.split(',') if i.strip().isdigit()]
        if id_list:
            qs = qs.filter(pk__in=id_list)
    elif group_id and group_id.isdigit():
        qs = qs.filter(group_id=int(group_id))

    products = list(qs)

    # Ensure every product has a valid barcode SKU
    for p in products:
        if not p.sku:
            p.sku = generate_unique_product_sku()
            p.save(update_fields=['sku'])

    all_labels = []
    for p in products:
        svg = generate_code128_svg(p.sku, height=42, module_width=1.6)
        data_uri = generate_code128_data_uri(p.sku, height=42, module_width=1.6)

        num_copies = copies_per_item
        if mode == 'stock':
            num_copies = max(1, p.total_stock)

        for _ in range(num_copies):
            all_labels.append({
                'product': p,
                'barcode_svg': svg,
                'barcode_data_uri': data_uri,
            })

    groups = ProductGroup.objects.all().order_by('name')

    return render(
        request,
        'products/barcode_batch_print.html',
        {
            'labels': all_labels,
            'products': products,
            'groups': groups,
            'total_stickers': len(all_labels),
            'selected_group': group_id,
            'selected_mode': mode,
            'copies_per_item': copies_per_item,
            'layout': layout,
            'ids_str': ids_str,
        },
    )


def api_generate_sku(request):
    """
    API to generate a unique SKU and its live SVG barcode representation.
    """
    from products.barcode import generate_unique_product_sku, generate_code128_svg

    prefix = request.GET.get('prefix', 'MTX').strip() or 'MTX'
    name_hint = request.GET.get('name', '').strip()
    group_hint = request.GET.get('group', '').strip()
    sku = generate_unique_product_sku(prefix=prefix, name_hint=name_hint or group_hint)
    svg = generate_code128_svg(sku, height=42)

    return JsonResponse({
        'success': True,
        'sku': sku,
        'svg': svg,
    })


def api_preview_barcode(request):
    """
    API to generate live SVG barcode for any typed text.
    """
    from products.barcode import generate_code128_svg, generate_code128_data_uri

    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({'success': False, 'valid': False, 'message': 'Code is required'}, status=400)

    svg = generate_code128_svg(code, height=44)
    data_uri = generate_code128_data_uri(code, height=44)

    return JsonResponse({
        'success': True,
        'valid': True,
        'code': code,
        'svg': svg,
        'data_uri': data_uri,
    })

