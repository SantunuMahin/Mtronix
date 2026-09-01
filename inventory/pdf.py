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
    _get_logo_image_data,
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
    logo_data: tuple[int, int, bytes] | None = None,
) -> List[str]:
    """Render the standard top brand banner for inventory reports with official logo."""
    ops: List[str] = [
        _text_line(762, 'MTRONIX', 20, 54, bold=True, r=0.0, g=0.0, b=0.0),
        _text_line(748, doc_title.upper(), 8.5, 54, bold=True, r=0.2, g=0.2, b=0.2),
        _text_line(735, f'Period: {period_label}  |  Generated: {generated}', 8, 54, r=0.25, g=0.25, b=0.25),
        _text_line(723, f'Address: {MTRONIX_ADDRESS}', 8, 54, r=0.25, g=0.25, b=0.25),
    ]

    if logo_data:
        ops.append('q 88 0 0 66 470 705 cm /Im1 Do Q')

    ops.append(_line(54, 710, 558, 710, r=0.0, g=0.0, b=0.0, width=1.5))
    return ops


def _append_statement_signatures(pc: PageComposer) -> None:
    if pc.y < 100:
        pc.ensure(70)
    y = 75
    pc._streams.append(_line(54, y, 200, y, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(y - 10, "Manager Signature", 8, 54, bold=True, r=0.0, g=0.0, b=0.0))

    pc._streams.append(_line(390, y, 558, y, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(y - 10, "CEO Abdul Mannan Signature", 8, 390, bold=True, r=0.0, g=0.0, b=0.0))


# ── 1. Current Stock Summary PDF ─────────────────────────────────────────────
def build_inventory_stock_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate multi-page PDF for complete current stock inventory with pure black and white styling."""
    logo_data = _get_logo_image_data()

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
                logo_data,
            ))

            curr_y = 690
            # Clean Table Header with Black Lines
            ops.append(_line(54, curr_y + 12, 558, curr_y + 12, r=0.0, g=0.0, b=0.0, width=1.5))
            ops.append(_text_line(curr_y + 2, 'PRODUCT NAME', 8.5, 64, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 2, 'SKU', 8.5, 305, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'UNIT PRICE (BDT)', 8.5, 430, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'QUANTITY', 8.5, 490, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'TOTAL VAL (BDT)', 8.5, 550, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))
        else:
            ops.append(_text_line(760, f'Mtronix Inventory Stock Report (Page {page_no})', 9, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, 750, 558, 750, r=0.0, g=0.0, b=0.0, width=0.75))
            curr_y = 732
            ops.append(_line(54, curr_y + 10, 558, curr_y + 10, r=0.0, g=0.0, b=0.0, width=1.5))
            ops.append(_text_line(curr_y + 1, 'PRODUCT NAME', 8, 64, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 1, 'SKU', 8, 305, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'UNIT PRICE (BDT)', 8, 430, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'QUANTITY', 8, 490, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'TOTAL VAL (BDT)', 8, 550, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True, image_data=logo_data)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer, page_top=672.0)

    items = report_data.get('items', [])
    if not items:
        pc.ensure(40)
        pc.add_line('No inventory items found.', 10, r=0.25, g=0.25, b=0.25)
    else:
        for idx, it in enumerate(items):
            pc.ensure(18)
            y = pc.y
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.80, 0.80, 0.80, 0.5))

            name_str = _sanitize_text(it['name'])[:34]
            sku_str = _sanitize_text(it.get('sku') or '-')[:14]
            s_price = f"{it['selling_price']:.2f}"
            qty_val = it['quantity']
            tot_val = f"{it['total_value']:.2f}"
            is_low = (qty_val <= it.get('low_stock_threshold', 5))

            pc._streams.append(_text_line(y, name_str, 8.5, 64, bold=True, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_line(y, sku_str, 8, 305, r=0.25, g=0.25, b=0.25))
            pc._streams.append(_text_right(y, s_price, 8.5, 430, r=0.0, g=0.0, b=0.0))

            if is_low:
                pc._streams.append(_text_right(y, str(qty_val), 9, 490, bold=True, r=0.0, g=0.0, b=0.0))
            else:
                pc._streams.append(_text_right(y, str(qty_val), 8.5, 490, r=0.0, g=0.0, b=0.0))

            pc._streams.append(_text_right(y, tot_val, 8.5, 550, bold=True, r=0.0, g=0.0, b=0.0))
            pc.skip(18)

    _append_statement_signatures(pc)
    pc.finish()
    return builder.build()


# ── 2. Today's / New Added Products PDF ──────────────────────────────────────
def build_new_products_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate multi-page PDF for newly added catalog products in pure black & white."""
    logo_data = _get_logo_image_data()

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
                logo_data,
            ))

            curr_y = 690
            ops.append(_line(54, curr_y + 12, 558, curr_y + 12, r=0.0, g=0.0, b=0.0, width=1.5))
            ops.append(_text_line(curr_y + 2, 'ADDED TIME', 8, 64, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 2, 'PRODUCT NAME', 8, 160, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 2, 'SKU', 8, 330, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'UNIT PRICE (BDT)', 8, 460, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'INITIAL STOCK', 8, 550, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))
        else:
            ops.append(_text_line(760, f'Mtronix New Products Report (Page {page_no})', 9, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, 750, 558, 750, r=0.0, g=0.0, b=0.0, width=0.75))
            curr_y = 732
            ops.append(_line(54, curr_y + 10, 558, curr_y + 10, r=0.0, g=0.0, b=0.0, width=1.5))
            ops.append(_text_line(curr_y + 1, 'ADDED TIME', 8, 64, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 1, 'PRODUCT NAME', 8, 160, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 1, 'SKU', 8, 330, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'UNIT PRICE (BDT)', 8, 460, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'INITIAL STOCK', 8, 550, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True, image_data=logo_data)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer, page_top=672.0)

    products = report_data.get('products', [])
    if not products:
        pc.ensure(40)
        pc.add_line('No new products added in this period.', 10, r=0.25, g=0.25, b=0.25)
    else:
        for idx, p in enumerate(products):
            pc.ensure(18)
            y = pc.y
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.80, 0.80, 0.80, 0.5))

            time_str = _sanitize_text(str(p['created_at'])[:16])
            name_str = _sanitize_text(p['name'])[:30]
            sku_str = _sanitize_text(p.get('sku') or '-')[:14]
            s_price = f"{p['selling_price']:.2f}"
            stk_str = str(p['current_stock'])

            pc._streams.append(_text_line(y, time_str, 8, 64, r=0.2, g=0.2, b=0.2))
            pc._streams.append(_text_line(y, name_str, 8.5, 160, bold=True, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_line(y, sku_str, 8, 330, r=0.25, g=0.25, b=0.25))
            pc._streams.append(_text_right(y, s_price, 8.5, 460, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_right(y, stk_str, 8.5, 550, bold=True, r=0.0, g=0.0, b=0.0))
            pc.skip(18)

    _append_statement_signatures(pc)
    pc.finish()
    return builder.build()


# ── 3. Stock / Quantity Updates PDF ──────────────────────────────────────────
def build_stock_updates_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate multi-page PDF for updated inventory stock and quantity changes in pure black & white."""
    logo_data = _get_logo_image_data()

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
                logo_data,
            ))

            curr_y = 690
            ops.append(_line(54, curr_y + 12, 558, curr_y + 12, r=0.0, g=0.0, b=0.0, width=1.5))
            ops.append(_text_line(curr_y + 2, 'UPDATED TIME', 8, 64, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 2, 'PRODUCT NAME', 8, 155, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 2, 'SKU', 8, 295, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'QUANTITY', 8, 410, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'LOW LIMIT', 8, 475, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'TOTAL VAL (BDT)', 8, 550, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))
        else:
            ops.append(_text_line(760, f'Mtronix Stock Updates Report (Page {page_no})', 9, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, 750, 558, 750, r=0.0, g=0.0, b=0.0, width=0.75))
            curr_y = 732
            ops.append(_line(54, curr_y + 10, 558, curr_y + 10, r=0.0, g=0.0, b=0.0, width=1.5))
            ops.append(_text_line(curr_y + 1, 'UPDATED TIME', 8, 64, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 1, 'PRODUCT NAME', 8, 155, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 1, 'SKU', 8, 295, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'QUANTITY', 8, 410, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'LOW LIMIT', 8, 475, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'TOTAL VAL (BDT)', 8, 550, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True, image_data=logo_data)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer, page_top=672.0)

    items = report_data.get('items', [])
    if not items:
        pc.ensure(40)
        pc.add_line('No stock quantity updates recorded in this period.', 10, r=0.25, g=0.25, b=0.25)
    else:
        for idx, it in enumerate(items):
            pc.ensure(18)
            y = pc.y
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.80, 0.80, 0.80, 0.5))

            time_str = _sanitize_text(str(it['updated_at'])[:16])
            name_str = _sanitize_text(it['name'])[:22]
            sku_str = _sanitize_text(it.get('sku') or '-')[:12]
            qty_val = it['quantity']
            limit_val = it.get('low_stock_threshold', 5)
            tot_val = f"{it['total_value']:.2f}"

            pc._streams.append(_text_line(y, time_str, 8, 64, r=0.2, g=0.2, b=0.2))
            pc._streams.append(_text_line(y, name_str, 8.5, 155, bold=True, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_line(y, sku_str, 8, 295, r=0.25, g=0.25, b=0.25))
            pc._streams.append(_text_right(y, str(qty_val), 8.5, 410, bold=True, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_right(y, str(limit_val), 8, 475, r=0.25, g=0.25, b=0.25))
            pc._streams.append(_text_right(y, tot_val, 8.5, 550, bold=True, r=0.0, g=0.0, b=0.0))
            pc.skip(18)

    _append_statement_signatures(pc)
    pc.finish()
    return builder.build()
