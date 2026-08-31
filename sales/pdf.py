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
INTLISOFT_EMAIL = 'santunukaysarmahin@gmail.com'

MAPS_URL = 'https://maps.google.com/?q=23.7218447,90.4121045'

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


# ── Drawing & Vector Helpers ──────────────────────────────────────────────────
def _sanitize_text(value: Any) -> str:
    """Sanitize string for standard Latin-1 PDF Type1 fonts (replaces unicode symbols)."""
    if value is None:
        return ''
    s = str(value)
    s = s.replace('৳', 'BDT ').replace('$', '$').replace('€', 'EUR ').replace('£', 'GBP ').replace('¥', 'JPY ')
    s = s.replace('\u2014', '-').replace('\u2013', '-').replace('\u2212', '-')
    s = s.replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
    s = s.replace('\u2022', '*').replace('\u00b7', '|').replace('\u2713', 'v').replace('\u2714', 'v')
    s = s.replace('\u2192', '->').replace('\u2190', '<-').replace('\u00a0', ' ')
    s = s.replace('🌓', '[Partial]').replace('✓', '[Paid]').replace('⚠', '[!]').replace('✨', '*').replace('📦', '')
    return s.encode('latin-1', errors='replace').decode('latin-1')


def _escape_pdf_string(value: Any) -> str:
    if value is None:
        return ''
    s = _sanitize_text(value)
    return s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _rect_fill(x: float, y: float, w: float, h: float, r: float = 0.96, g: float = 0.97, b: float = 0.99) -> str:
    """Filled rectangle."""
    return f'{r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f'


def _rect_stroke(x: float, y: float, w: float, h: float, r: float = 0.85, g: float = 0.88, b: float = 0.92, line_width: float = 0.75) -> str:
    """Stroked rectangular border."""
    return f'{line_width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S'


def _rect_card(
    x: float,
    y: float,
    w: float,
    h: float,
    bg: tuple[float, float, float] = (0.975, 0.985, 0.995),
    border: tuple[float, float, float] = (0.88, 0.91, 0.94),
    line_width: float = 0.75,
) -> str:
    """Filled and bordered card box."""
    return (
        f'{bg[0]:.3f} {bg[1]:.3f} {bg[2]:.3f} rg '
        f'{border[0]:.3f} {border[1]:.3f} {border[2]:.3f} RG '
        f'{line_width:.2f} w '
        f'{x:.2f} {y:.2f} {w:.2f} {h:.2f} re B'
    )


def _line(x1: float, y1: float, x2: float, y2: float, r: float = 0.85, g: float = 0.88, b: float = 0.92, width: float = 0.75) -> str:
    """Vector line."""
    return f'{width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S'


def _divider(y: float, size: int = 10, r: float = 0.88, g: float = 0.91, b: float = 0.94, width: float = 0.75, x1: float = 54, x2: float = 558) -> str:
    """Geometric divider line across page margins."""
    return _line(x1, y, x2, y, r, g, b, width)


def _text_line(
    y: float,
    text: str,
    size: int = 10,
    x: float = 54,
    bold: bool = False,
    r: float = 0.06,
    g: float = 0.09,
    b: float = 0.16,
) -> str:
    font = '/F2' if bold else '/F1'
    return (
        f'{r:.3f} {g:.3f} {b:.3f} rg '
        f'BT {font} {size} Tf {x:.2f} {y:.2f} Td '
        f'({_escape_pdf_string(text)}) Tj ET'
    )


def _text_right(
    y: float,
    text: str,
    size: int = 9,
    x_right: float = 550,
    bold: bool = False,
    r: float = 0.06,
    g: float = 0.09,
    b: float = 0.16,
) -> str:
    """Render right-aligned text."""
    approx_w = len(str(text)) * (size * 0.52)
    x = max(54.0, x_right - approx_w)
    return _text_line(y, text, size=size, x=x, bold=bold, r=r, g=g, b=b)


def _badge(
    x: float,
    y: float,
    text: str,
    bg: tuple[float, float, float] = (0.82, 0.98, 0.90),
    fg: tuple[float, float, float] = (0.02, 0.37, 0.27),
    w: float = 50,
    h: float = 14,
    size: int = 8,
) -> str:
    """Render a colored status badge."""
    ops = [
        _rect_fill(x, y, w, h, bg[0], bg[1], bg[2]),
        _rect_stroke(x, y, w, h, bg[0]*0.9, bg[1]*0.9, bg[2]*0.9, 0.5),
        _text_line(y + 3.5, text, size=size, x=x + 4, bold=True, r=fg[0], g=fg[1], b=fg[2]),
    ]
    return '\n'.join(ops)


