"""Inventory PDF reports generator for stock levels, new products, and quantity updates with executive styling."""

from __future__ import annotations

import datetime
from typing import Any, List

from django.utils import timezone
import pytz

from sales.pdf import (
    INTLISOFT_EMAIL,
    INTLISOFT_PHONE,
    MAPS_URL,
    MTRONIX_ADDRESS,
    MTRONIX_EMAIL,
    MTRONIX_PHONE,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    PageComposer,
    PdfBuilder,
    _badge,
    _bd_now,
    _bd_time,
    _build_qr_matrix,
    _divider,
    _line,
    _make_footer_ops,
    _qr_pdf_stream,
    _rect_card,
    _rect_fill,
    _render_kpi_cards,
    _sanitize_text,
    _text_line,
    _text_right,
)

BD_TZ = pytz.timezone('Asia/Dhaka')


def _render_inventory_header_top(
    doc_title: str,
    period_label: str,
    generated: str,
    qr_matrix: List[List[bool]],
    qr_cell: float = 1.05,
) -> List[str]:
    """Render the standard top brand banner for inventory reports."""
    ops: List[str] = [
        _text_line(762, 'MTRONIX', 20, 54, bold=True, r=0.06, g=0.09, b=0.16),
        _text_line(748, doc_title.upper(), 8.5, 54, bold=True, r=0.06, g=0.46, b=0.43),
        _text_line(735, f'Period: {period_label}  |  Generated: {generated}', 8, 54, r=0.39, g=0.45, b=0.55),
        _text_line(723, f'Address: {MTRONIX_ADDRESS}', 8, 54, r=0.39, g=0.45, b=0.55),
    ]

    if qr_matrix:
        qr_size = len(qr_matrix) * qr_cell
        card_w = qr_size + 14
        card_h = qr_size + 20
        card_x = 558 - card_w
        card_y = 712
        qr_x = card_x + 7
        qr_y = card_y + 4
        ops.append(_rect_card(card_x, card_y, card_w, card_h, bg=(0.98, 0.99, 1.0), border=(0.85, 0.88, 0.92)))
        ops.append(_text_line(card_y + card_h - 10, 'SCAN LOCATION', 6.0, card_x + 4, bold=True, r=0.39, g=0.45, b=0.55))
        ops.append(_qr_pdf_stream(qr_matrix, qr_x, qr_y, qr_cell))

    ops.append(_line(54, 710, 558, 710, r=0.06, g=0.09, b=0.16, width=1.5))
    return ops


