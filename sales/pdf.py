from django.utils import timezone


def _pdf_text(value):
    return str(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _text_line(y, text, size=11, x=72):
    escaped = _pdf_text(text)
    return f'BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET'


def _assemble_pdf(lines):
    content = '\n'.join(lines).encode('latin-1', errors='replace')
    stream = (
        b'4 0 obj\n'
        b'<< /Length ' + str(len(content)).encode('ascii') + b' >>\n'
        b'stream\n' + content + b'\nendstream\nendobj\n'
    )
    objects = [
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n',
        stream,
        b'5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
    ]

    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_position = len(pdf)
    pdf.extend(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    pdf.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    pdf.extend(
        b'trailer\n'
        + f'<< /Size {len(objects) + 1} /Root 1 0 R >>\n'.encode('ascii')
        + b'startxref\n'
        + str(xref_position).encode('ascii')
        + b'\n%%EOF\n'
    )
    return bytes(pdf)


def build_sale_receipt_pdf(sale):
    sold_at = timezone.localtime(sale.sold_at).strftime('%Y-%m-%d %H:%M')
    customer = sale.customer_name or 'Walk-in'
    lines = [
        _text_line(760, 'Mtronix Sales Receipt', 18),
        _text_line(730, f'Receipt No: SALE-{sale.pk:05d}', 12),
        _text_line(712, f'Date: {sold_at}', 12),
        _text_line(694, f'Customer: {customer}', 12),
        _text_line(660, 'Item', 12),
        _text_line(660, 'SKU', 12, 270),
        _text_line(660, 'Qty', 12, 370),
        _text_line(660, 'Unit Price', 12, 430),
        _text_line(660, 'Total', 12, 520),
        _text_line(642, '-' * 86, 10),
    ]

    y = 620
    for item in sale.items.all():
        lines.extend([
            _text_line(y, item.product.name, 11),
            _text_line(y, item.product.sku, 11, 270),
            _text_line(y, item.quantity, 11, 370),
            _text_line(y, f'{item.unit_price:.2f}', 11, 430),
            _text_line(y, f'{item.total_amount:.2f}', 11, 520),
        ])
        y -= 20
        if y < 120:
            break

    lines.extend([
        _text_line(y, '-' * 86, 10),
        _text_line(y - 30, f'Total Amount: {sale.total_amount:.2f}', 14, 390),
        _text_line(y - 70, 'Thank you for your purchase.', 12),
    ])

    return _assemble_pdf(lines)


def build_sales_report_pdf(report_data):
    lines = [
        _text_line(760, 'Mtronix Sales Summary Report', 18),
        _text_line(730, f'Period: {report_data["period_label"]}', 12),
        _text_line(712, f'Generated: {report_data["generated_at"]}', 10),
        _text_line(695, '-' * 86, 10),
        
        # Summary Metrics
        _text_line(675, f'Total Revenue: ${report_data["total_revenue"]:.2f}', 12),
        _text_line(675, f'Total Items Sold: {report_data["total_items_sold"]}', 12, 250),
        _text_line(675, f'Transactions: {report_data["total_transactions"]}', 12, 430),
        _text_line(655, '-' * 86, 10),
    ]
    
    # Top Selling Products Section
    lines.append(_text_line(630, 'Top Selling Products (by Quantity)', 14))
    y = 610
    top_selling = report_data['top_selling']
    if not top_selling:
        lines.append(_text_line(y, 'No sales recorded in this period.', 11))
        y -= 20
    else:
        for idx, item in enumerate(top_selling[:5], 1):
            name = item['product__name']
            sku = item['product__sku']
            qty = item['total_qty']
            sales = item['total_sales']
            lines.append(_text_line(y, f'{idx}. {name} ({sku}) - {qty} sold (Total: ${sales:.2f})', 11))
            y -= 20
            
    y -= 10
    lines.append(_text_line(y, '-' * 86, 10))
    y -= 20
    
    # Product Sales Breakdown Section
    lines.append(_text_line(y, 'Product Sales Breakdown', 14))
    y -= 20
    lines.extend([
        _text_line(y, 'Product Name', 11),
        _text_line(y, 'SKU', 11, 270),
        _text_line(y, 'Qty Sold', 11, 370),
        _text_line(y, 'Total Sales', 11, 460),
    ])
    y -= 15
    lines.append(_text_line(y, '-' * 86, 10))
    y -= 18
    
    product_sales = report_data['product_sales']
    if not product_sales:
        lines.append(_text_line(y, 'No product breakdown available.', 11))
    else:
        for item in product_sales[:12]:
            if y < 80:
                break
            lines.extend([
                _text_line(y, item['product__name'], 10),
                _text_line(y, item['product__sku'], 10, 270),
                _text_line(y, item['total_qty'], 10, 370),
                _text_line(y, f"${item['total_sales']:.2f}", 10, 460),
            ])
            y -= 18
            
    lines.append(_text_line(50, 'Mtronix Sales & Inventory System - Confidential Report', 9))
    
    return _assemble_pdf(lines)
