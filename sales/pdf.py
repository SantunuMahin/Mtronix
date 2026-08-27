"""Fixed PDF generation with no text overriding or duplicate printing"""

from __future__ import annotations

import datetime
import io
from typing import Any, List, Sequence

from django.utils import timezone
import pytz

try:
    import qrcode
except ImportError:
    qrcode = None

# ── Timezone ─────────────────────────────────────────────────────────────────
BD_TZ = pytz.timezone('Asia/Dhaka')

# ── Contact Details ──────────────────────────────────────────────────────────
MTRONIX_ADDRESS = 'Ibrahim Electric & Electronics Market, 124 BCC Road, Dhaka, Bangladesh'
MTRONIX_PHONE   = '01706-970195'
MTRONIX_EMAIL   = 'mannanelectronics111@gmail.com'

INTLISOFT_PHONE = '01888-735883'
INTLISOFT_EMAIL = 'info.intlisoftinnovation@gmail.com'

MAPS_URL = (
    'https://www.google.com/maps/dir/23.7174784,90.4200192/'
    '23.7218447,90.4121045/@23.7197368,90.411174,16z/'
    'data=!3m1!4b1!4m4!4m3!1m1!4e1!1m0?entry=ttu'
    '&g_ep=EgoyMDI2MDYwNy4wIKXMDSoASAFQAw%3D%3D'
)

# ── Page & font constants ────────────────────────────────────────────────────
PAGE_WIDTH    = 612   # US Letter
PAGE_HEIGHT   = 792
MARGIN_TOP    = 60    # usable area top (y from bottom)
MARGIN_BOTTOM = 760   # usable area starts here (y from bottom, high value = near top)
FONT_NAME     = '/Helvetica'
FONT_BOLD     = '/Helvetica-Bold'

# ── QR helpers ───────────────────────────────────────────────────────────────
def _build_qr_matrix(url: str) -> List[List[bool]]:
    if qrcode is None:
        return []
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.get_matrix()


def _qr_pdf_stream(
    matrix: List[List[bool]],
    x_origin: float,
    y_origin: float,
    cell_size: float = 2.0,
) -> str:
    if not matrix:
        return ''
    rows = len(matrix)
    parts = ['0 0 0 rg']
    for r, row in enumerate(matrix):
        y = y_origin + (rows - 1 - r) * cell_size
        for c, dark in enumerate(row):
            if dark:
                x = x_origin + c * cell_size
                parts.append(f'{x:.2f} {y:.2f} {cell_size:.2f} {cell_size:.2f} re f')
    return '\n'.join(parts)


# ── PDF text helpers ─────────────────────────────────────────────────────────
def _escape_pdf_string(value: str) -> str:
    return value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _text_line(y: float, text: str, size: int = 11, x: float = 72, bold: bool = False) -> str:
    font = '/F2' if bold else '/F1'
    return (
        f'BT {font} {size} Tf {x:.2f} {y:.2f} Td '
        f'({_escape_pdf_string(text)}) Tj ET'
    )


def _divider(y: float, size: int = 10) -> str:
    return _text_line(y, '-' * 86, size)


# ── Timezone helpers ─────────────────────────────────────────────────────────
def _bd_now() -> str:
    """Return the current Bangladesh time as a formatted string."""
    return timezone.now().astimezone(BD_TZ).strftime('%d %b %Y, %I:%M %p %A')


def _bd_time(dt) -> str:
    """Convert a Django-aware UTC datetime to Bangladesh time as a formatted string."""
    return timezone.localtime(dt, BD_TZ).strftime('%d %b %Y, %I:%M %p %A')


