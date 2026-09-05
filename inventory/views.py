import calendar
import datetime
from decimal import Decimal
import json
from django.db import models
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import viewsets
import pytz

from inventory.forms import StockAdjustmentForm
from inventory.models import Inventory, StockMovement
from inventory.pdf import (
    BD_TZ,
    build_inventory_stock_pdf,
    build_new_products_pdf,
    build_stock_updates_pdf,
)
from inventory.serializers import InventorySerializer
from inventory.services import InventoryService
from products.models import Product
from sales.models import Sale, SaleItem


def _get_date_range_for_period(period):
    now = timezone.now().astimezone(BD_TZ)
    midnight = {'hour': 0, 'minute': 0, 'second': 0, 'microsecond': 0}
    end_of_day = {'hour': 23, 'minute': 59, 'second': 59, 'microsecond': 999999}

    if period == "today":
        start = now.replace(**midnight)
        end = now.replace(**end_of_day)
        label = f"Today ({start.strftime('%b %d, %Y')})"
    elif period == "week":
        start = (now - datetime.timedelta(days=now.weekday())).replace(**midnight)
        end = now.replace(**end_of_day)
        label = f"This Week ({start.strftime('%b %d')} - {end.strftime('%b %d, %Y')})"
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


def _build_chart_trend_data(period, sales_qs):
    now = timezone.now().astimezone(BD_TZ)
    if period == 'today':
        earliest = (now - datetime.timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_of_week = now - datetime.timedelta(days=now.weekday())
        earliest = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'month':
        earliest = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'year':
        earliest = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # 'all' -> last 6 months
        earliest = (now - datetime.timedelta(days=185)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    all_sales = list(sales_qs.filter(sold_at__gte=earliest))

    labels = []
    revenue_series = []
    orders_series = []
    paid_series = []
    due_series = []

    if period == 'today':
        for i in range(6, -1, -1):
            day_dt = now - datetime.timedelta(days=i)
            day_start = day_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            lbl = "Today" if i == 0 else day_dt.strftime("%a %d")
            labels.append(lbl)
            day_sales = [s for s in all_sales if day_start <= s.sold_at.astimezone(BD_TZ) <= day_end]
            revenue_series.append(float(sum(s.total_amount for s in day_sales)))
            orders_series.append(len(day_sales))
            paid_series.append(float(sum(s.effective_paid_amount for s in day_sales)))
            due_series.append(float(sum(s.due_amount for s in day_sales)))

    elif period == 'week':
        start_of_week = now - datetime.timedelta(days=now.weekday())
        for i in range(7):
            day_dt = start_of_week + datetime.timedelta(days=i)
            day_start = day_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            labels.append(day_dt.strftime("%a (%d)"))
            day_sales = [s for s in all_sales if day_start <= s.sold_at.astimezone(BD_TZ) <= day_end]
            revenue_series.append(float(sum(s.total_amount for s in day_sales)))
            orders_series.append(len(day_sales))
            paid_series.append(float(sum(s.effective_paid_amount for s in day_sales)))
            due_series.append(float(sum(s.due_amount for s in day_sales)))

    elif period == 'month':
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        step = max(1, days_in_month // 6)
        day_points = list(range(1, days_in_month + 1, step))
        if days_in_month not in day_points:
            day_points.append(days_in_month)

        for i in range(len(day_points) - 1):
            d_start = day_points[i]
            d_end = day_points[i + 1] - (1 if i + 1 < len(day_points) - 1 else 0)
            if d_start > d_end:
                d_end = d_start
            dt_start = now.replace(day=d_start, hour=0, minute=0, second=0, microsecond=0)
            dt_end = now.replace(day=d_end, hour=23, minute=59, second=59, microsecond=999999)
            labels.append(f"{dt_start.strftime('%b')} {d_start}-{d_end}")
            bracket_sales = [s for s in all_sales if dt_start <= s.sold_at.astimezone(BD_TZ) <= dt_end]
            revenue_series.append(float(sum(s.total_amount for s in bracket_sales)))
            orders_series.append(len(bracket_sales))
            paid_series.append(float(sum(s.effective_paid_amount for s in bracket_sales)))
            due_series.append(float(sum(s.due_amount for s in bracket_sales)))

    elif period == 'year':
        for m in range(1, 13):
            m_start = now.replace(month=m, day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day = calendar.monthrange(now.year, m)[1]
            m_end = now.replace(month=m, day=last_day, hour=23, minute=59, second=59, microsecond=999999)
            labels.append(calendar.month_abbr[m])
            m_sales = [s for s in all_sales if m_start <= s.sold_at.astimezone(BD_TZ) <= m_end]
            revenue_series.append(float(sum(s.total_amount for s in m_sales)))
            orders_series.append(len(m_sales))
            paid_series.append(float(sum(s.effective_paid_amount for s in m_sales)))
            due_series.append(float(sum(s.due_amount for s in m_sales)))

    else:  # 'all'
        for i in range(5, -1, -1):
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1
            m_start = now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day = calendar.monthrange(year, month)[1]
            m_end = now.replace(year=year, month=month, day=last_day, hour=23, minute=59, second=59, microsecond=999999)
            labels.append(f"{calendar.month_abbr[month]} '{str(year)[-2:]}")
            m_sales = [s for s in all_sales if m_start <= s.sold_at.astimezone(BD_TZ) <= m_end]
            revenue_series.append(float(sum(s.total_amount for s in m_sales)))
            orders_series.append(len(m_sales))
            paid_series.append(float(sum(s.effective_paid_amount for s in m_sales)))
            due_series.append(float(sum(s.due_amount for s in m_sales)))

    return {
        'labels': labels,
        'revenue': revenue_series,
        'orders': orders_series,
        'paid': paid_series,
        'due': due_series,
    }


class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Inventory.objects.select_related('product').order_by('product__name')
    serializer_class = InventorySerializer


def dashboard(request):
    period = request.GET.get('period', 'today').lower()
    start_date, end_date, period_label = _get_date_range_for_period(period)

    # Base inventory
    inventory_qs = Inventory.objects.select_related('product', 'product__group').order_by('product__name')
    inventory_list = list(inventory_qs)
    total_products = Product.objects.count()
    total_stock_units = sum(i.quantity for i in inventory_list)
    inventory_value_cost = sum(i.quantity * i.product.purchase_price for i in inventory_list)
    inventory_value_retail = sum(i.quantity * i.product.selling_price for i in inventory_list)
    potential_profit = max(Decimal('0.00'), inventory_value_retail - inventory_value_cost)

    low_stock = [i for i in inventory_list if i.quantity <= i.product.low_stock_threshold]
    out_of_stock = [i for i in inventory_list if i.quantity == 0]

    # Sales Analytics for selected period
    sales_qs = Sale.objects.prefetch_related('items__product').order_by('-sold_at')
    if start_date and end_date:
        period_sales_qs = sales_qs.filter(sold_at__range=(start_date, end_date))
    else:
        period_sales_qs = sales_qs

    period_sales = list(period_sales_qs)
    period_revenue = sum(s.total_amount for s in period_sales)
    period_paid = sum(s.effective_paid_amount for s in period_sales)
    period_due = sum(s.due_amount for s in period_sales)
    period_tx_count = len(period_sales)

    # Calculate total units sold in period
    items_qs = SaleItem.objects.all()
    if start_date and end_date:
        items_qs = items_qs.filter(sale__sold_at__range=(start_date, end_date))
    period_units_sold = sum(item.quantity for item in items_qs)

    # Store-wide all time receivables — lean queryset to avoid full model loads
    all_sales_summary = Sale.objects.only('payment_status', 'paid_amount').prefetch_related('items')
    store_total_due = sum(s.due_amount for s in all_sales_summary)
    store_total_revenue = sum(s.total_amount for s in all_sales_summary)
    store_total_paid = sum(s.effective_paid_amount for s in all_sales_summary)

    # Realized Gross Profit in period
    period_gross_profit = Decimal('0.00')
    for s in period_sales:
        for item in s.items.all():
            if item.product:
                cost = item.product.purchase_price
                period_gross_profit += ((item.unit_price - cost) * item.quantity)
    period_gross_profit = max(Decimal('0.00'), period_gross_profit)
    period_profit_margin_pct = round((float(period_gross_profit) / float(period_revenue) * 100), 1) if period_revenue > 0 else 0.0

    # Recent Sales (latest 8)
    recent_sales = sales_qs[:8]

    # Top 5 selling items in period
    top_selling_qs = (
        items_qs
        .annotate(
            resolved_name=Coalesce("product__name", "custom_name", models.Value("Custom / Unlisted Item")),
            resolved_sku=Coalesce("product__sku", models.Value("—")),
        )
        .values("resolved_name", "resolved_sku")
        .annotate(
            total_qty=models.Sum("quantity"),
            total_sales=models.Sum(
                models.F("quantity") * models.F("unit_price"),
                output_field=models.DecimalField(max_digits=18, decimal_places=2)
            )
        )
        .order_by("-total_qty")[:5]
    )
    top_selling = list(top_selling_qs)
    max_top_qty = max([item['total_qty'] for item in top_selling], default=1) or 1
    for item in top_selling:
        item['pct'] = int((item['total_qty'] / max_top_qty) * 100)

    # Average Order Value
    avg_order_value = (period_revenue / period_tx_count) if period_tx_count > 0 else Decimal('0.00')

    # Collection Rate (% paid in period)
    collection_rate = round((period_paid / period_revenue * 100), 1) if period_revenue > 0 else 100.0

    # Stock Health (%)
    healthy_stock_count = len([i for i in inventory_list if i.quantity > i.product.low_stock_threshold])
    low_stock_count = len(low_stock) - len(out_of_stock)
    out_of_stock_count = len(out_of_stock)
    stock_health_pct = round((healthy_stock_count / total_products * 100), 1) if total_products > 0 else 100.0

    # Product Group sales & category distribution
    group_rev_map = {}
    for s in period_sales:
        for item in s.items.all():
            grp = item.product.group.name if (item.product and item.product.group) else 'Unassigned'
            group_rev_map[grp] = group_rev_map.get(grp, 0.0) + float(item.quantity * item.unit_price)

    # Fallback to inventory value by group if no sales recorded in selected period
    if not group_rev_map or sum(group_rev_map.values()) == 0:
        for inv in inventory_list:
            grp = inv.product.group.name if inv.product.group else 'Unassigned'
            group_rev_map[grp] = group_rev_map.get(grp, 0.0) + float(inv.quantity * inv.product.selling_price)
        cat_chart_title = "Inventory Value by Group (BDT)"
    else:
        cat_chart_title = "Sales Share by Group (BDT)"

    chart_category_labels = list(group_rev_map.keys())
    chart_category_data = [round(v, 2) for v in group_rev_map.values()]

    # Stock health distribution dataset
    chart_stock_labels = ['Healthy Stock', 'Low Stock Threshold', 'Out of Stock']
    chart_stock_data = [healthy_stock_count, low_stock_count, out_of_stock_count]

    # Payment ratio dataset
    chart_payment_labels = ['Paid (Cash In)', 'Due (Receivables)']
    chart_payment_data = [float(period_paid), float(period_due)]

    # Time series trend data — query is bounded by earliest date inside the helper
    chart_trend_data = _build_chart_trend_data(period, sales_qs)

    context = {
        'period': period,
        'period_label': period_label,
        'total_products': total_products,
        'total_stock_units': total_stock_units,
        'inventory_value_cost': inventory_value_cost,
        'inventory_value_retail': inventory_value_retail,
        'potential_profit': potential_profit,
        'low_stock': low_stock,
        'low_stock_count': len(low_stock),
        'out_of_stock_count': out_of_stock_count,
        'period_revenue': period_revenue,
        'period_paid': period_paid,
        'period_due': period_due,
        'period_gross_profit': period_gross_profit,
        'period_profit_margin_pct': period_profit_margin_pct,
        'period_tx_count': period_tx_count,
        'period_units_sold': period_units_sold,
        'avg_order_value': avg_order_value,
        'collection_rate': collection_rate,
        'stock_health_pct': stock_health_pct,
        'store_total_due': store_total_due,
        'store_total_revenue': store_total_revenue,
        'store_total_paid': store_total_paid,
        'recent_sales': recent_sales,
        'top_selling': top_selling,
        'current_inventory': inventory_list[:8],
        # Chart JSON contexts
        'chart_labels_json': json.dumps(chart_trend_data['labels']),
        'chart_revenue_json': json.dumps(chart_trend_data['revenue']),
        'chart_orders_json': json.dumps(chart_trend_data['orders']),
        'chart_paid_json': json.dumps(chart_trend_data['paid']),
        'chart_due_json': json.dumps(chart_trend_data['due']),
        'chart_category_labels_json': json.dumps(chart_category_labels),
        'chart_category_data_json': json.dumps(chart_category_data),
        'cat_chart_title': cat_chart_title,
        'chart_stock_labels_json': json.dumps(chart_stock_labels),
        'chart_stock_data_json': json.dumps(chart_stock_data),
        'chart_payment_labels_json': json.dumps(chart_payment_labels),
        'chart_payment_data_json': json.dumps(chart_payment_data),
    }
    return render(request, 'inventory/dashboard.html', context)


def inventory_list(request):
    query = request.GET.get('q', '').strip()
    group_filter = request.GET.get('group', '').strip()
    status_filter = request.GET.get('status', 'all').lower()
    sort_by = request.GET.get('sort', 'name').lower()

    # Base queryset
    qs = Inventory.objects.select_related('product', 'product__group')

    # Group filter
    if group_filter:
        qs = qs.filter(product__group__name=group_filter)

    # Search filter
    if query:
        qs = qs.filter(
            models.Q(product__name__icontains=query) |
            models.Q(product__sku__icontains=query) |
            models.Q(product__group__name__icontains=query)
        )

    all_inventory = list(qs)
    total_products_count = Product.objects.count()
    all_unfiltered = list(Inventory.objects.select_related('product', 'product__group'))

    # Summary metrics across entire store
    total_units_count = sum(i.quantity for i in all_unfiltered)
    total_retail_valuation = sum(i.quantity * i.product.selling_price for i in all_unfiltered)
    total_cost_valuation = sum(i.quantity * i.product.purchase_price for i in all_unfiltered)
    potential_profit = max(Decimal('0.00'), total_retail_valuation - total_cost_valuation)
    low_stock_count = sum(1 for i in all_unfiltered if i.quantity <= i.product.low_stock_threshold and i.quantity > 0)
    out_of_stock_count = sum(1 for i in all_unfiltered if i.quantity == 0)
    healthy_stock_count = sum(1 for i in all_unfiltered if i.quantity > i.product.low_stock_threshold)

    # Filter by stock level status
    if status_filter == 'out':
        filtered_inventory = [i for i in all_inventory if i.quantity == 0]
    elif status_filter == 'low':
        filtered_inventory = [i for i in all_inventory if i.quantity <= i.product.low_stock_threshold and i.quantity > 0]
    elif status_filter == 'in_stock':
        filtered_inventory = [i for i in all_inventory if i.quantity > i.product.low_stock_threshold]
    else:
        filtered_inventory = all_inventory

    # Sorting
    if sort_by == 'qty_asc':
        filtered_inventory.sort(key=lambda i: i.quantity)
    elif sort_by == 'qty_desc':
        filtered_inventory.sort(key=lambda i: i.quantity, reverse=True)
    elif sort_by == 'val_desc':
        filtered_inventory.sort(key=lambda i: (i.quantity * i.product.selling_price), reverse=True)
    elif sort_by == 'val_asc':
        filtered_inventory.sort(key=lambda i: (i.quantity * i.product.selling_price))
    else:  # name default
        filtered_inventory.sort(key=lambda i: i.product.name.lower())

    from products.models import ProductGroup
    product_groups = ProductGroup.objects.all().order_by('name')

    return render(request, 'inventory/list.html', {
        'inventory': filtered_inventory,
        'query': query,
        'group_filter': group_filter,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'product_groups': product_groups,
        'total_products_count': total_products_count,
        'total_units_count': total_units_count,
        'total_retail_valuation': total_retail_valuation,
        'total_cost_valuation': total_cost_valuation,
        'potential_profit': potential_profit,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'healthy_stock_count': healthy_stock_count,
    })


def inventory_logs(request):
    product_id = request.GET.get('product', '').strip()
    movement_type = request.GET.get('type', '').strip().upper()
    query = request.GET.get('q', '').strip()

    movements = StockMovement.objects.select_related('product', 'product__group', 'user').order_by('-created_at')

    if product_id and product_id.isdigit():
        movements = movements.filter(product_id=int(product_id))

    if movement_type and movement_type != 'ALL':
        movements = movements.filter(movement_type=movement_type)

    if query:
        movements = movements.filter(
            models.Q(product__name__icontains=query) |
            models.Q(product__sku__icontains=query) |
            models.Q(reason__icontains=query) |
            models.Q(notes__icontains=query)
        )

    all_products = Product.objects.all().order_by('name')

    # Count BEFORE slicing (sliced querysets cannot be counted)
    total_movements_count = movements.count()

    return render(request, 'inventory/logs.html', {
        'movements': movements[:150],
        'total_movements_count': total_movements_count,
        'selected_product_id': product_id,
        'selected_type': movement_type,
        'query': query,
        'all_products': all_products,
        'movement_types': StockMovement.MOVEMENT_TYPE_CHOICES,
    })


def inventory_add_stock(request, pk):
    inventory = get_object_or_404(Inventory.objects.select_related('product', 'product__group'), pk=pk)
    form = StockAdjustmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        qty = form.cleaned_data['quantity']
        reason = form.cleaned_data.get('reason') or 'Supplier Restock / Delivery'
        notes = form.cleaned_data.get('notes') or ''
        user = request.user if request.user.is_authenticated else None
        InventoryService.add_stock(inventory.product, qty, user=user, reason=reason, notes=notes)
        return redirect('inventory:list')

    return render(
        request,
        'inventory/adjust.html',
        {
            'form': form,
            'inventory': inventory,
            'mode': 'ADD',
            'title': f'Add Stock — {inventory.product.name}',
            'action_label': 'Confirm Stock In (+)',
            'reason_choices': StockAdjustmentForm.REASON_ADD_CHOICES,
        },
    )


def inventory_remove_stock(request, pk):
    inventory = get_object_or_404(Inventory.objects.select_related('product', 'product__group'), pk=pk)
    form = StockAdjustmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        qty = form.cleaned_data['quantity']
        reason = form.cleaned_data.get('reason') or 'Damaged / Broken / Defective'
        notes = form.cleaned_data.get('notes') or ''
        user = request.user if request.user.is_authenticated else None
        try:
            InventoryService.remove_stock(inventory.product, qty, user=user, reason=reason, notes=notes)
            return redirect('inventory:list')
        except ValueError as exc:
            form.add_error('quantity', str(exc))

    return render(
        request,
        'inventory/adjust.html',
        {
            'form': form,
            'inventory': inventory,
            'mode': 'REMOVE',
            'title': f'Deduct Stock — {inventory.product.name}',
            'action_label': 'Confirm Stock Out (−)',
            'reason_choices': StockAdjustmentForm.REASON_REMOVE_CHOICES,
        },
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
