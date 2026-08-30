"""Inventory PDF reports generator for stock levels, new products, and quantity updates."""

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
    _bd_now,
    _bd_time,
    _build_qr_matrix,
    _divider,
    _make_footer_ops,
    _text_line,
)

BD_TZ = pytz.timezone('Asia/Dhaka')


def _make_inventory_footer(qr_matrix, qr_cell):
    footer_text_ops = [
        _divider(82, 8),
        _text_line(70, f'Mtronix: {MTRONIX_ADDRESS}', 8),
        _text_line(58, f'Ph: {MTRONIX_PHONE}  |  Email: {MTRONIX_EMAIL}', 8),
        _divider(48, 7),
        _text_line(36, 'Mtronix Sales & Inventory System — Confidential Report', 8),
        _text_line(24, (
            f'Software Provider: Intlisoft Innovation  |  '
            f'Ph: {INTLISOFT_PHONE}  |  Email: {INTLISOFT_EMAIL}'
        ), 8),
    ]

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last, qr_matrix, qr_cell, footer_text_ops)

    return footer


# ── 1. Current Stock Summary PDF ─────────────────────────────────────────────
def build_inventory_stock_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate multi-page PDF for complete current stock inventory."""
    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell = 1.1

    raw_dt = report_data.get('generated_at')
    generated = raw_dt if isinstance(raw_dt, str) and raw_dt else _bd_now()

    footer = _make_inventory_footer(qr_matrix, qr_cell)

    def header(page_no: int) -> List[str]:
        ops = [
            _text_line(760, 'Mtronix Current Inventory Stock Report', 17, bold=True),
            _text_line(738, f'Report Type : Complete Stock Inventory ({report_data.get("period_label", "Current")})', 10),
            _text_line(724, f'Generated   : {generated}', 9),
            _text_line(710, f'Address     : {MTRONIX_ADDRESS}', 8),
            _divider(696),
        ]
        if page_no == 1:
            ops += [
                _text_line(678, f'Total Products: {report_data["total_products"]}', 11, 54, bold=True),
                _text_line(678, f'Total Units: {report_data["total_units"]}', 11, 200, bold=True),
                _text_line(678, f'Stock Value: BDT {report_data["total_value"]:.2f}', 11, 320, bold=True),
                _text_line(678, f'Low Stock: {report_data["low_stock_count"]}', 11, 480, bold=True),
                _divider(662),
            ]
        else:
            ops.append(_text_line(678, f'... continued (page {page_no})', 9))
        return ops

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    # Column headers
    y = pc.y
    pc._streams.append(_text_line(y, 'Product Name',  10,  54, bold=True))
    pc._streams.append(_text_line(y, 'SKU',           10, 235, bold=True))
    pc._streams.append(_text_line(y, 'Purchase (BDT)',10, 310, bold=True))
    pc._streams.append(_text_line(y, 'Selling (BDT)', 10, 385, bold=True))
    pc._streams.append(_text_line(y, 'Qty',           10, 460, bold=True))
    pc._streams.append(_text_line(y, 'Value (BDT)',   10, 505, bold=True))
    pc.skip(16)
    pc.add_divider()
    pc.skip(4)

    items = report_data.get('items', [])
    if not items:
        pc.add_line('No inventory items found.', 11)
    else:
        for it in items:
            pc.ensure(18)
            y = pc.y
            pc._streams.append(_text_line(y, str(it['name'])[:28],          9,  54))
            pc._streams.append(_text_line(y, str(it.get('sku') or '—')[:12], 9, 235))
            pc._streams.append(_text_line(y, f"{it['purchase_price']:.2f}", 9, 310))
            pc._streams.append(_text_line(y, f"{it['selling_price']:.2f}",  9, 385))
            pc._streams.append(_text_line(y, str(it['quantity']),           9, 460, bold=(it['quantity'] <= it.get('low_stock_threshold', 5))))
            pc._streams.append(_text_line(y, f"{it['total_value']:.2f}",    9, 505))
            pc.skip(16)

    pc.finish()
    return builder.build()


# ── 2. Today's / New Added Products PDF ──────────────────────────────────────
def build_new_products_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate multi-page PDF for newly added catalog products."""
    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell = 1.1

    raw_dt = report_data.get('generated_at')
    generated = raw_dt if isinstance(raw_dt, str) and raw_dt else _bd_now()

    footer = _make_inventory_footer(qr_matrix, qr_cell)

    def header(page_no: int) -> List[str]:
        ops = [
            _text_line(760, 'Mtronix New Added Products Report', 17, bold=True),
            _text_line(738, f'Period      : {report_data["period_label"]}', 10),
            _text_line(724, f'Generated   : {generated}', 9),
            _text_line(710, f'Address     : {MTRONIX_ADDRESS}', 8),
            _divider(696),
        ]
        if page_no == 1:
            ops += [
                _text_line(678, f'New Products Added: {report_data["total_new_products"]}', 11, 54, bold=True),
                _text_line(678, f'Total Stock Units: {report_data["total_units"]}', 11, 260, bold=True),
                _text_line(678, f'Total Cost: BDT {report_data["total_cost"]:.2f}', 11, 410, bold=True),
                _divider(662),
            ]
        else:
            ops.append(_text_line(678, f'... continued (page {page_no})', 9))
        return ops

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    # Column headers
    y = pc.y
    pc._streams.append(_text_line(y, 'Added Time',    10,  54, bold=True))
    pc._streams.append(_text_line(y, 'Product Name',  10, 160, bold=True))
    pc._streams.append(_text_line(y, 'SKU',           10, 310, bold=True))
    pc._streams.append(_text_line(y, 'Purchase (BDT)',10, 385, bold=True))
    pc._streams.append(_text_line(y, 'Selling (BDT)', 10, 460, bold=True))
    pc._streams.append(_text_line(y, 'Stock',         10, 525, bold=True))
    pc.skip(16)
    pc.add_divider()
    pc.skip(4)

    products = report_data.get('products', [])
    if not products:
        pc.add_line('No new products added in this period.', 11)
    else:
        for p in products:
            pc.ensure(18)
            y = pc.y
            pc._streams.append(_text_line(y, str(p['created_at'])[:16],      9,  54))
            pc._streams.append(_text_line(y, str(p['name'])[:24],            9, 160))
            pc._streams.append(_text_line(y, str(p.get('sku') or '—')[:12],  9, 310))
            pc._streams.append(_text_line(y, f"{p['purchase_price']:.2f}",   9, 385))
            pc._streams.append(_text_line(y, f"{p['selling_price']:.2f}",    9, 460))
            pc._streams.append(_text_line(y, str(p['current_stock']),        9, 525, bold=True))
            pc.skip(16)

    pc.finish()
    return builder.build()