# ── Multi-page PDF builder ───────────────────────────────────────────────────
class PdfBuilder:
    """
    Multi-page PDF assembler.

    Usage
    -----
    builder = PdfBuilder()
    builder.add_page(streams)   # list of PDF operator strings for page 1
    builder.add_page(streams)   # page 2, etc.
    return builder.build()
    """

    def __init__(self) -> None:
        self._pages: List[List[str]] = []   # one list of operator strings per page

    def add_page(self, streams: List[str]) -> None:
        self._pages.append(streams)

    def build(self) -> bytes:
        if not self._pages:
            self.add_page([])

        out      = io.BytesIO()
        obj_data : List[bytes] = []   # raw bytes for each indirect object
        offsets  : List[int]   = []   # byte offset of each object

        def next_obj_num() -> int:
            return len(obj_data) + 1   # 1-based

        # ── Reserve object slots ─────────────────────────────────────────────
        # 1 = Catalog, 2 = Pages, 3 = Font F1 (regular), 4 = Font F2 (bold)
        # 5..4+N = Page objects, 5+N..4+2N = Content stream objects

        n          = len(self._pages)
        CATALOG    = 1
        PAGES      = 2
        FONT_F1    = 3
        FONT_F2    = 4
        PAGE_START = 5                    # page objects: 5 … 4+n
        CONT_START = PAGE_START + n       # content streams: 5+n … 4+2n

        page_obj_nums = [PAGE_START + i for i in range(n)]
        cont_obj_nums = [CONT_START + i for i in range(n)]
        total_objs    = 4 + 2 * n         # catalog+pages+2 fonts + n pages + n streams

        # ── Build content streams first (we need their lengths) ──────────────
        content_streams: List[bytes] = []
        for streams in self._pages:
            raw = '\n'.join(s for s in streams if s).encode('latin-1', errors='replace')
            content_streams.append(raw)

        # ── Assemble raw object bytes (in object-number order 1…total) ──────
        # We'll write them in order and track offsets.

        # Catalog (obj 1)
        catalog_bytes = (
            f'{CATALOG} 0 obj\n'
            f'<< /Type /Catalog /Pages {PAGES} 0 R >>\n'
            f'endobj\n'
        ).encode('ascii')

        # Pages (obj 2) – Kids list
        kids = ' '.join(f'{num} 0 R' for num in page_obj_nums)
        pages_bytes = (
            f'{PAGES} 0 obj\n'
            f'<< /Type /Pages /Kids [{kids}] /Count {n} >>\n'
            f'endobj\n'
        ).encode('ascii')

        # Font F1 – Helvetica (obj 3)
        font_f1_bytes = (
            f'{FONT_F1} 0 obj\n'
            f'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n'
            f'endobj\n'
        ).encode('ascii')

        # Font F2 – Helvetica-Bold (obj 4)
        font_f2_bytes = (
            f'{FONT_F2} 0 obj\n'
            f'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\n'
            f'endobj\n'
        ).encode('ascii')

        fixed_objects = [catalog_bytes, pages_bytes, font_f1_bytes, font_f2_bytes]

        # Page objects (objs 5 … 4+n)
        page_objects: List[bytes] = []
        for i, (page_num, cont_num) in enumerate(zip(page_obj_nums, cont_obj_nums)):
            page_bytes = (
                f'{page_num} 0 obj\n'
                f'<< /Type /Page /Parent {PAGES} 0 R '
                f'/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] '
                f'/Resources << /Font << /F1 {FONT_F1} 0 R /F2 {FONT_F2} 0 R >> >> '
                f'/Contents {cont_num} 0 R >>\n'
                f'endobj\n'
            ).encode('ascii')
            page_objects.append(page_bytes)

        # Content stream objects (objs 5+n … 4+2n)
        stream_objects: List[bytes] = []
        for cont_num, raw in zip(cont_obj_nums, content_streams):
            stream_obj = (
                f'{cont_num} 0 obj\n'
                f'<< /Length {len(raw)} >>\n'
                f'stream\n'
            ).encode('ascii') + raw + b'\nendstream\nendobj\n'
            stream_objects.append(stream_obj)

        all_objects = fixed_objects + page_objects + stream_objects

        # ── Write PDF ────────────────────────────────────────────────────────
        out.write(b'%PDF-1.4\n')
        for obj in all_objects:
            offsets.append(out.tell())
            out.write(obj)

        # ── xref table ───────────────────────────────────────────────────────
        xref_pos = out.tell()
        out.write(f'xref\n0 {total_objs + 1}\n'.encode('ascii'))
        out.write(b'0000000000 65535 f \n')
        for offset in offsets:
            out.write(f'{offset:010d} 00000 n \n'.encode('ascii'))

        # ── trailer ──────────────────────────────────────────────────────────
        out.write(
            b'trailer\n' +
            f'<< /Size {total_objs + 1} /Root {CATALOG} 0 R >>\n'.encode('ascii') +
            b'startxref\n' +
            str(xref_pos).encode('ascii') +
            b'\n%%EOF\n'
        )
        return out.getvalue()