# ── 1. Current Stock Summary PDF ─────────────────────────────────────────────
def build_inventory_stock_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate multi-page PDF for complete current stock inventory with executive styling."""
    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell = 1.05

    raw_dt = report_data.get('generated_at')
    generated = raw_dt if isinstance(raw_dt, str) and raw_dt else _bd_now()
    period_label = report_data.get("period_label", "Current Stock")

    def header(page_no: int) -> List[str]:
        ops = []
        if page_no == 1:
            ops.extend(_render_inventory_header_top(
                'Complete Inventory Stock Report',
                period_label,
                generated,
                qr_matrix,
                qr_cell,
            ))

            # 4 KPI Cards
            kpis = [
                ('Total Products', str(report_data.get("total_products", 0)), (0.06, 0.46, 0.43)),
                ('Total Units', str(report_data.get("total_units", 0)), (0.02, 0.37, 0.27)),
                ('Stock Value', f'BDT {report_data.get("total_value", 0.0):.2f}', (0.06, 0.09, 0.16)),
                ('Low Stock Alert', str(report_data.get("low_stock_count", 0)), (0.60, 0.11, 0.11) if report_data.get("low_stock_count", 0) > 0 else (0.06, 0.46, 0.43)),
            ]
            ops.extend(_render_kpi_cards(656, kpis, h=44))

            curr_y = 638
            # Dark Slate Table Header
            ops.append(_rect_fill(54, curr_y - 4, 504, 20, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(curr_y + 2, 'PRODUCT NAME', 8, 64, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 2, 'SKU', 8, 220, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'PURCHASE (BDT)', 8, 345, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'SELLING (BDT)', 8, 420, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'STOCK QTY', 8, 475, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'TOTAL VAL (BDT)', 8, 550, bold=True, r=1.0, g=1.0, b=1.0))
        else:
            ops.append(_text_line(760, f'Mtronix Inventory Stock Report (Page {page_no})', 9, 54, bold=True, r=0.39, g=0.45, b=0.55))
            ops.append(_line(54, 750, 558, 750, r=0.88, g=0.91, b=0.94, width=0.75))
            curr_y = 732
            ops.append(_rect_fill(54, curr_y - 4, 504, 18, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(curr_y + 1, 'PRODUCT NAME', 8, 64, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 1, 'SKU', 8, 220, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'PURCHASE (BDT)', 8, 345, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'SELLING (BDT)', 8, 420, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'STOCK QTY', 8, 475, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'TOTAL VAL (BDT)', 8, 550, bold=True, r=1.0, g=1.0, b=1.0))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    items = report_data.get('items', [])
    if not items:
        pc.ensure(40)
        pc.add_line('No inventory items found.', 10, r=0.39, g=0.45, b=0.55)
    else:
        for idx, it in enumerate(items):
            pc.ensure(18)
            y = pc.y
            if idx % 2 == 1:
                pc._streams.append(_rect_fill(54, y - 4, 504, 18, 0.975, 0.985, 0.995))
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.90, 0.92, 0.95, 0.5))

            name_str = _sanitize_text(it['name'])[:24]
            sku_str = _sanitize_text(it.get('sku') or '-')[:12]
            p_price = f"{it['purchase_price']:.2f}"
            s_price = f"{it['selling_price']:.2f}"
            qty_val = it['quantity']
            tot_val = f"{it['total_value']:.2f}"
            is_low = (qty_val <= it.get('low_stock_threshold', 5))

            pc._streams.append(_text_line(y, name_str, 8.5, 64, bold=True, r=0.06, g=0.09, b=0.16))
            pc._streams.append(_text_line(y, sku_str, 8, 220, r=0.39, g=0.45, b=0.55))
            pc._streams.append(_text_right(y, p_price, 8.5, 345, r=0.06, g=0.09, b=0.16))
            pc._streams.append(_text_right(y, s_price, 8.5, 420, r=0.06, g=0.09, b=0.16))

            if is_low:
                pc._streams.append(_text_right(y, str(qty_val), 9, 475, bold=True, r=0.60, g=0.11, b=0.11))
            else:
                pc._streams.append(_text_right(y, str(qty_val), 8.5, 475, r=0.06, g=0.09, b=0.16))

            pc._streams.append(_text_right(y, tot_val, 8.5, 550, bold=True, r=0.06, g=0.09, b=0.16))
            pc.skip(18)

    pc.finish()
    return builder.build()


# ── 2. Today's / New Added Products PDF ──────────────────────────────────────
def build_new_products_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate multi-page PDF for newly added catalog products with executive styling."""
    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell = 1.05

    raw_dt = report_data.get('generated_at')
    generated = raw_dt if isinstance(raw_dt, str) and raw_dt else _bd_now()
    period_label = report_data.get("period_label", "Recent Additions")

    def header(page_no: int) -> List[str]:
        ops = []
        if page_no == 1:
            ops.extend(_render_inventory_header_top(
                'New Added Products Catalog Report',
                period_label,
                generated,
                qr_matrix,
                qr_cell,
            ))

            kpis = [
                ('New Products', str(report_data.get("total_new_products", 0)), (0.06, 0.46, 0.43)),
                ('Total Units Added', str(report_data.get("total_units", 0)), (0.02, 0.37, 0.27)),
                ('Total Cost Value', f'BDT {report_data.get("total_cost", 0.0):.2f}', (0.06, 0.09, 0.16)),
            ]
            ops.extend(_render_kpi_cards(656, kpis, h=44))

            curr_y = 638
            ops.append(_rect_fill(54, curr_y - 4, 504, 20, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(curr_y + 2, 'ADDED TIME', 8, 64, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 2, 'PRODUCT NAME', 8, 150, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 2, 'SKU', 8, 290, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'PURCHASE (BDT)', 8, 395, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'SELLING (BDT)', 8, 475, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'INITIAL STOCK', 8, 550, bold=True, r=1.0, g=1.0, b=1.0))
        else:
            ops.append(_text_line(760, f'Mtronix New Products Report (Page {page_no})', 9, 54, bold=True, r=0.39, g=0.45, b=0.55))
            ops.append(_line(54, 750, 558, 750, r=0.88, g=0.91, b=0.94, width=0.75))
            curr_y = 732
            ops.append(_rect_fill(54, curr_y - 4, 504, 18, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(curr_y + 1, 'ADDED TIME', 8, 64, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 1, 'PRODUCT NAME', 8, 150, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 1, 'SKU', 8, 290, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'PURCHASE (BDT)', 8, 395, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'SELLING (BDT)', 8, 475, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'INITIAL STOCK', 8, 550, bold=True, r=1.0, g=1.0, b=1.0))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    products = report_data.get('products', [])
    if not products:
        pc.ensure(40)
        pc.add_line('No new products added in this period.', 10, r=0.39, g=0.45, b=0.55)
    else:
        for idx, p in enumerate(products):
            pc.ensure(18)
            y = pc.y
            if idx % 2 == 1:
                pc._streams.append(_rect_fill(54, y - 4, 504, 18, 0.975, 0.985, 0.995))
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.90, 0.92, 0.95, 0.5))

            time_str = _sanitize_text(str(p['created_at'])[:16])
            name_str = _sanitize_text(p['name'])[:22]
            sku_str = _sanitize_text(p.get('sku') or '-')[:12]
            p_price = f"{p['purchase_price']:.2f}"
            s_price = f"{p['selling_price']:.2f}"
            stk_str = str(p['current_stock'])

            pc._streams.append(_text_line(y, time_str, 8, 64, r=0.28, g=0.33, b=0.41))
            pc._streams.append(_text_line(y, name_str, 8.5, 150, bold=True, r=0.06, g=0.09, b=0.16))
            pc._streams.append(_text_line(y, sku_str, 8, 290, r=0.39, g=0.45, b=0.55))
            pc._streams.append(_text_right(y, p_price, 8.5, 395, r=0.06, g=0.09, b=0.16))
            pc._streams.append(_text_right(y, s_price, 8.5, 475, r=0.06, g=0.09, b=0.16))
            pc._streams.append(_text_right(y, stk_str, 8.5, 550, bold=True, r=0.06, g=0.46, b=0.43))
            pc.skip(18)

    pc.finish()
    return builder.build()