# ── 3. Stock / Quantity Updates PDF ──────────────────────────────────────────
def build_stock_updates_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate multi-page PDF for updated inventory stock and quantity changes."""
    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell = 1.1

    raw_dt = report_data.get('generated_at')
    generated = raw_dt if isinstance(raw_dt, str) and raw_dt else _bd_now()

    footer = _make_inventory_footer(qr_matrix, qr_cell)

    def header(page_no: int) -> List[str]:
        ops = [
            _text_line(760, 'Mtronix Stock & Quantity Updates Report', 17, bold=True),
            _text_line(738, f'Period      : {report_data["period_label"]}', 10),
            _text_line(724, f'Generated   : {generated}', 9),
            _text_line(710, f'Address     : {MTRONIX_ADDRESS}', 8),
            _divider(696),
        ]
        if page_no == 1:
            ops += [
                _text_line(678, f'Updated Items: {report_data["total_updated_items"]}', 11, 54, bold=True),
                _text_line(678, f'Total Quantity: {report_data["total_units"]}', 11, 230, bold=True),
                _text_line(678, f'Total Value: BDT {report_data["total_value"]:.2f}', 11, 380, bold=True),
                _divider(662),
            ]
        else:
            ops.append(_text_line(678, f'... continued (page {page_no})', 9))
        return ops

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    # Column headers
    y = pc.y
    pc._streams.append(_text_line(y, 'Updated Time',  10,  54, bold=True))
    pc._streams.append(_text_line(y, 'Product Name',  10, 165, bold=True))
    pc._streams.append(_text_line(y, 'SKU',           10, 315, bold=True))
    pc._streams.append(_text_line(y, 'Quantity',      10, 395, bold=True))
    pc._streams.append(_text_line(y, 'Low Limit',     10, 460, bold=True))
    pc._streams.append(_text_line(y, 'Total Val (BDT)', 10, 515, bold=True))
    pc.skip(16)
    pc.add_divider()
    pc.skip(4)

    items = report_data.get('items', [])
    if not items:
        pc.add_line('No stock quantity updates recorded in this period.', 11)
    else:
        for it in items:
            pc.ensure(18)
            y = pc.y
            pc._streams.append(_text_line(y, str(it['updated_at'])[:16],       9,  54))
            pc._streams.append(_text_line(y, str(it['name'])[:24],             9, 165))
            pc._streams.append(_text_line(y, str(it.get('sku') or '—')[:12],   9, 315))
            pc._streams.append(_text_line(y, str(it['quantity']),              9, 395, bold=True))
            pc._streams.append(_text_line(y, str(it.get('low_stock_threshold', 5)), 9, 460))
            pc._streams.append(_text_line(y, f"{it['total_value']:.2f}",       9, 515))
            pc.skip(16)

    pc.finish()
    return builder.build()
