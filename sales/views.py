import json
import calendar
from django.db import transaction, models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.forms import inlineformset_factory
from rest_framework import viewsets

from inventory.services import InventoryService
from sales.forms import SaleForm, SaleItemForm
from sales.models import Sale, SaleItem
from sales.pdf import build_sale_receipt_pdf, build_sales_report_pdf
from sales.serializers import SaleSerializer


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.prefetch_related('items__product').order_by('-sold_at')
    serializer_class = SaleSerializer


def sale_list(request):
    query = request.GET.get('q', '')
    sales = Sale.objects.prefetch_related('items__product').order_by('-sold_at')
    if query:
        sales = sales.filter(customer_name__icontains=query)
    return render(request, 'sales/list.html', {'sales': sales, 'query': query})


SaleItemFormSet = inlineformset_factory(
    Sale,
    SaleItem,
    form=SaleItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


def sale_create(request):
    form = SaleForm(request.POST or None)
    formset = SaleItemFormSet(request.POST or None, instance=Sale())
    
    if request.method == 'POST':
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    sale = form.save()
                    formset.instance = sale
                    items = formset.save(commit=False)
                    for item in items:
                        InventoryService.remove_stock(item.product, item.quantity)
                        item.save()
                    formset.save_m2m()
                return redirect('sales:receipt_pdf', pk=sale.pk)
            except ValueError as exc:
                form.add_error(None, f"Stock error: {str(exc)}")

    from products.models import Product
    products_json = json.dumps({p.id: str(p.selling_price) for p in Product.objects.all()})

    return render(request, 'sales/form.html', {
        'form': form,
        'formset': formset,
        'title': 'New Sale',
        'products_json': products_json,
    })


def sale_receipt_pdf(request, pk):
    sale = get_object_or_404(Sale.objects.prefetch_related('items__product'), pk=pk)
    response = HttpResponse(build_sale_receipt_pdf(sale), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="sale-{sale.pk}-receipt.pdf"'
    return response


def get_date_range_for_period(period):
    now = timezone.localtime(timezone.now())
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        label = f"Today ({start.strftime('%b %d, %Y')})"
    elif period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(now.year, now.month)[1]
        end = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
        label = f"This Month ({start.strftime('%B %Y')})"
    elif period == 'year':
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        label = f"This Year ({start.strftime('%Y')})"
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        label = f"Today ({start.strftime('%b %d, %Y')})"
    return start, end, label


def sales_report_pdf(request):
    period = request.GET.get('period', 'today')
    start_date, end_date, period_label = get_date_range_for_period(period)
    
    sales_qs = Sale.objects.filter(sold_at__range=(start_date, end_date))
    total_transactions = sales_qs.count()
    
    items_qs = SaleItem.objects.filter(sale__sold_at__range=(start_date, end_date)).select_related('product')
    
    total_revenue = sum(item.total_amount for item in items_qs)
    total_items_sold = sum(item.quantity for item in items_qs)
    
    product_sales_qs = items_qs.values('product__name', 'product__sku')\
        .annotate(
            total_qty=models.Sum('quantity'),
            total_sales=models.Sum(models.F('quantity') * models.F('unit_price'), output_field=models.DecimalField())
        ).order_by('-total_qty')
        
    product_sales = list(product_sales_qs)
    top_selling = product_sales[:5]
    
    report_data = {
        'period_label': period_label,
        'generated_at': timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M'),
        'total_revenue': float(total_revenue),
        'total_items_sold': total_items_sold,
        'total_transactions': total_transactions,
        'top_selling': [{
            'product__name': item['product__name'],
            'product__sku': item['product__sku'],
            'total_qty': item['total_qty'],
            'total_sales': float(item['total_sales'] or 0)
        } for item in top_selling],
        'product_sales': [{
            'product__name': item['product__name'],
            'product__sku': item['product__sku'],
            'total_qty': item['total_qty'],
            'total_sales': float(item['total_sales'] or 0)
        } for item in product_sales]
    }
    
    pdf_bytes = build_sales_report_pdf(report_data)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="sales-report-{period}.pdf"'
    return response