# ── Page composer helper ─────────────────────────────────────────────────────
class PageComposer:
    """
    Tracks the current Y position across multiple pages and automatically
    starts a new page when content would overflow.

    Usage
    -----
    pc = PageComposer(builder, header_fn=my_header, footer_fn=my_footer)
    pc.ensure(20)          # ensure 20 pts of space, start new page if needed
    pc.add(_text_line(...))
    pc.add(_divider(...))  # pass pre-built operator strings
    pc.finish()            # flush last page (adds footer/QR)
    """

    Y_START  = 740   # first content line y after page header
    Y_BOTTOM = 110   # minimum y before page break (leaves room for footer)

    def __init__(
        self,
        builder: PdfBuilder,
        page_num_total: int = 0,   # 0 = unknown
        header_fn=None,
        footer_fn=None,
    ) -> None:
        self._builder   = builder
        self._header_fn = header_fn   # callable(page_no) -> List[str]
        self._footer_fn = footer_fn   # callable(page_no, is_last) -> List[str]
        self._page_no   = 0
        self._streams   : List[str] = []
        self._y         = self.Y_START
        self._is_first_page = True
        self._new_page()              # start page 1 immediately

    def _new_page(self) -> None:
        # Don't close previous page if this is the first page
        if self._page_no > 0:
            self._close_page(is_last=False)

        self._page_no += 1
        self._streams = []
        self._y       = self.Y_START

        if self._header_fn:
            header_ops = self._header_fn(self._page_no)
            for op in header_ops:
                self._streams.append(op)

            # Extract the lowest Y position from header operations
            lowest_y = self.Y_START
            for op in header_ops:
                if op and 'Td' in op:
                    # Parse Y coordinate from the PDF operator
                    # Format: BT /F1 11 Tf 72.00 740.00 Td (text) Tj ET
                    try:
                        parts = op.split('Td')[0].split()
                        if len(parts) >= 2:
                            y_val = float(parts[-1])
                            lowest_y = min(lowest_y, y_val)
                    except (ValueError, IndexError):
                        pass

            # Set Y position just below the lowest header element
            # Subtract extra space for the font size and padding
            self._y = lowest_y - 20

    def _close_page(self, is_last: bool) -> None:
        if self._footer_fn:
            for op in self._footer_fn(self._page_no, is_last):
                self._streams.append(op)
        self._builder.add_page(self._streams)

    def ensure(self, needed: float) -> None:
        """Start a new page if there isn't enough vertical space."""
        if self._y - needed < self.Y_BOTTOM:
            self._new_page()

    def add(self, op: str, dy: float = 0) -> None:
        """Append an operator string; optionally advance y by dy afterwards."""
        if op:
            self._streams.append(op)
        if dy:
            self._y -= dy

    def add_line(self, text: str, size: int = 11, x: float = 72,
                 bold: bool = False, dy: float | None = None) -> None:
        """Render a text line at current y and advance."""
        self.ensure(size + 4)
        self._streams.append(_text_line(self._y, text, size, x, bold))
        self._y -= dy if dy is not None else size + 4

    def add_divider(self, size: int = 10) -> None:
        self.ensure(size + 4)
        self._streams.append(_divider(self._y, size))
        self._y -= size + 4

    @property
    def y(self) -> float:
        return self._y

    def skip(self, pts: float) -> None:
        self._y -= pts

    def finish(self) -> None:
        self._close_page(is_last=True)