def _render_kpi_cards(
    y: float,
    cards: Sequence[tuple[str, str, tuple[float, float, float]]],
    h: float = 44,
) -> list[str]:
    """
    Render 3 or 4 sleek KPI metric cards side-by-side.
    cards: list of (label, value, accent_rgb)
    """
    ops: list[str] = []
    n = len(cards)
    if n == 0:
        return ops

    total_w = 504.0
    gap = 10.0
    card_w = (total_w - (n - 1) * gap) / n

    for i, (label, val, accent) in enumerate(cards):
        cx = 54.0 + i * (card_w + gap)
        # Background & border
        ops.append(_rect_card(cx, y, card_w, h, bg=(0.985, 0.99, 1.0), border=(0.85, 0.88, 0.92)))
        # Top color accent bar (2.5pt)
        ops.append(_line(cx, y + h, cx + card_w, y + h, r=accent[0], g=accent[1], b=accent[2], width=2.5))
        # Label (small muted uppercase)
        ops.append(_text_line(y + h - 14, label.upper(), size=7.5, x=cx + 8, bold=True, r=0.39, g=0.45, b=0.55))
        # Value (bold dark)
        ops.append(_text_line(y + 8, val, size=11.5, x=cx + 8, bold=True, r=0.06, g=0.09, b=0.16))

    return ops


# ── Timezone helpers ─────────────────────────────────────────────────────────
def _bd_now() -> str:
    """Return current Bangladesh time as formatted string."""
    return timezone.now().astimezone(BD_TZ).strftime('%d %b %Y, %I:%M %p')


def _bd_time(dt) -> str:
    """Convert Django datetime to Bangladesh time formatted string."""
    return timezone.localtime(dt, BD_TZ).strftime('%d %b %Y, %I:%M %p')


# ── Multi-page PDF builder ───────────────────────────────────────────────────
class PdfBuilder:
    def __init__(self, auto_print: bool = False) -> None:
        self._pages: List[List[str]] = []
        self.auto_print = auto_print

    def add_page(self, streams: List[str]) -> None:
        self._pages.append(streams)

    def build(self) -> bytes:
        if not self._pages:
            self.add_page([])

        n = len(self._pages)
        CATALOG = 1
        PAGES = 2
        FONT_F1 = 3
        FONT_F2 = 4
        PAGE_START = 5
        CONT_START = PAGE_START + n

        page_obj_nums = [PAGE_START + i for i in range(n)]
        cont_obj_nums = [CONT_START + i for i in range(n)]
        total_objs = 4 + 2 * n

        content_streams: List[bytes] = []
        for streams in self._pages:
            raw = '\n'.join(s for s in streams if s).encode('latin-1', errors='replace')
            content_streams.append(raw)

        if self.auto_print:
            catalog_bytes = (
                f'{CATALOG} 0 obj\n'
                f'<< /Type /Catalog /Pages {PAGES} 0 R /OpenAction << /Type /Action /S /Named /N /Print >> >>\n'
                f'endobj\n'
            ).encode('ascii')
        else:
            catalog_bytes = (
                f'{CATALOG} 0 obj\n'
                f'<< /Type /Catalog /Pages {PAGES} 0 R >>\n'
                f'endobj\n'
            ).encode('ascii')

        kids = ' '.join(f'{num} 0 R' for num in page_obj_nums)
        pages_bytes = (
            f'{PAGES} 0 obj\n'
            f'<< /Type /Pages /Kids [{kids}] /Count {n} >>\n'
            f'endobj\n'
        ).encode('ascii')

        font_f1_bytes = (
            f'{FONT_F1} 0 obj\n'
            f'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n'
            f'endobj\n'
        ).encode('ascii')

        font_f2_bytes = (
            f'{FONT_F2} 0 obj\n'
            f'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\n'
            f'endobj\n'
        ).encode('ascii')

        fixed_objects = [catalog_bytes, pages_bytes, font_f1_bytes, font_f2_bytes]

        page_objects: List[bytes] = []
        for i, (page_num, cont_num) in enumerate(zip(page_obj_nums, cont_obj_nums)):
            page_bytes = (
                f'{page_num} 0 obj\n'
                f'<< /Type /Page /Parent {PAGES} 0 R\n'
                f'   /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}]\n'
                f'   /Contents {cont_num} 0 R\n'
                f'   /Resources << /Font << /F1 {FONT_F1} 0 R /F2 {FONT_F2} 0 R >> >>\n'
                f'>>\n'
                f'endobj\n'
            ).encode('ascii')
            page_objects.append(page_bytes)

        stream_objects: List[bytes] = []
        for cont_num, raw_stream in zip(cont_obj_nums, content_streams):
            stream_head = (
                f'{cont_num} 0 obj\n'
                f'<< /Length {len(raw_stream)} >>\n'
                f'stream\n'
            ).encode('ascii')
            stream_foot = b'\nendstream\nendobj\n'
            stream_objects.append(stream_head + raw_stream + stream_foot)

        all_objects = fixed_objects + page_objects + stream_objects

        out = io.BytesIO()
        out.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets: List[int] = []

        for obj_b in all_objects:
            offsets.append(out.tell())
            out.write(obj_b)

        xref_offset = out.tell()
        out.write(f'xref\n0 {total_objs + 1}\n'.encode('ascii'))
        out.write(b'0000000000 65535 f \n')
        for off in offsets:
            out.write(f'{off:010d} 00000 n \n'.encode('ascii'))

        trailer = (
            f'trailer\n'
            f'<< /Size {total_objs + 1} /Root {CATALOG} 0 R >>\n'
            f'startxref\n'
            f'{xref_offset}\n'
            f'%%EOF\n'
        )
        out.write(trailer.encode('ascii'))
        return out.getvalue()


