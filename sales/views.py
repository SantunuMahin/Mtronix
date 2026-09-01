import calendar
from django.contrib import messages
from django.db import models
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.forms import inlineformset_factory
from rest_framework import mixins, viewsets
import base64
import io
import pytz

from decimal import Decimal
import re

from inventory.services import InventoryService
from sales.forms import SaleForm, SaleItemForm
from sales.models import Sale, SaleItem
from sales.pdf import (
    MAPS_URL,
    build_customer_statement_pdf,
    build_sale_receipt_pdf,
    build_sales_report_pdf,
    qrcode,
)
from sales.serializers import SaleSerializer

BD_TZ = pytz.timezone('Asia/Dhaka')


def _generate_qr_base64(data: str) -> str:
    if qrcode is None:
        return ''
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=2,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('ascii')


class SaleViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Sale.objects.prefetch_related('items__product').order_by('-sold_at')
    serializer_class = SaleSerializer


SaleItemFormSet = inlineformset_factory(
    Sale,
    SaleItem,
    form=SaleItemForm,
    extra=0,
    min_num=1,
    validate_min=True,
)


# ─── Helper functions ────────────────────────────────────────

def _build_products_catalog():
    """Build product catalog with inventory data for the frontend."""
    from products.models import Product
    products = Product.objects.select_related('inventory', 'group').order_by('name')
    products_catalog = []
    for product in products:
        stock = product.inventory.quantity if hasattr(product, 'inventory') else 0
        products_catalog.append({
            'id': product.id,
            'name': product.name,
            'group': product.group.name if product.group else '',
            'sku': product.sku,
            'price': str(product.selling_price),
            'stock': stock,
        })
    return products_catalog


def _build_customer_suggestions(limit=40):
    """Build returning customer profiles with previous buy details and totals."""
    sales = Sale.objects.exclude(customer_name='').prefetch_related('items__product').order_by('-sold_at')
    customers = {}
    for sale in sales:
        c_name = (sale.customer_name or '').strip()
        c_phone = (sale.customer_phone or '').strip()
        if not c_name and not c_phone:
            continue
        key = (c_name.lower(), c_phone.lower())
        if key not in customers:
            if len(customers) >= limit:
                continue
            customers[key] = {
                'customer_name': c_name,
                'customer_phone': c_phone,
                'customer_address': (sale.customer_address or '').strip(),
                'total_orders': 0,
                'total_spent': Decimal('0.00'),
                'total_paid': Decimal('0.00'),
                'total_due': Decimal('0.00'),
                'last_order_date': timezone.localtime(sale.sold_at, BD_TZ).strftime('%d %b %Y, %I:%M %p'),
                'recent_sales': [],
            }
        c = customers[key]
        c['total_orders'] += 1
        c['total_spent'] += sale.total_amount
        c['total_paid'] += sale.effective_paid_amount
        c['total_due'] += sale.due_amount
        if not c['customer_address'] and sale.customer_address:
            c['customer_address'] = sale.customer_address.strip()
        if len(c['recent_sales']) < 3:
            items_list = [
                {
                    'product_id': item.product_id,
                    'product_name': item.display_name,
                    'sku': item.sku,
                    'quantity': item.quantity,
                    'unit_price': str(item.unit_price),
                    'total_amount': str(item.total_amount),
                    'is_custom': item.product_id is None,
                }
                for item in sale.items.all()
            ]
            c['recent_sales'].append({
                'id': sale.pk,
                'code': f'SALE-{sale.pk:05d}',
                'date': timezone.localtime(sale.sold_at, BD_TZ).strftime('%d %b %Y'),
                'total_amount': str(sale.total_amount),
                'paid_amount': str(sale.effective_paid_amount),
                'due_amount': str(sale.due_amount),
                'payment_status': sale.payment_status,
                'status_display': sale.get_payment_status_display(),
                'items': items_list,
            })

    return [
        {
            'customer_name': v['customer_name'],
            'customer_phone': v['customer_phone'],
            'customer_address': v['customer_address'],
            'total_orders': v['total_orders'],
            'total_spent': float(v['total_spent']),
            'total_paid': float(v['total_paid']),
            'total_due': float(v['total_due']),
            'last_order_date': v['last_order_date'],
            'recent_sales': v['recent_sales'],
        }
        for v in customers.values()
    ]