# ── 3. Stock / Quantity Updates PDF ──────────────────────────────────────────
def build_stock_updates_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate multi-page PDF for updated inventory stock and quantity changes with executive styling."""
    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell = 1.05

    raw_dt = report_data.get('generated_at')
    generated = raw_dt if isinstance(raw_dt, str) and raw_dt else _bd_now()
    period_label = report_data.get("period_label", "Recent Quantity Updates")

    def header(page_no: int) -> List[str]:
        ops = []
        if page_no == 1:
            ops.extend(_render_inventory_header_top(
                'Stock & Quantity Updates Audit Report',
                period_label,
                generated,
                qr_matrix,
                qr_cell,
            ))

            kpis = [
                ('Updated Items', str(report_data.get("total_updated_items", 0)), (0.06, 0.46, 0.43)),
                ('Total Units', str(report_data.get("total_units", 0)), (0.02, 0.37, 0.27)),
                ('Total Value', f'BDT {report_data.get("total_value", 0.0):.2f}', (0.06, 0.09, 0.16)),
            ]
            ops.extend(_render_kpi_cards(656, kpis, h=44))

            curr_y = 638
            ops.append(_rect_fill(54, curr_y - 4, 504, 20, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(curr_y + 2, 'UPDATED TIME', 8, 64, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 2, 'PRODUCT NAME', 8, 155, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 2, 'SKU', 8, 295, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'QUANTITY', 8, 410, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'LOW LIMIT', 8, 475, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'TOTAL VAL (BDT)', 8, 550, bold=True, r=1.0, g=1.0, b=1.0))
        else:
            ops.append(_text_line(760, f'Mtronix Stock Updates Report (Page {page_no})', 9, 54, bold=True, r=0.39, g=0.45, b=0.55))
            ops.append(_line(54, 750, 558, 750, r=0.88, g=0.91, b=0.94, width=0.75))
            curr_y = 732
            ops.append(_rect_fill(54, curr_y - 4, 504, 18, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(curr_y + 1, 'UPDATED TIME', 8, 64, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 1, 'PRODUCT NAME', 8, 155, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 1, 'SKU', 8, 295, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'QUANTITY', 8, 410, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'LOW LIMIT', 8, 475, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'TOTAL VAL (BDT)', 8, 550, bold=True, r=1.0, g=1.0, b=1.0))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    items = report_data.get('items', [])
    if not items:
        pc.ensure(40)
        pc.add_line('No stock quantity updates recorded in this period.', 10, r=0.39, g=0.45, b=0.55)
    else:
        for idx, it in enumerate(items):
            pc.ensure(18)
            y = pc.y
            if idx % 2 == 1:
                pc._streams.append(_rect_fill(54, y - 4, 504, 18, 0.975, 0.985, 0.995))
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.90, 0.92, 0.95, 0.5))

            time_str = _sanitize_text(str(it['updated_at'])[:16])
            name_str = _sanitize_text(it['name'])[:22]
            sku_str = _sanitize_text(it.get('sku') or '-')[:12]
            qty_val = it['quantity']
            limit_val = it.get('low_stock_threshold', 5)
            tot_val = f"{it['total_value']:.2f}"

            pc._streams.append(_text_line(y, time_str, 8, 64, r=0.28, g=0.33, b=0.41))
            pc._streams.append(_text_line(y, name_str, 8.5, 155, bold=True, r=0.06, g=0.09, b=0.16))
            pc._streams.append(_text_line(y, sku_str, 8, 295, r=0.39, g=0.45, b=0.55))
            pc._streams.append(_text_right(y, str(qty_val), 8.5, 410, bold=True, r=0.06, g=0.09, b=0.16))
            pc._streams.append(_text_right(y, str(limit_val), 8, 475, r=0.39, g=0.45, b=0.55))
            pc._streams.append(_text_right(y, tot_val, 8.5, 550, bold=True, r=0.06, g=0.09, b=0.16))
            pc.skip(18)

    pc.finish()
    return builder.build()
