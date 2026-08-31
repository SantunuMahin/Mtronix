import calendar
from django.contrib import messages
from django.db import models
from django.db.models.functions import Coalesce
from django.http import HttpResponse
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

    sales = Sale.objects.prefetch_related('items__product').order_by('-sold_at')

    if status_filter == 'paid':
        sales = sales.filter(payment_status='PAID')
    elif status_filter == 'partial':
        sales = sales.filter(payment_status='PARTIAL')
    elif status_filter == 'unpaid':
        sales = sales.filter(payment_status='UNPAID')

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

    # Calculate summary metrics for current selection
    all_current_sales = list(sales)
    total_count = len(all_current_sales)
    total_revenue = sum(s.total_amount for s in all_current_sales)
    total_paid = sum(s.effective_paid_amount for s in all_current_sales)
    total_unpaid = sum(s.due_amount for s in all_current_sales)

    receipt_sale = None
    receipt_pk = request.GET.get('receipt')
    if receipt_pk:
        receipt_sale = Sale.objects.filter(pk=receipt_pk).first()

    return render(request, 'sales/list.html', {
        'sales': all_current_sales,
        'query': query,
        'status_filter': status_filter,
        'total_count': total_count,
        'total_revenue': total_revenue,
        'total_paid': total_paid,
        'total_unpaid': total_unpaid,
        'receipt_sale': receipt_sale,
    })


def sale_create(request):
    form = SaleForm(request.POST or None)
    formset = SaleItemFormSet(request.POST or None, instance=Sale())
    
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        try:
            sale = InventoryService.create_sale(
                customer_name=form.cleaned_data.get('customer_name', ''),
                customer_phone=form.cleaned_data.get('customer_phone', ''),
                customer_address=form.cleaned_data.get('customer_address', ''),
                payment_status=form.cleaned_data.get('payment_status', 'PAID'),
                paid_amount=form.cleaned_data.get('paid_amount', Decimal('0.00')),
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


def sale_receipt_print(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__product'),
        pk=pk
    )
    qr_code_b64 = _generate_qr_base64(MAPS_URL)
    return render(request, 'sales/receipt.html', {
        'sale': sale,
        'qr_code_b64': qr_code_b64,
    })


def sale_receipt_pdf(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__product'), 
        pk=pk
    )
    response = HttpResponse(build_sale_receipt_pdf(sale), content_type='application/pdf')
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

    # Build report data
    report_data = {
        "period_label": period_label,
        "generated_at": timezone.now().astimezone(BD_TZ).strftime("%Y-%m-%d %H:%M"),
        "total_revenue": float(total_revenue or 0),
        "total_paid": float(total_paid or 0),
        "total_due": float(total_due or 0),
        "total_items_sold": total_items_sold,
        "total_transactions": total_transactions,
        "top_selling": _serialize_product_sales_data(product_sales[:5]),
        "product_sales": _serialize_product_sales_data(product_sales),
    }

    pdf_bytes = build_sales_report_pdf(report_data)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="sales-report-{period}.pdf"'
    return response