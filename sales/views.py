import calendar
from django.contrib import messages
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.forms import inlineformset_factory
from rest_framework import mixins, viewsets
import base64
import io
import pytz

from inventory.services import InventoryService
from sales.forms import SaleForm, SaleItemForm
from sales.models import Sale, SaleItem
from sales.pdf import MAPS_URL, build_sale_receipt_pdf, build_sales_report_pdf, qrcode
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
    extra=1,
    can_delete=True,
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
            "product__name": item["product__name"],
            "product__sku": item["product__sku"],
            "total_qty": item["total_qty"] or 0,
            "total_sales": float(item["total_sales"] or 0),
        }
        for item in items
    ]


# ─── Views ──────────────────────────────────────────────────

import re

def sale_list(request):
    query = request.GET.get('q', '').strip()
    sales = Sale.objects.prefetch_related('items__product').order_by('-sold_at')
    if query:
        q_filter = models.Q(customer_name__icontains=query) | models.Q(items__product__name__icontains=query)
        clean_digits = re.sub(r'[^\d]', '', query)
        if clean_digits:
            try:
                sale_id = int(clean_digits)
                q_filter |= models.Q(pk=sale_id)
            except ValueError:
                pass
        sales = sales.filter(q_filter).distinct()

    receipt_sale = None
    receipt_pk = request.GET.get('receipt')
    if receipt_pk:
        receipt_sale = Sale.objects.filter(pk=receipt_pk).first()

    return render(request, 'sales/list.html', {
        'sales': sales,
        'query': query,
        'receipt_sale': receipt_sale,
    })


def sale_create(request):
    form = SaleForm(request.POST or None)
    formset = SaleItemFormSet(request.POST or None, instance=Sale())
    
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        try:
            sale = InventoryService.create_sale(
                customer_name=form.cleaned_data.get('customer_name', ''),
                items=[
                    {
                        'product': item.product,
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


def sales_report_pdf(request):
    period = request.GET.get("period", "today")
    start_date, end_date, period_label = _get_date_range_for_period(period)

    # Base querysets
    sales_qs = Sale.objects.filter(sold_at__range=(start_date, end_date))
    items_qs = (
        SaleItem.objects
        .filter(sale__sold_at__range=(start_date, end_date))
        .select_related("product")
    )

    # Summary metrics
    total_transactions = sales_qs.count()
    total_revenue = sum(item.total_amount for item in items_qs)
    total_items_sold = sum(item.quantity for item in items_qs)

    # Product-level aggregation
    product_sales_qs = (
        items_qs
        .values("product__name", "product__sku")
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
        "total_items_sold": total_items_sold,
        "total_transactions": total_transactions,
        "top_selling": _serialize_product_sales_data(product_sales[:5]),
        "product_sales": _serialize_product_sales_data(product_sales),
    }

    pdf_bytes = build_sales_report_pdf(report_data)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="sales-report-{period}.pdf"'
    return response