# ── Shared footer / QR builders ──────────────────────────────────────────────
def _make_footer_ops(
    page_no: int,
    is_last: bool,
    qr_matrix: List[List[bool]],
    qr_cell: float,
    extra_lines: List[str],   # additional footer text ops already built
) -> List[str]:
    """
    Return PDF operator strings for the standard footer area.
    QR code appears bottom-right on the LAST page only.
    """
    ops: List[str] = []

    # page number
    ops.append(_text_line(30, f'Page {page_no}', 8, PAGE_WIDTH // 2 - 10))

    # shared footer text
    ops.extend(extra_lines)

    # QR on last page only
    if is_last and qr_matrix:
        qr_size_pts = len(qr_matrix) * qr_cell
        qr_x        = PAGE_WIDTH - 36 - qr_size_pts
        qr_y_bottom = 30
        ops.append(_text_line(qr_y_bottom + qr_size_pts + 4, 'Scan for location', 8, int(qr_x)))
        ops.append(_qr_pdf_stream(qr_matrix, qr_x, qr_y_bottom, qr_cell))

    return ops


# ── Sale Receipt ─────────────────────────────────────────────────────────────
def build_sale_receipt_pdf(sale) -> bytes:
    """Generate a multi-page PDF receipt for the given Sale instance."""
    sold_at  = _bd_time(sale.sold_at)
    customer = sale.customer_name or 'Walk-in'

    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell   = 2.0

    # Pre-built footer text operators (same on every page)
    footer_text_ops = [
        _divider(82, 8),
        _text_line(70, f'Mtronix: {MTRONIX_ADDRESS}', 8),
        _text_line(58, f'Ph: {MTRONIX_PHONE}  |  Email: {MTRONIX_EMAIL}', 8),
        _divider(48, 7),
        _text_line(36, 'This is a computer-generated receipt.', 8),
        _text_line(24, (
            f'Software Provider: Intlisoft Innovation  |  '
            f'Ph: {INTLISOFT_PHONE}  |  Email: {INTLISOFT_EMAIL}'
        ), 8),
    ]

    def header(page_no: int) -> List[str]:
        ops = [
            _text_line(760, 'Mtronix Sales Receipt', 18, bold=True),
            _text_line(738, f'Receipt No : SALE-{sale.pk:05d}', 11),
            _text_line(722, f'Date       : {sold_at}', 11),
            _text_line(706, f'Customer   : {customer}', 11),
            _text_line(692, f'Address    : {MTRONIX_ADDRESS}', 9),
            _text_line(680, f'Phone      : {MTRONIX_PHONE}    Email: {MTRONIX_EMAIL}', 9),
            _divider(668),
        ]
        if page_no == 1:
            # Column headers only on page 1
            ops += [
                _text_line(650, 'Item',        12,  72, bold=True),
                _text_line(650, 'SKU',         12, 270, bold=True),
                _text_line(650, 'Qty',         12, 355, bold=True),
                _text_line(650, 'Unit (BDT)',  12, 405, bold=True),
                _text_line(650, 'Total (BDT)', 12, 500, bold=True),
                _divider(635),
            ]
        else:
            ops += [
                _text_line(650, f'... continued (page {page_no})', 9),
                _text_line(636, 'Item',        10,  72, bold=True),
                _text_line(636, 'SKU',         10, 270, bold=True),
                _text_line(636, 'Qty',         10, 355, bold=True),
                _text_line(636, 'Unit (BDT)',  10, 405, bold=True),
                _text_line(636, 'Total (BDT)', 10, 500, bold=True),
                _divider(623),
            ]
        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last, qr_matrix, qr_cell, footer_text_ops)

    builder = PdfBuilder()
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    # ── Item rows ────────────────────────────────────────────────────────────
    for item in sale.items.select_related('product', 'location').all():
        pc.ensure(22)
        y = pc.y

        # Place all column text at the same Y position (single row)
        pc._streams.append(_text_line(y, item.product.name,          11,  72))
        pc._streams.append(_text_line(y, item.product.sku,           11, 270))
        pc._streams.append(_text_line(y, str(item.quantity),         11, 355))
        pc._streams.append(_text_line(y, f'{item.unit_price:.2f}',   11, 405))
        pc._streams.append(_text_line(y, f'{item.total_amount:.2f}', 11, 500))

        # Advance Y position for next row
        pc.skip(20)

    # ── Totals & closing lines ───────────────────────────────────────────────
    pc.ensure(100)
    pc.add_divider()
    pc.add_line(f'Total Amount:  BDT {sale.total_amount:.2f}', 14, 350, bold=True)
    pc.skip(4)
    pc.add_divider(9)
    pc.skip(4)
    pc.add_line('Thank you for your purchase!', 11)
    pc.add_line('Mtronix — Your trusted electronics partner.', 10)

    pc.finish()
    return builder.build()


# ── Sales Report ─────────────────────────────────────────────────────────────
def build_sales_report_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate a multi-page sales summary report PDF."""
    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell   = 2.0

    # generated_at may be a datetime object, an already-formatted string, or None.
    # Only pass it through _bd_time() if it's an actual datetime; otherwise use as-is
    # (already formatted string) or fall back to the current BD time.
    raw_dt    = report_data.get('generated_at')
    if isinstance(raw_dt, datetime.datetime):
        generated = _bd_time(raw_dt)
    elif isinstance(raw_dt, str) and raw_dt:
        generated = raw_dt          # already a formatted string — use directly
    else:
        generated = _bd_now()       # None or missing — use current time

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

    def header(page_no: int) -> List[str]:
        ops = [
            _text_line(760, 'Mtronix Sales Summary Report', 18, bold=True),
            _text_line(738, f'Period    : {report_data["period_label"]}', 11),
            _text_line(722, f'Generated : {generated}', 9),
            _text_line(708, f'Address   : {MTRONIX_ADDRESS}', 9),
            _text_line(696, f'Phone     : {MTRONIX_PHONE}    Email: {MTRONIX_EMAIL}', 9),
            _divider(682),
        ]
        if page_no == 1:
            ops += [
                _text_line(664, f'Total Revenue  : BDT {report_data["total_revenue"]:.2f}', 12,  72, bold=True),
                _text_line(664, f'Items Sold     : {report_data["total_items_sold"]}',       12, 280, bold=True),
                _text_line(664, f'Transactions   : {report_data["total_transactions"]}',     12, 440, bold=True),
                _divider(648),
            ]
        else:
            ops.append(_text_line(668, f'... continued (page {page_no})', 9))
        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last, qr_matrix, qr_cell, footer_text_ops)

    builder = PdfBuilder()
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    # ── Top Selling Products ─────────────────────────────────────────────────
    pc.ensure(60)
    pc.add_line('Top Selling Products (by Quantity)', 13, bold=True)
    pc.skip(4)

    top_selling = report_data.get('top_selling') or []
    if not top_selling:
        pc.add_line('No sales recorded in this period.', 11)
    else:
        for idx, item in enumerate(top_selling[:5], 1):
            line = (
                f'{idx}. {item["product__name"]} ({item["product__sku"]})'
                f'  —  {item["total_qty"]} sold  |  BDT {item["total_sales"]:.2f}'
            )
            pc.add_line(line, 11)

    pc.skip(8)
    pc.add_divider()
    pc.skip(6)

    # ── Product Sales Breakdown ──────────────────────────────────────────────
    pc.ensure(60)
    pc.add_line('Product Sales Breakdown', 13, bold=True)
    pc.skip(4)

    # Column headers
    y = pc.y
    pc._streams.append(_text_line(y, 'Product Name',  11,  72, bold=True))
    pc._streams.append(_text_line(y, 'SKU',           11, 270, bold=True))
    pc._streams.append(_text_line(y, 'Qty Sold',      11, 360, bold=True))
    pc._streams.append(_text_line(y, 'Total (BDT)',   11, 450, bold=True))
    pc.skip(16)
    pc.add_divider()
    pc.skip(4)

    product_sales = report_data.get('product_sales') or []
    if not product_sales:
        pc.add_line('No product breakdown available.', 11)
    else:
        for item in product_sales:
            pc.ensure(20)
            y = pc.y

            # Place all column text at the same Y position (single row)
            pc._streams.append(_text_line(y, item['product__name'],        10,  72))
            pc._streams.append(_text_line(y, item['product__sku'],         10, 270))
            pc._streams.append(_text_line(y, str(item['total_qty']),       10, 360))
            pc._streams.append(_text_line(y, f"{item['total_sales']:.2f}", 10, 450))

            # Advance Y position for next row
            pc.skip(18)

    pc.finish()
    return builder.build()