# ── Page Composer ────────────────────────────────────────────────────────────
class PageComposer:
    Y_TOP = 760
    Y_BOTTOM = 80

    def __init__(self, builder: PdfBuilder, header_fn=None, footer_fn=None) -> None:
        self._builder = builder
        self._header_fn = header_fn
        self._footer_fn = footer_fn
        self._page_no = 0
        self._streams: List[str] = []
        self._y = self.Y_TOP
        self._new_page()

    def _new_page(self) -> None:
        if self._page_no > 0:
            self._close_page(is_last=False)
        self._page_no += 1
        self._streams = []
        self._y = self.Y_TOP

        if self._header_fn:
            header_ops = self._header_fn(self._page_no)
            self._streams.extend(header_ops)
            lowest_y = self.Y_TOP
            for op in header_ops:
                if ' Td ' in op:
                    try:
                        parts = op.split('Td')[0].split()
                        if len(parts) >= 2:
                            y_val = float(parts[-1])
                            lowest_y = min(lowest_y, y_val)
                    except (ValueError, IndexError):
                        pass
            self._y = lowest_y - 16

    def _close_page(self, is_last: bool) -> None:
        if self._footer_fn:
            for op in self._footer_fn(self._page_no, is_last):
                self._streams.append(op)
        self._builder.add_page(self._streams)

    def ensure(self, needed: float) -> None:
        if self._y - needed < self.Y_BOTTOM:
            self._new_page()

    def add(self, op: str, dy: float = 0) -> None:
        if op:
            self._streams.append(op)
        if dy:
            self._y -= dy

    def add_line(self, text: str, size: int = 10, x: float = 54, bold: bool = False, dy: float | None = None, r: float = 0.06, g: float = 0.09, b: float = 0.16) -> None:
        self.ensure(size + 4)
        self._streams.append(_text_line(self._y, text, size, x, bold, r, g, b))
        self._y -= dy if dy is not None else size + 4

    def add_divider(self, size: int = 10) -> None:
        self.ensure(10)
        self._streams.append(_divider(self._y))
        self._y -= 10

    @property
    def y(self) -> float:
        return self._y

    def skip(self, pts: float) -> None:
        self._y -= pts

    def finish(self) -> None:
        self._close_page(is_last=True)


# ── Shared Executive Footer ──────────────────────────────────────────────────
def _make_footer_ops(
    page_no: int,
    is_last: bool,
    *args,
) -> List[str]:
    """Render a clean executive footer across all pages."""
    ops: List[str] = [
        _line(54, 52, 558, 52, r=0.88, g=0.91, b=0.94, width=0.75),
        _text_line(38, f'Mtronix: {MTRONIX_ADDRESS}', 7.5, 54, r=0.39, g=0.45, b=0.55),
        _text_line(26, f'Ph: {MTRONIX_PHONE}  |  Email: {MTRONIX_EMAIL}', 7.5, 54, r=0.39, g=0.45, b=0.55),
        _text_line(38, f'Page {page_no}', 8, 510, bold=True, r=0.06, g=0.09, b=0.16),
        _text_line(26, f'Software: Intlisoft Innovation ({INTLISOFT_PHONE})', 7.5, 330, r=0.47, g=0.53, b=0.62),
    ]
    return ops