def customer_lookup_api(request):
    """
    API for searching customer purchase history dynamically by name or phone.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})

    sales = (
        Sale.objects.filter(
            models.Q(customer_name__icontains=query) |
            models.Q(customer_phone__icontains=query)
        )
        .prefetch_related('items__product')
        .order_by('-sold_at')
    )

    customers_map = {}
    for sale in sales:
        c_name = (sale.customer_name or '').strip()
        c_phone = (sale.customer_phone or '').strip()
        if not c_name and not c_phone:
            continue
        key = (c_name.lower(), c_phone.lower())
        if key not in customers_map:
            customers_map[key] = {
                'customer_name': c_name,
                'customer_phone': c_phone,
                'customer_address': (sale.customer_address or '').strip(),
                'total_orders': 0,
                'total_spent': Decimal('0.00'),
                'total_paid': Decimal('0.00'),
                'total_due': Decimal('0.00'),
                'last_order_date': timezone.localtime(sale.sold_at, BD_TZ).strftime('%d %b %Y, %I:%M %p'),
                'recent_sales': [],
            }

        c_data = customers_map[key]
        c_data['total_orders'] += 1
        c_data['total_spent'] += sale.total_amount
        c_data['total_paid'] += sale.effective_paid_amount
        c_data['total_due'] += sale.due_amount
        if not c_data['customer_address'] and sale.customer_address:
            c_data['customer_address'] = sale.customer_address.strip()

        if len(c_data['recent_sales']) < 5:
            items_list = [
                {
                    'product_id': item.product_id,
                    'product_name': item.display_name,
                    'sku': item.sku,
                    'quantity': item.quantity,
                    'unit_price': str(item.unit_price),
                    'total_amount': str(item.total_amount),
                    'is_custom': item.product_id is None,
                }
                for item in sale.items.all()
            ]
            c_data['recent_sales'].append({
                'id': sale.pk,
                'code': f'SALE-{sale.pk:05d}',
                'date': timezone.localtime(sale.sold_at, BD_TZ).strftime('%d %b %Y'),
                'total_amount': str(sale.total_amount),
                'paid_amount': str(sale.effective_paid_amount),
                'due_amount': str(sale.due_amount),
                'payment_status': sale.payment_status,
                'status_display': sale.get_payment_status_display(),
                'items': items_list,
            })

    results = [
        {
            'customer_name': c['customer_name'],
            'customer_phone': c['customer_phone'],
            'customer_address': c['customer_address'],
            'total_orders': c['total_orders'],
            'total_spent': float(c['total_spent']),
            'total_paid': float(c['total_paid']),
            'total_due': float(c['total_due']),
            'last_order_date': c['last_order_date'],
            'recent_sales': c['recent_sales'],
        }
        for c in list(customers_map.values())[:10]
    ]

    return JsonResponse({'results': results})


def _get_date_range_for_period(period):
    """Calculate start/end dates and label for a given period in BD time."""
    now = timezone.now().astimezone(BD_TZ)
    midnight = {'hour': 0, 'minute': 0, 'second': 0, 'microsecond': 0}
    end_of_day = {'hour': 23, 'minute': 59, 'second': 59, 'microsecond': 999999}

    if period == "today":
        start = now.replace(**midnight)
        end = now.replace(**end_of_day)
        label = f"Today ({start.strftime('%b %d, %Y')})"

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
        start = now.replace(**midnight)
        end = now.replace(**end_of_day)
        label = f"Today ({start.strftime('%b %d, %Y')})"

    return start, end, label


def _serialize_product_sales_data(items):
    """Convert product sales queryset results to dict format for report."""
    return [
        {
            "product__name": item.get("resolved_name") or item.get("product__name") or "Custom Item",
            "product__sku": item.get("resolved_sku") or item.get("product__sku") or "—",
            "total_qty": item["total_qty"] or 0,
            "total_sales": float(item["total_sales"] or 0),
        }
        for item in items
    ]


def _build_customer_statement_data(request):
    """Compile customer transaction history, aggregates, and selective filters."""
    customer_query = request.GET.get('customer', '').strip()
    phone_query = request.GET.get('phone', '').strip()
    status_filter = request.GET.get('status', 'all').lower()
    selected_ids = request.GET.get('ids', '').strip()

    sales_qs = Sale.objects.prefetch_related('items__product').order_by('sold_at')

    if selected_ids:
        id_list = [int(i.strip()) for i in selected_ids.split(',') if i.strip().isdigit()]
        if id_list:
            sales_qs = sales_qs.filter(pk__in=id_list)
    elif customer_query:
        sales_qs = sales_qs.filter(
            models.Q(customer_name__iexact=customer_query) |
            models.Q(customer_name__icontains=customer_query) |
            models.Q(customer_phone__icontains=customer_query)
        )
    elif phone_query:
        sales_qs = sales_qs.filter(customer_phone__icontains=phone_query)

    if status_filter == 'paid':
        sales_qs = sales_qs.filter(payment_status='PAID')
        filter_label = 'Paid Invoices Only'
    elif status_filter == 'partial':
        sales_qs = sales_qs.filter(payment_status='PARTIAL')
        filter_label = 'Partial Payments Only'
    elif status_filter == 'unpaid':
        sales_qs = sales_qs.filter(payment_status='UNPAID')
        filter_label = 'Unpaid (Due) Invoices Only'
    else:
        filter_label = 'All Transactions (Paid, Partial & Due)'

    sales = list(sales_qs)

    # Detect distinct customers in the selection
    distinct_customers = {}
    for s in sales:
        c_name = (s.customer_name or '').strip()
        display_cname = c_name if c_name else 'Walk-in Customer'
        distinct_customers.setdefault(display_cname, []).append(s)

    has_single_named_customer = (len(distinct_customers) == 1 and 'Walk-in Customer' not in distinct_customers)

    if customer_query:
        primary_customer = customer_query
        primary_phone = phone_query or (sales[0].customer_phone if sales and sales[0].customer_phone else '')
        primary_address = sales[0].customer_address if sales and sales[0].customer_address else ''
        is_multi_customer = False
    elif has_single_named_customer:
        first_cust = list(distinct_customers.keys())[0]
        primary_customer = first_cust
        first_sale = distinct_customers[first_cust][0]
        primary_phone = first_sale.customer_phone or ''
        primary_address = first_sale.customer_address or ''
        is_multi_customer = False
    elif len(sales) == 1:
        first_sale = sales[0]
        primary_customer = first_sale.customer_name or 'Walk-in Customer'
        primary_phone = first_sale.customer_phone or ''
        primary_address = first_sale.customer_address or ''
        is_multi_customer = False
    else:
        is_multi_customer = True
        cust_count = len(distinct_customers)
        primary_customer = f"Consolidated Ledger ({cust_count} Accounts)" if cust_count > 0 else "Consolidated Ledger"
        primary_phone = ""
        primary_address = ""

    items = []
    total_billed = Decimal('0.00')
    total_paid = Decimal('0.00')
    total_due = Decimal('0.00')

    for sale in sales:
        sale_total = sale.total_amount
        sale_paid = sale.effective_paid_amount
        sale_due = sale.due_amount

        total_billed += sale_total
        total_paid += sale_paid
        total_due += sale_due

        c_name = (sale.customer_name or '').strip() or 'Walk-in Customer'

        for item in sale.items.all():
            items.append({
                'sale_id': sale.pk,
                'sale_code': f'SALE-{sale.pk:05d}',
                'date': timezone.localtime(sale.sold_at, BD_TZ).strftime('%d %b %Y'),
                'customer_name': c_name,
                'customer_phone': sale.customer_phone or '',
                'customer_address': sale.customer_address or '',
                'product_name': item.display_name,
                'sku': item.sku or '—',
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'total_amount': float(item.total_amount),
                'status': sale.payment_status,
                'is_paid': sale.is_paid,
                'is_partial': sale.is_partial,
                'paid_amount': float(sale_paid),
                'due_amount': float(sale_due),
            })

    return {
        'customer_name': primary_customer or 'Valued Customer',
        'customer_phone': primary_phone,
        'customer_address': primary_address,
        'is_multi_customer': is_multi_customer,
        'distinct_customer_count': len(distinct_customers),
        'filter_label': filter_label,
        'status_filter': status_filter,
        'generated_at': timezone.now().astimezone(BD_TZ).strftime('%d %b %Y, %I:%M %p'),
        'sales_count': len(sales),
        'items_count': len(items),
        'total_billed': float(total_billed),
        'total_paid': float(total_paid),
        'total_due': float(total_due),
        'items': items,
        'sales': sales,
        'customer_query': customer_query,
        'selected_ids': selected_ids,
        'qr_code_b64': _generate_qr_base64(MAPS_URL),
    }


# ─── Views ──────────────────────────────────────────────────

def sale_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all').lower()
    period = request.GET.get('period', 'all').lower()
    sort_by = request.GET.get('sort', 'newest').lower()

    now = timezone.now().astimezone(BD_TZ)
    midnight = {'hour': 0, 'minute': 0, 'second': 0, 'microsecond': 0}
    end_of_day = {'hour': 23, 'minute': 59, 'second': 59, 'microsecond': 999999}

    sales = Sale.objects.prefetch_related('items__product')

    # Date Period Filter
    if period == 'today':
        start = now.replace(**midnight)
        end = now.replace(**end_of_day)
        sales = sales.filter(sold_at__gte=start, sold_at__lte=end)
    elif period == 'week':
        from datetime import timedelta
        start = (now - timedelta(days=6)).replace(**midnight)
        end = now.replace(**end_of_day)
        sales = sales.filter(sold_at__gte=start, sold_at__lte=end)
    elif period == 'month':
        start = now.replace(day=1, **midnight)
        last_day = calendar.monthrange(now.year, now.month)[1]
        end = now.replace(day=last_day, **end_of_day)
        sales = sales.filter(sold_at__gte=start, sold_at__lte=end)
    elif period == 'year':
        start = now.replace(month=1, day=1, **midnight)
        end = now.replace(month=12, day=31, **end_of_day)
        sales = sales.filter(sold_at__gte=start, sold_at__lte=end)

    # Search Query
    if query:
        q_filter = (
            models.Q(customer_name__icontains=query) |
            models.Q(customer_phone__icontains=query) |
            models.Q(customer_address__icontains=query) |
            models.Q(items__product__name__icontains=query) |
            models.Q(items__custom_name__icontains=query)
        )
        clean_digits = re.sub(r'[^\d]', '', query)
        if clean_digits:
            try:
                sale_id = int(clean_digits)
                q_filter |= models.Q(pk=sale_id)
            except ValueError:
                pass
        sales = sales.filter(q_filter).distinct()

    # Pre-calculate counts for filter tabs within current period/search
    count_all = sales.count()
    count_paid = sales.filter(payment_status='PAID').count()
    count_partial = sales.filter(payment_status='PARTIAL').count()
    count_unpaid = sales.filter(payment_status='UNPAID').count()

    # Apply Status Filter
    if status_filter == 'paid':
        sales = sales.filter(payment_status='PAID')
    elif status_filter == 'partial':
        sales = sales.filter(payment_status='PARTIAL')
    elif status_filter == 'unpaid':
        sales = sales.filter(payment_status='UNPAID')

    all_current_sales = list(sales)

    # Sorting
    if sort_by == 'oldest':
        all_current_sales.sort(key=lambda s: s.sold_at)
    elif sort_by == 'amount_desc':
        all_current_sales.sort(key=lambda s: s.total_amount, reverse=True)
    elif sort_by == 'amount_asc':
        all_current_sales.sort(key=lambda s: s.total_amount)
    elif sort_by == 'customer':
        all_current_sales.sort(key=lambda s: (s.customer_name or '').lower())
    else:  # newest default
        all_current_sales.sort(key=lambda s: s.sold_at, reverse=True)

    receipt_sale = None
    receipt_pk = request.GET.get('receipt')
    if receipt_pk:
        receipt_sale = Sale.objects.filter(pk=receipt_pk).first()

    return render(request, 'sales/list.html', {
        'sales': all_current_sales,
        'query': query,
        'status_filter': status_filter,
        'period': period,
        'sort_by': sort_by,
        'count_all': count_all,
        'count_paid': count_paid,
        'count_partial': count_partial,
        'count_unpaid': count_unpaid,
        'receipt_sale': receipt_sale,
    })


def sale_create(request):
    form = SaleForm(request.POST or None)
    formset = SaleItemFormSet(request.POST or None, instance=Sale())
    
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        try:
            user = request.user if request.user.is_authenticated else None
            sale = InventoryService.create_sale(
                customer_name=form.cleaned_data.get('customer_name', ''),
                customer_phone=form.cleaned_data.get('customer_phone', ''),
                customer_address=form.cleaned_data.get('customer_address', ''),
                payment_status=form.cleaned_data.get('payment_status', 'PAID'),
                paid_amount=form.cleaned_data.get('paid_amount', Decimal('0.00')),
                user=user,
                items=[
                    {
                        'product': item.product,
                        'custom_name': item.custom_name,
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                    }
                    for item in formset.save(commit=False)
                ],
            )
            messages.success(request, f'Sale #{sale.pk} saved. Receipt opened in a new page.')
            return redirect(f'{reverse("sales:list")}?receipt={sale.pk}')
        except ValueError as exc:
            form.add_error(None, f"Stock error: {str(exc)}")

    return render(request, 'sales/form.html', {
        'form': form,
        'formset': formset,
        'title': 'New Sale',
        'products_catalog': _build_products_catalog(),
        'customers_catalog': _build_customer_suggestions(),
    })


def sale_toggle_payment_status(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if sale.payment_status == 'PAID':
        sale.payment_status = 'UNPAID'
        sale.paid_amount = Decimal('0.00')
    else:
        sale.payment_status = 'PAID'
        sale.paid_amount = sale.total_amount
    sale.save(update_fields=['payment_status', 'paid_amount'])
    messages.success(request, f'Sale #{sale.pk} marked as {sale.get_payment_status_display()}.')
    next_url = request.POST.get('next') or request.GET.get('next') or reverse('sales:list')
    return redirect(next_url)


def _get_customer_previous_history(sale):
    """
    Returns previous order statistics and previous items for returning customers prior to this sale.
    Returns None if this is a first-time customer or Walk-in.
    """
    c_name = (sale.customer_name or '').strip()
    c_phone = (sale.customer_phone or '').strip()

    if not c_name and not c_phone:
        return None
    if c_name.lower() in ('walk-in', 'walk-in customer', 'walk in', 'cash'):
        return None

    # Match previous sales by customer name or phone (before current sale)
    q = models.Q()
    if c_name:
        q |= models.Q(customer_name__iexact=c_name)
    if c_phone:
        q |= models.Q(customer_phone=c_phone)

    prev_sales_qs = Sale.objects.filter(q).exclude(pk=sale.pk)
    if sale.sold_at and sale.pk:
        prev_sales_qs = prev_sales_qs.filter(
            models.Q(sold_at__lt=sale.sold_at) | models.Q(sold_at=sale.sold_at, pk__lt=sale.pk)
        )

    prev_sales = list(prev_sales_qs.prefetch_related('items__product').order_by('-sold_at'))
    if not prev_sales:
        return None

    prev_orders_count = len(prev_sales)
    prev_total_billed = sum(s.total_amount for s in prev_sales)
    prev_total_paid = sum(s.effective_paid_amount for s in prev_sales)
    prev_total_due = sum(s.due_amount for s in prev_sales)
    current_due = sale.due_amount
    net_due = prev_total_due + current_due

    recent_prev_orders = []
    for ps in prev_sales[:3]:
        items_summary = ', '.join([item.display_name for item in ps.items.all()[:3]])
        recent_prev_orders.append({
            'id': ps.pk,
            'code': f'SALE-{ps.pk:05d}',
            'date': timezone.localtime(ps.sold_at, BD_TZ).strftime('%d %b %Y'),
            'total': ps.total_amount,
            'paid': ps.effective_paid_amount,
            'due': ps.due_amount,
            'status': ps.get_payment_status_display(),
            'items_summary': items_summary,
        })

    return {
        'has_previous_orders': True,
        'previous_orders_count': prev_orders_count,
        'previous_total_billed': prev_total_billed,
        'previous_total_paid': prev_total_paid,
        'previous_total_due': prev_total_due,
        'current_due': current_due,
        'net_due': net_due,
        'recent_previous_orders': recent_prev_orders,
        'last_previous_order_date': recent_prev_orders[0]['date'] if recent_prev_orders else None,
    }


def sale_receipt_print(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__product'),
        pk=pk
    )
    qr_code_b64 = _generate_qr_base64(MAPS_URL)
    prev_history = _get_customer_previous_history(sale)
    return render(request, 'sales/receipt.html', {
        'sale': sale,
        'qr_code_b64': qr_code_b64,
        'prev_history': prev_history,
    })


def sale_receipt_pdf(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__product'), 
        pk=pk
    )
    prev_history = _get_customer_previous_history(sale)
    response = HttpResponse(build_sale_receipt_pdf(sale, prev_history=prev_history), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="sale-{sale.pk}-receipt.pdf"'
    return response


def customer_statement_view(request):
    """View customer statement in HTML with options to filter or print/export."""
    data = _build_customer_statement_data(request)
    return render(request, 'sales/customer_statement.html', data)


def customer_statement_pdf(request):
    """Download consolidated customer statement PDF for all/selective paid/unpaid items."""
    data = _build_customer_statement_data(request)
    pdf_bytes = build_customer_statement_pdf(data)
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', data['customer_name']) or 'Customer'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="statement-{safe_name}.pdf"'
    return response


def sales_report_pdf(request):
    period = request.GET.get("period", "today")
    start_date, end_date, period_label = _get_date_range_for_period(period)

    # Base querysets
    sales_qs = Sale.objects.filter(sold_at__range=(start_date, end_date)).prefetch_related("items")
    items_qs = (
        SaleItem.objects
        .filter(sale__sold_at__range=(start_date, end_date))
        .select_related("product")
    )

    # Summary metrics
    sales_list = list(sales_qs)
    total_transactions = len(sales_list)
    total_revenue = sum(s.total_amount for s in sales_list)
    total_paid = sum(s.effective_paid_amount for s in sales_list)
    total_due = sum(s.due_amount for s in sales_list)
    total_items_sold = sum(item.quantity for item in items_qs)

    # Product-level aggregation (handling both catalog and custom items)
    product_sales_qs = (
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
        .order_by("-total_qty")
    )

    product_sales = list(product_sales_qs)

    sales_transactions = []
    for s in sales_list:
        items_summary = ", ".join([f"{item.display_name} (x{item.quantity})" for item in s.items.all()[:2]])
        extra_count = s.items.count() - 2
        if extra_count > 0:
            items_summary += f" +{extra_count}"
        sales_transactions.append({
            "id": s.pk,
            "code": f"SALE-{s.pk:05d}",
            "date": timezone.localtime(s.sold_at, BD_TZ).strftime("%d %b %I:%M %p"),
            "customer_name": (s.customer_name or "Walk-in Customer")[:18],
            "customer_phone": (s.customer_phone or "—")[:12],
            "items_summary": items_summary[:30],
            "total_amount": float(s.total_amount),
            "paid_amount": float(s.effective_paid_amount),
            "due_amount": float(s.due_amount),
            "payment_status": s.payment_status,
            "status_display": s.get_payment_status_display(),
        })

    # Build report data
    report_data = {
        "period_label": period_label,
        "generated_at": timezone.now().astimezone(BD_TZ).strftime("%Y-%m-%d %H:%M"),
        "total_revenue": float(total_revenue or 0),
        "total_paid": float(total_paid or 0),
        "total_due": float(total_due or 0),
        "total_items_sold": total_items_sold,
        "total_transactions": total_transactions,
        "sales_transactions": sales_transactions,
        "top_selling": _serialize_product_sales_data(product_sales[:5]),
        "product_sales": _serialize_product_sales_data(product_sales),
    }

    pdf_bytes = build_sales_report_pdf(report_data)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="sales-report-{period}.pdf"'
    return response