# ── 1. Sale Receipt PDF ──────────────────────────────────────────────────────
def build_sale_receipt_pdf(sale) -> bytes:
    """Generate a high-end multi-page PDF receipt for the given Sale instance."""
    sold_at = _bd_time(sale.sold_at)
    customer = sale.customer_name or 'Walk-in Customer'
    phone = sale.customer_phone or ''
    address = sale.customer_address or ''
    status_str = sale.get_payment_status_display().upper() if hasattr(sale, 'get_payment_status_display') else str(sale.payment_status).upper()
    is_paid = (sale.payment_status == 'PAID')
    is_partial = (sale.payment_status == 'PARTIAL')
    paid_amt = float(sale.effective_paid_amount)
    due_amt = float(sale.due_amount)

    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell = 1.05

    def header(page_no: int) -> List[str]:
        ops = []
        if page_no == 1:
            # ── Brand Header ──
            ops.append(_text_line(762, 'MTRONIX', 20, 54, bold=True, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(748, 'ELECTRONICS, HARDWARE & COMPONENTS', 8, 54, bold=True, r=0.06, g=0.46, b=0.43))
            ops.append(_text_line(735, '124 BCC Road, Ibrahim Market, Dhaka, Bangladesh', 8, 54, r=0.39, g=0.45, b=0.55))
            ops.append(_text_line(723, f'Phone: {MTRONIX_PHONE}  |  {MTRONIX_EMAIL}', 8, 54, r=0.39, g=0.45, b=0.55))

            # ── QR Code Top Right ──
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

            # Divider below brand
            ops.append(_line(54, 710, 558, 710, r=0.06, g=0.09, b=0.16, width=1.5))

            # ── Meta Box ──
            ops.append(_rect_card(54, 642, 504, 60, bg=(0.975, 0.985, 0.995), border=(0.88, 0.91, 0.94)))
            
            # Left col: Invoice & Date
            ops.append(_text_line(685, 'INVOICE NO', 7.5, 68, bold=True, r=0.39, g=0.45, b=0.55))
            ops.append(_text_line(671, f'SALE-{sale.pk:05d}', 11, 68, bold=True, r=0.06, g=0.46, b=0.43))
            ops.append(_text_line(655, f'Date: {sold_at}', 8.5, 68, r=0.28, g=0.33, b=0.41))

            # Right col: Customer & Status
            ops.append(_text_line(685, 'CUSTOMER DETAILS', 7.5, 290, bold=True, r=0.39, g=0.45, b=0.55))
            ops.append(_text_line(671, customer, 10.5, 290, bold=True, r=0.06, g=0.09, b=0.16))
            cust_sub = f'Phone: {phone}' if phone else ''
            if address:
                cust_sub += f'  |  {address}' if cust_sub else address
            if cust_sub:
                ops.append(_text_line(656, cust_sub[:42], 8, 290, r=0.39, g=0.45, b=0.55))

            # Payment badge
            if is_paid:
                ops.append(_badge(476, 672, 'PAID', bg=(0.82, 0.98, 0.90), fg=(0.02, 0.37, 0.27), w=66, h=16, size=8.5))
            elif is_partial:
                ops.append(_badge(476, 672, 'PARTIAL', bg=(0.99, 0.95, 0.78), fg=(0.57, 0.25, 0.05), w=66, h=16, size=8.5))
            else:
                ops.append(_badge(476, 672, 'UNPAID', bg=(0.99, 0.89, 0.89), fg=(0.60, 0.11, 0.11), w=66, h=16, size=8.5))

            curr_y = 626
            # ── Table Header Bar ──
            ops.append(_rect_fill(54, curr_y - 4, 504, 20, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(curr_y + 2, 'ITEM DESCRIPTION', 8.5, 66, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 2, 'SKU', 8.5, 260, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'QTY', 8.5, 370, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'UNIT PRICE (BDT)', 8.5, 460, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 2, 'TOTAL (BDT)', 8.5, 550, bold=True, r=1.0, g=1.0, b=1.0))
        else:
            ops.append(_text_line(760, f'Mtronix Sales Receipt - SALE-{sale.pk:05d} (Page {page_no})', 9, 54, bold=True, r=0.39, g=0.45, b=0.55))
            ops.append(_line(54, 750, 558, 750, r=0.88, g=0.91, b=0.94, width=0.75))
            curr_y = 732
            ops.append(_rect_fill(54, curr_y - 4, 504, 18, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(curr_y + 1, 'ITEM DESCRIPTION', 8, 66, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_line(curr_y + 1, 'SKU', 8, 260, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'QTY', 8, 370, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'UNIT PRICE (BDT)', 8, 460, bold=True, r=1.0, g=1.0, b=1.0))
            ops.append(_text_right(curr_y + 1, 'TOTAL (BDT)', 8, 550, bold=True, r=1.0, g=1.0, b=1.0))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    # ── Item Rows with Zebra Striping ──
    for idx, item in enumerate(sale.items.select_related('product').all()):
        pc.ensure(20)
        y = pc.y
        # Zebra shading on odd rows
        if idx % 2 == 1:
            pc._streams.append(_rect_fill(54, y - 4, 504, 18, 0.975, 0.985, 0.995))
        pc._streams.append(_line(54, y - 4, 558, y - 4, 0.90, 0.92, 0.95, 0.5))

        p_name = _sanitize_text(item.display_name)[:30]
        sku_val = _sanitize_text(item.sku) if item.sku else '-'

        pc._streams.append(_text_line(y, p_name, 9, 66, bold=True, r=0.06, g=0.09, b=0.16))
        pc._streams.append(_text_line(y, sku_val, 8.5, 260, r=0.39, g=0.45, b=0.55))
        pc._streams.append(_text_right(y, str(item.quantity), 9, 370, r=0.06, g=0.09, b=0.16))
        pc._streams.append(_text_right(y, f'{item.unit_price:.2f}', 9, 460, r=0.06, g=0.09, b=0.16))
        pc._streams.append(_text_right(y, f'{item.total_amount:.2f}', 9.5, 550, bold=True, r=0.06, g=0.09, b=0.16))
        pc.skip(18)

    # ── Financial Totals Box ──
    pc.ensure(110)
    pc.skip(8)
    y = pc.y
    box_w = 230.0
    box_x = 558.0 - box_w
    has_due = (due_amt > 0)
    box_h = 88.0 if has_due else 64.0

    pc._streams.append(_rect_card(box_x, y - box_h, box_w, box_h, bg=(0.98, 0.985, 0.995), border=(0.85, 0.88, 0.92)))
    
    # Total Amount
    pc._streams.append(_text_line(y - 18, 'TOTAL AMOUNT:', 9.5, box_x + 14, bold=True, r=0.06, g=0.09, b=0.16))
    pc._streams.append(_text_line(y - 18, f'BDT {sale.total_amount:.2f}', 12, box_x + 120, bold=True, r=0.06, g=0.46, b=0.43))
    
    # Paid Amount
    pc._streams.append(_text_line(y - 34, 'PAID AMOUNT:', 9, box_x + 14, bold=True, r=0.02, g=0.37, b=0.27))
    pc._streams.append(_text_line(y - 34, f'BDT {paid_amt:.2f}', 10.5, box_x + 120, bold=True, r=0.02, g=0.37, b=0.27))

    # Payment Status
    pc._streams.append(_text_line(y - 50, 'Payment Status:', 8.5, box_x + 14, r=0.39, g=0.45, b=0.55))
    pc._streams.append(_text_line(y - 50, status_str, 9, box_x + 120, bold=True, r=(0.02 if is_paid else (0.57 if is_partial else 0.60)), g=(0.37 if is_paid else (0.25 if is_partial else 0.11)), b=(0.27 if is_paid else (0.05 if is_partial else 0.11))))

    if has_due:
        pc._streams.append(_line(box_x + 10, y - 60, box_x + box_w - 10, y - 60, 0.88, 0.91, 0.94, 0.5))
        pc._streams.append(_text_line(y - 76, 'BALANCE DUE:', 9.5, box_x + 14, bold=True, r=0.60, g=0.11, b=0.11))
        pc._streams.append(_text_line(y - 76, f'BDT {due_amt:.2f}', 12, box_x + 120, bold=True, r=0.60, g=0.11, b=0.11))

    # Notes on left side of totals
    pc._streams.append(_text_line(y - 18, 'Thank you for your purchase!', 10.5, 54, bold=True, r=0.06, g=0.09, b=0.16))
    pc._streams.append(_text_line(y - 32, 'Warranty claims valid with this invoice.', 8, 54, r=0.39, g=0.45, b=0.55))
    pc._streams.append(_text_line(y - 44, 'Computer-generated receipt, valid without signature.', 8, 54, r=0.39, g=0.45, b=0.55))

    pc.skip(box_h + 16)
    pc.finish()
    return builder.build()


# ── 2. Customer Account Statement PDF ─────────────────────────────────────────
def build_customer_statement_pdf(data: dict[str, Any]) -> bytes:
    """Generate executive consolidated customer account statement PDF."""
    customer_name = data.get('customer_name') or 'Valued Customer'
    customer_phone = data.get('customer_phone') or ''
    customer_address = data.get('customer_address') or ''
    is_multi_customer = data.get('is_multi_customer', False)
    distinct_count = data.get('distinct_customer_count', 1)
    filter_label = data.get('filter_label') or 'All Transactions'
    generated = data.get('generated_at') or _bd_now()

    total_billed = float(data.get('total_billed', 0.0))
    total_paid = float(data.get('total_paid', 0.0))
    total_due = float(data.get('total_due', 0.0))
    items = data.get('items', [])

    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell = 1.05

    def header(page_no: int) -> List[str]:
        ops = []
        if page_no == 1:
            # ── Brand Header ──
            ops.append(_text_line(762, 'MTRONIX', 20, 54, bold=True, r=0.06, g=0.09, b=0.16))
            sub_title = 'CONSOLIDATED SALES & CUSTOMER LEDGER' if is_multi_customer else 'CUSTOMER ACCOUNT STATEMENT & LEDGER'
            ops.append(_text_line(748, sub_title, 8.5, 54, bold=True, r=0.06, g=0.46, b=0.43))
            ops.append(_text_line(735, '124 BCC Road, Ibrahim Market, Dhaka, Bangladesh', 8, 54, r=0.39, g=0.45, b=0.55))
            ops.append(_text_line(723, f'Phone: {MTRONIX_PHONE}  |  {MTRONIX_EMAIL}', 8, 54, r=0.39, g=0.45, b=0.55))

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

            # ── Customer / Account Info Box ──
            ops.append(_rect_card(54, 652, 504, 50, bg=(0.975, 0.985, 0.995), border=(0.88, 0.91, 0.94)))
            if is_multi_customer:
                ops.append(_text_line(688, 'STATEMENT TYPE:', 7.5, 68, bold=True, r=0.39, g=0.45, b=0.55))
                ops.append(_text_line(674, f'Consolidated Ledger ({distinct_count} Accounts)', 10.5, 68, bold=True, r=0.06, g=0.09, b=0.16))
                ops.append(_text_line(660, 'Combined transaction ledger across multiple customer accounts & walk-ins', 7.5, 68, r=0.39, g=0.45, b=0.55))
            else:
                ops.append(_text_line(688, 'ACCOUNT FOR:', 7.5, 68, bold=True, r=0.39, g=0.45, b=0.55))
                ops.append(_text_line(674, customer_name, 11, 68, bold=True, r=0.06, g=0.09, b=0.16))
                c_meta = f'Phone: {customer_phone}' if customer_phone else ''
                if customer_address:
                    c_meta += f'  |  {customer_address}' if c_meta else customer_address
                if c_meta:
                    ops.append(_text_line(660, c_meta[:50], 8, 68, r=0.39, g=0.45, b=0.55))

            ops.append(_text_line(688, 'STATEMENT CRITERIA:', 7.5, 340, bold=True, r=0.39, g=0.45, b=0.55))
            ops.append(_text_line(674, f'{filter_label}', 9.5, 340, bold=True, r=0.06, g=0.46, b=0.43))
            ops.append(_text_line(660, f'Generated: {generated}', 8, 340, r=0.39, g=0.45, b=0.55))

            # ── KPI Cards ──
            kpis = [
                ('Total Invoiced', f'BDT {total_billed:.2f}', (0.06, 0.46, 0.43)),
                ('Total Paid', f'BDT {total_paid:.2f}', (0.02, 0.37, 0.27)),
                ('Outstanding Due', f'BDT {total_due:.2f}', (0.60, 0.11, 0.11) if total_due > 0 else (0.06, 0.46, 0.43)),
            ]
            ops.extend(_render_kpi_cards(596, kpis, h=44))

            curr_y = 580
            # ── Table Header Bar ──
            ops.append(_rect_fill(54, curr_y - 4, 504, 20, r=0.06, g=0.09, b=0.16))
            if is_multi_customer:
                ops.append(_text_line(curr_y + 2, 'DATE', 7.5, 60, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 2, 'INVOICE', 7.5, 118, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 2, 'CUSTOMER', 7.5, 175, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 2, 'PRODUCT', 7.5, 262, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 2, 'QTY', 7.5, 375, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 2, 'PRICE (BDT)', 7.5, 435, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 2, 'TOTAL (BDT)', 7.5, 495, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 2, 'STATUS', 7.5, 514, bold=True, r=1.0, g=1.0, b=1.0))
            else:
                ops.append(_text_line(curr_y + 2, 'DATE', 8, 64, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 2, 'INVOICE', 8, 135, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 2, 'PRODUCT DESCRIPTION', 8, 195, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 2, 'QTY', 8, 360, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 2, 'PRICE (BDT)', 8, 430, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 2, 'TOTAL (BDT)', 8, 495, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 2, 'STATUS', 8, 516, bold=True, r=1.0, g=1.0, b=1.0))
        else:
            header_title = f'Mtronix Consolidated Statement (Page {page_no})' if is_multi_customer else f'Mtronix Customer Statement - {customer_name} (Page {page_no})'
            ops.append(_text_line(760, header_title, 9, 54, bold=True, r=0.39, g=0.45, b=0.55))
            ops.append(_line(54, 750, 558, 750, r=0.88, g=0.91, b=0.94, width=0.75))
            curr_y = 732
            ops.append(_rect_fill(54, curr_y - 4, 504, 18, r=0.06, g=0.09, b=0.16))
            if is_multi_customer:
                ops.append(_text_line(curr_y + 1, 'DATE', 7.5, 60, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 1, 'INVOICE', 7.5, 118, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 1, 'CUSTOMER', 7.5, 175, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 1, 'PRODUCT', 7.5, 262, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 1, 'QTY', 7.5, 375, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 1, 'PRICE (BDT)', 7.5, 435, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 1, 'TOTAL (BDT)', 7.5, 495, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 1, 'STATUS', 7.5, 514, bold=True, r=1.0, g=1.0, b=1.0))
            else:
                ops.append(_text_line(curr_y + 1, 'DATE', 8, 64, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 1, 'INVOICE', 8, 135, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 1, 'PRODUCT DESCRIPTION', 8, 195, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 1, 'QTY', 8, 360, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 1, 'PRICE (BDT)', 8, 430, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_right(curr_y + 1, 'TOTAL (BDT)', 8, 495, bold=True, r=1.0, g=1.0, b=1.0))
                ops.append(_text_line(curr_y + 1, 'STATUS', 8, 516, bold=True, r=1.0, g=1.0, b=1.0))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder()
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    if not items:
        pc.ensure(40)
        pc.add_line('No transaction records found for the selected criteria.', 10, r=0.39, g=0.45, b=0.55)
    else:
        for idx, it in enumerate(items):
            pc.ensure(18)
            y = pc.y
            if idx % 2 == 1:
                pc._streams.append(_rect_fill(54, y - 4, 504, 18, 0.975, 0.985, 0.995))
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.90, 0.92, 0.95, 0.5))

            date_str = _sanitize_text(it.get('date', '-'))
            inv_str = _sanitize_text(it.get('sale_code', f"#{it.get('sale_id', '')}"))
            cust_str = _sanitize_text(str(it.get('customer_name', 'Walk-in'))[:14])
            prod_str = _sanitize_text(str(it.get('product_name', ''))[:(14 if is_multi_customer else 22)])
            qty_str = str(it.get('quantity', 0))
            price_str = f"{float(it.get('unit_price', 0)):.2f}"
            total_str = f"{float(it.get('total_amount', 0)):.2f}"
            st_raw = str(it.get('status', 'PAID')).upper()

            if is_multi_customer:
                pc._streams.append(_text_line(y, date_str, 7.5, 60, r=0.28, g=0.33, b=0.41))
                pc._streams.append(_text_line(y, inv_str, 7.5, 118, bold=True, r=0.06, g=0.46, b=0.43))
                pc._streams.append(_text_line(y, cust_str, 7.5, 175, bold=True, r=0.15, g=0.20, b=0.30))
                pc._streams.append(_text_line(y, prod_str, 7.5, 262, bold=True, r=0.06, g=0.09, b=0.16))
                pc._streams.append(_text_right(y, qty_str, 7.5, 375, r=0.06, g=0.09, b=0.16))
                pc._streams.append(_text_right(y, price_str, 7.5, 435, r=0.06, g=0.09, b=0.16))
                pc._streams.append(_text_right(y, total_str, 7.5, 495, bold=True, r=0.06, g=0.09, b=0.16))
                badge_x = 512
            else:
                pc._streams.append(_text_line(y, date_str, 8, 64, r=0.28, g=0.33, b=0.41))
                pc._streams.append(_text_line(y, inv_str, 8, 135, bold=True, r=0.06, g=0.46, b=0.43))
                pc._streams.append(_text_line(y, prod_str, 8.5, 195, bold=True, r=0.06, g=0.09, b=0.16))
                pc._streams.append(_text_right(y, qty_str, 8.5, 360, r=0.06, g=0.09, b=0.16))
                pc._streams.append(_text_right(y, price_str, 8.5, 430, r=0.06, g=0.09, b=0.16))
                pc._streams.append(_text_right(y, total_str, 8.5, 495, bold=True, r=0.06, g=0.09, b=0.16))
                badge_x = 510

            if st_raw == 'PAID':
                pc._streams.append(_badge(badge_x, y - 2, 'PAID', bg=(0.82, 0.98, 0.90), fg=(0.02, 0.37, 0.27), w=(40 if is_multi_customer else 44), h=13, size=6.5))
            elif st_raw == 'PARTIAL':
                pc._streams.append(_badge(badge_x, y - 2, 'PARTIAL', bg=(0.99, 0.95, 0.78), fg=(0.57, 0.25, 0.05), w=(40 if is_multi_customer else 44), h=13, size=6.5))
            else:
                pc._streams.append(_badge(badge_x, y - 2, 'UNPAID', bg=(0.99, 0.89, 0.89), fg=(0.60, 0.11, 0.11), w=(40 if is_multi_customer else 44), h=13, size=6.5))

            pc.skip(18)

    # ── Summary Box at End ──
    pc.ensure(90)
    pc.skip(10)
    y = pc.y
    box_w = 230.0
    box_x = 558.0 - box_w
    box_h = 70.0

    pc._streams.append(_rect_card(box_x, y - box_h, box_w, box_h, bg=(0.98, 0.985, 0.995), border=(0.85, 0.88, 0.92)))
    pc._streams.append(_text_line(y - 18, 'TOTAL BILLED:', 9, box_x + 14, bold=True, r=0.39, g=0.45, b=0.55))
    pc._streams.append(_text_line(y - 18, f'BDT {total_billed:.2f}', 10.5, box_x + 120, bold=True, r=0.06, g=0.09, b=0.16))

    pc._streams.append(_text_line(y - 34, 'TOTAL PAID:', 9, box_x + 14, bold=True, r=0.39, g=0.45, b=0.55))
    pc._streams.append(_text_line(y - 34, f'BDT {total_paid:.2f}', 10.5, box_x + 120, bold=True, r=0.02, g=0.37, b=0.27))

    pc._streams.append(_line(box_x + 10, y - 44, box_x + box_w - 10, y - 44, 0.88, 0.91, 0.94, 0.5))
    pc._streams.append(_text_line(y - 60, 'BALANCE DUE:', 9.5, box_x + 14, bold=True, r=0.60, g=0.11, b=0.11))
    pc._streams.append(_text_line(y - 60, f'BDT {total_due:.2f}', 12, box_x + 120, bold=True, r=0.60, g=0.11, b=0.11))

    pc.skip(box_h + 16)
    pc.finish()
    return builder.build()


# ── 3. Sales Summary Report PDF ──────────────────────────────────────────────
def build_sales_report_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate executive sales summary report PDF."""
    qr_matrix = _build_qr_matrix(MAPS_URL)
    qr_cell = 1.05

    raw_dt = report_data.get('generated_at')
    if isinstance(raw_dt, datetime.datetime):
        generated = _bd_time(raw_dt)
    elif isinstance(raw_dt, str) and raw_dt:
        generated = raw_dt
    else:
        generated = _bd_now()

    tot_rev = float(report_data.get("total_revenue", 0))
    tot_paid = float(report_data.get("total_paid", 0))
    tot_due = float(report_data.get("total_due", 0))
    items_sold = int(report_data.get("total_items_sold", 0))

    def header(page_no: int) -> List[str]:
        ops = []
        if page_no == 1:
            ops.append(_text_line(762, 'MTRONIX', 20, 54, bold=True, r=0.06, g=0.09, b=0.16))
            ops.append(_text_line(748, 'SALES SUMMARY & PERFORMANCE REPORT', 8.5, 54, bold=True, r=0.06, g=0.46, b=0.43))
            ops.append(_text_line(735, f'Period: {report_data["period_label"]}  |  Generated: {generated}', 8, 54, r=0.39, g=0.45, b=0.55))
            ops.append(_text_line(723, f'Address: {MTRONIX_ADDRESS}', 8, 54, r=0.39, g=0.45, b=0.55))

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

            kpis = [
                ('Total Revenue', f'BDT {tot_rev:.2f}', (0.06, 0.46, 0.43)),
                ('Total Paid', f'BDT {tot_paid:.2f}', (0.02, 0.37, 0.27)),
                ('Outstanding Due', f'BDT {tot_due:.2f}', (0.60, 0.11, 0.11) if tot_due > 0 else (0.06, 0.46, 0.43)),
                ('Items Sold', str(items_sold), (0.06, 0.09, 0.16)),
            ]
            ops.extend(_render_kpi_cards(656, kpis, h=44))
        else:
            ops.append(_text_line(760, f'Mtronix Sales Summary Report (Page {page_no})', 9, 54, bold=True, r=0.39, g=0.45, b=0.55))
            ops.append(_line(54, 750, 558, 750, r=0.88, g=0.91, b=0.94, width=0.75))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder()
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    # ── Top Selling Products ──
    pc.ensure(80)
    pc.add_line('Top Selling Products (by Quantity)', 12, bold=True, r=0.06, g=0.09, b=0.16)
    pc.skip(6)

    top_selling = report_data.get('top_selling') or []
    if not top_selling:
        pc.add_line('No sales recorded in this period.', 9.5, r=0.39, g=0.45, b=0.55)
    else:
        for idx, item in enumerate(top_selling[:5], 1):
            sku_suffix = f' ({item["product__sku"]})' if item.get("product__sku") else ''
            pname = _sanitize_text(f'{idx}. {item["product__name"]}{sku_suffix}')
            line = f'{pname}   *   {item["total_qty"]} sold   |   BDT {item["total_sales"]:.2f}'
            pc.add_line(line, 9.5, r=0.06, g=0.09, b=0.16)

    pc.skip(10)
    pc.add_divider()
    pc.skip(8)

    # ── Product Sales Breakdown ──
    pc.ensure(80)
    pc.add_line('Product Sales Breakdown', 12, bold=True, r=0.06, g=0.09, b=0.16)
    pc.skip(8)

    y = pc.y
    pc._streams.append(_rect_fill(54, y - 4, 504, 20, r=0.06, g=0.09, b=0.16))
    pc._streams.append(_text_line(y + 2, 'PRODUCT NAME', 8.5, 66, bold=True, r=1.0, g=1.0, b=1.0))
    pc._streams.append(_text_line(y + 2, 'SKU', 8.5, 270, bold=True, r=1.0, g=1.0, b=1.0))
    pc._streams.append(_text_right(y + 2, 'QTY SOLD', 8.5, 390, bold=True, r=1.0, g=1.0, b=1.0))
    pc._streams.append(_text_right(y + 2, 'TOTAL SALES (BDT)', 8.5, 550, bold=True, r=1.0, g=1.0, b=1.0))
    pc.skip(20)

    product_sales = report_data.get('product_sales') or []
    if not product_sales:
        pc.add_line('No product breakdown available.', 9.5, r=0.39, g=0.45, b=0.55)
    else:
        for idx, item in enumerate(product_sales):
            pc.ensure(18)
            y = pc.y
            if idx % 2 == 1:
                pc._streams.append(_rect_fill(54, y - 4, 504, 18, 0.975, 0.985, 0.995))
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.90, 0.92, 0.95, 0.5))

            pc._streams.append(_text_line(y, _sanitize_text(item['product__name'])[:30], 9, 66, bold=True, r=0.06, g=0.09, b=0.16))
            pc._streams.append(_text_line(y, _sanitize_text(item.get('product__sku') or '-'), 8.5, 270, r=0.39, g=0.45, b=0.55))
            pc._streams.append(_text_right(y, str(item['total_qty']), 9, 390, r=0.06, g=0.09, b=0.16))
            pc._streams.append(_text_right(y, f"{item['total_sales']:.2f}", 9.5, 550, bold=True, r=0.06, g=0.09, b=0.16))
            pc.skip(18)

    pc.finish()
    return builder.build()