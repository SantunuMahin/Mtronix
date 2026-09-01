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
MTRONIX_ADDRESS = '44/45, KaftanBazar Madina Electric & Electronics, (2nd floor), shop no-3,4. Wari, Dhaka.'
MTRONIX_PHONE   = '01744676770'
MTRONIX_EMAIL   = 'mtronix1203@gmail.com'

INTLISOFT_PHONE = '01888-735883'
INTLISOFT_EMAIL = 'santunukaysarmahin@gmail.com'

MAPS_URL = 'https://maps.app.goo.gl/2LzGoBcWLzdZQkrZ9'

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
    bg: tuple[float, float, float] = (1.0, 1.0, 1.0),
    fg: tuple[float, float, float] = (0.0, 0.0, 0.0),
    w: float = 50,
    h: float = 14,
    size: int = 8,
) -> str:
    """Render a clean monochrome status badge."""
    ops = [
        _rect_stroke(x, y, w, h, 0.0, 0.0, 0.0, 0.75),
        _text_line(y + 3.5, text, size=size, x=x + 4, bold=True, r=0.0, g=0.0, b=0.0),
    ]
    return '\n'.join(ops)


def _render_kpi_cards(
    y: float,
    cards: Sequence[tuple[str, str, Any]],
    h: float = 38,
) -> list[str]:
    """
    Render clean, open, black-and-white summary metrics without colored boxes or frames.
    """
    ops: list[str] = []
    n = len(cards)
    if n == 0:
        return ops

    total_w = 504.0
    col_w = total_w / n

    # Clean top and bottom dividers
    ops.append(_line(54.0, y + h, 558.0, y + h, r=0.0, g=0.0, b=0.0, width=1.0))
    for i, item in enumerate(cards):
        label = item[0]
        val = item[1]
        cx = 54.0 + i * col_w
        ops.append(_text_line(y + h - 12, label.upper(), size=7.5, x=cx, bold=True, r=0.25, g=0.25, b=0.25))
        ops.append(_text_line(y + 4, val, size=11, x=cx, bold=True, r=0.0, g=0.0, b=0.0))
    ops.append(_line(54.0, y, 558.0, y, r=0.0, g=0.0, b=0.0, width=1.0))

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

        objects: Dict[int, bytes] = {}

        if self.auto_print:
            objects[CATALOG] = (
                b'<< /Type /Catalog /Pages 2 0 R /OpenAction << /S /JavaScript /JS (this.print({bUI:true,bSilent:false,bShrinkToFit:true});) >> >>'
            )
        else:
            objects[CATALOG] = b'<< /Type /Catalog /Pages 2 0 R >>'

        kids = ' '.join(f'{num} 0 R' for num in page_obj_nums)
        objects[PAGES] = f'<< /Type /Pages /Kids [{kids}] /Count {n} >>'.encode('ascii')

        objects[FONT_F1] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'
        objects[FONT_F2] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>'

        for i, page_obj in enumerate(page_obj_nums):
            cont_obj = cont_obj_nums[i]
            objects[page_obj] = (
                f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
                f'/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> '
                f'/Contents {cont_obj} 0 R >>'
            ).encode('ascii')

        for i, cont_obj in enumerate(cont_obj_nums):
            stream_body = '\n'.join(self._pages[i]).encode('latin-1')
            objects[cont_obj] = (
                f'<< /Length {len(stream_body)} >>\nstream\n'.encode('ascii')
                + stream_body
                + b'\nendstream'
            )

        total_objects = CONT_START + n - 1
        buf = bytearray()
        buf.extend(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')

        offsets: Dict[int, int] = {}
        for obj_num in range(1, total_objects + 1):
            offsets[obj_num] = len(buf)
            buf.extend(f'{obj_num} 0 obj\n'.encode('ascii'))
            buf.extend(objects[obj_num])
            buf.extend(b'\nendobj\n')

        xref_start = len(buf)
        buf.extend(f'xref\n0 {total_objects + 1}\n'.encode('ascii'))
        buf.extend(b'0000000000 65535 f \n')
        for obj_num in range(1, total_objects + 1):
            buf.extend(f'{offsets[obj_num]:010d} 00000 n \n'.encode('ascii'))

        buf.extend(
            f'trailer\n<< /Size {total_objects + 1} /Root 1 0 R >>\n'
            f'startxref\n{xref_start}\n%%EOF\n'.encode('ascii')
        )
        return bytes(buf)


# ── Page Composer ─────────────────────────────────────────────────────────────
class PageComposer:
    def __init__(
        self,
        builder: PdfBuilder,
        header_fn: Callable[[int], List[str]],
        footer_fn: Callable[[int, bool], List[str]],
        page_top: float = 620.0,
        page_bottom: float = 70.0,
    ) -> None:
        self.builder = builder
        self.header_fn = header_fn
        self.footer_fn = footer_fn
        self.page_top = page_top
        self.page_bottom = page_bottom
        self.page_no = 0
        self._y = page_top
        self._streams: List[str] = []
        self._start_page()

    def _start_page(self) -> None:
        self.page_no += 1
        self._streams = []
        self._streams.extend(self.header_fn(self.page_no))
        self._y = self.page_top

    def _close_page(self, is_last: bool = False) -> None:
        self._streams.extend(self.footer_fn(self.page_no, is_last))
        self.builder.add_page(self._streams)

    def ensure(self, pts: float) -> None:
        if (self._y - pts) < self.page_bottom:
            self._close_page(is_last=False)
            self._start_page()

    def add_line(
        self,
        text: str,
        size: int = 9,
        bold: bool = False,
        r: float = 0.0,
        g: float = 0.0,
        b: float = 0.0,
        x: float = 54.0,
    ) -> None:
        self.ensure(size + 6)
        self._streams.append(_text_line(self._y, text, size=size, bold=bold, r=r, g=g, b=b, x=x))
        self._y -= (size + 4)

    def add_divider(self) -> None:
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
    """Render a clean black and white executive footer across all pages."""
    ops: List[str] = [
        _line(54, 52, 558, 52, r=0.0, g=0.0, b=0.0, width=0.75),
        _text_line(38, f'Mtronix: {MTRONIX_ADDRESS}', 7.5, 54, r=0.25, g=0.25, b=0.25),
        _text_line(26, f'Ph: {MTRONIX_PHONE}  |  Email: {MTRONIX_EMAIL}', 7.5, 54, r=0.25, g=0.25, b=0.25),
        _text_line(38, f'Page {page_no}', 8, 510, bold=True, r=0.0, g=0.0, b=0.0),
        _text_line(26, f'Software: Intlisoft Innovation ({INTLISOFT_PHONE})', 7.5, 330, r=0.3, g=0.3, b=0.3),
    ]
    return ops


# ── 1. Sale Receipt PDF ──────────────────────────────────────────────────────
def build_sale_receipt_pdf(sale, prev_history=None) -> bytes:
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
            ops.append(_text_line(762, 'MTRONIX', 20, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(748, 'ELECTRONICS, HARDWARE & COMPONENTS', 8, 54, bold=True, r=0.2, g=0.2, b=0.2))
            ops.append(_text_line(735, MTRONIX_ADDRESS, 8, 54, r=0.25, g=0.25, b=0.25))
            ops.append(_text_line(723, f'Phone: {MTRONIX_PHONE}  |  {MTRONIX_EMAIL}', 8, 54, r=0.25, g=0.25, b=0.25))

            # ── QR Code Top Right ──
            if qr_matrix:
                qr_size = len(qr_matrix) * qr_cell
                card_w = qr_size + 14
                card_h = qr_size + 20
                card_x = 558 - card_w
                card_y = 712
                qr_x = card_x + 7
                qr_y = card_y + 4
                ops.append(_rect_card(card_x, card_y, card_w, card_h, bg=(1.0, 1.0, 1.0), border=(0.0, 0.0, 0.0)))
                ops.append(_text_line(card_y + card_h - 10, 'SCAN LOCATION', 6.0, card_x + 4, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_qr_pdf_stream(qr_matrix, qr_x, qr_y, qr_cell))

            # Divider below brand
            ops.append(_line(54, 710, 558, 710, r=0.0, g=0.0, b=0.0, width=1.5))

            # ── Meta Details (Clean Open Layout) ──
            # Left col: Invoice & Date
            ops.append(_text_line(695, 'INVOICE NO', 7.5, 54, bold=True, r=0.3, g=0.3, b=0.3))
            ops.append(_text_line(681, f'SALE-{sale.pk:05d}', 11, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(667, f'Date: {sold_at}', 8.5, 54, r=0.2, g=0.2, b=0.2))

            # Right col: Customer & Status
            cust_label = 'CUSTOMER DETAILS'
            if prev_history and prev_history.get('has_previous_orders'):
                cust_label += f" (Order #{prev_history['previous_orders_count'] + 1})"
            ops.append(_text_line(695, cust_label, 7.5, 290, bold=True, r=0.3, g=0.3, b=0.3))
            ops.append(_text_line(681, customer, 10.5, 290, bold=True, r=0.0, g=0.0, b=0.0))
            cust_sub = f'Phone: {phone}' if phone else ''
            if address:
                cust_sub += f'  |  {address}' if cust_sub else address
            if cust_sub:
                ops.append(_text_line(667, cust_sub[:42], 8, 290, r=0.25, g=0.25, b=0.25))

            # Payment badge (Monochrome)
            if is_paid:
                ops.append(_badge(476, 680, 'PAID', bg=(1.0, 1.0, 1.0), fg=(0.0, 0.0, 0.0), w=66, h=16, size=8.5))
            elif is_partial:
                ops.append(_badge(476, 680, 'PARTIAL', bg=(1.0, 1.0, 1.0), fg=(0.0, 0.0, 0.0), w=66, h=16, size=8.5))
            else:
                ops.append(_badge(476, 680, 'UNPAID', bg=(1.0, 1.0, 1.0), fg=(0.0, 0.0, 0.0), w=66, h=16, size=8.5))

            ops.append(_line(54, 656, 558, 656, r=0.0, g=0.0, b=0.0, width=0.75))

            curr_y = 636
            # ── Table Header Bar ──
            ops.append(_line(54, curr_y + 12, 558, curr_y + 12, r=0.0, g=0.0, b=0.0, width=1.5))
            ops.append(_text_line(curr_y + 2, 'ITEM DESCRIPTION', 8.5, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 2, 'SKU', 8.5, 260, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'QTY', 8.5, 370, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'UNIT PRICE (BDT)', 8.5, 460, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 2, 'TOTAL (BDT)', 8.5, 558, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))
        else:
            ops.append(_text_line(760, f'Mtronix Sales Receipt - SALE-{sale.pk:05d} (Page {page_no})', 9, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, 750, 558, 750, r=0.0, g=0.0, b=0.0, width=0.75))
            curr_y = 732
            ops.append(_line(54, curr_y + 10, 558, curr_y + 10, r=0.0, g=0.0, b=0.0, width=1.5))
            ops.append(_text_line(curr_y + 1, 'ITEM DESCRIPTION', 8, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(curr_y + 1, 'SKU', 8, 260, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'QTY', 8, 370, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'UNIT PRICE (BDT)', 8, 460, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_right(curr_y + 1, 'TOTAL (BDT)', 8, 558, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    # ── Item Rows ──
    for idx, item in enumerate(sale.items.select_related('product').all()):
        pc.ensure(20)
        y = pc.y
        pc._streams.append(_line(54, y - 4, 558, y - 4, 0.80, 0.80, 0.80, 0.5))

        p_name = _sanitize_text(item.display_name)[:32]
        sku_val = _sanitize_text(item.sku) if item.sku else '-'

        pc._streams.append(_text_line(y, p_name, 9, 54, bold=True, r=0.0, g=0.0, b=0.0))
        pc._streams.append(_text_line(y, sku_val, 8.5, 260, r=0.25, g=0.25, b=0.25))
        pc._streams.append(_text_right(y, str(item.quantity), 9, 370, r=0.0, g=0.0, b=0.0))
        pc._streams.append(_text_right(y, f'{item.unit_price:.2f}', 9, 460, r=0.0, g=0.0, b=0.0))
        pc._streams.append(_text_right(y, f'{item.total_amount:.2f}', 9.5, 558, bold=True, r=0.0, g=0.0, b=0.0))
        pc.skip(18)

    # ── Financial Totals (Clean Open Monochrome List) ──
    has_prev = bool(prev_history and prev_history.get('has_previous_orders'))
    need_h = 130 if has_prev else 90
    pc.ensure(need_h)
    pc.skip(10)
    y = pc.y
    box_w = 220.0
    box_x = 558.0 - box_w
    has_due = (due_amt > 0)

    # Top border for totals section
    pc._streams.append(_line(54, y + 6, 558, y + 6, 0.0, 0.0, 0.0, 1.5))
    
    # Total Amount
    pc._streams.append(_text_line(y - 12, 'TOTAL AMOUNT:', 9.5, box_x, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y - 12, f'BDT {sale.total_amount:.2f}', 11, 558, bold=True, r=0.0, g=0.0, b=0.0))
    
    # Paid Amount
    pc._streams.append(_text_line(y - 28, 'PAID AMOUNT:', 9, box_x, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y - 28, f'BDT {paid_amt:.2f}', 10, 558, bold=True, r=0.0, g=0.0, b=0.0))

    curr_tot_y = y - 36
    # Balance Due on current invoice
    if has_due:
        pc._streams.append(_line(box_x, curr_tot_y, 558, curr_tot_y, 0.0, 0.0, 0.0, 1.0))
        curr_tot_y -= 14
        pc._streams.append(_text_line(curr_tot_y, 'BALANCE DUE:', 9.5, box_x, bold=True, r=0.0, g=0.0, b=0.0))
        pc._streams.append(_text_right(curr_tot_y, f'BDT {due_amt:.2f}', 11, 558, bold=True, r=0.0, g=0.0, b=0.0))

    # Previous Orders Summary (if returning customer)
    if has_prev:
        curr_tot_y -= 8
        pc._streams.append(_line(box_x, curr_tot_y, 558, curr_tot_y, 0.0, 0.0, 0.0, 0.5))
        curr_tot_y -= 12
        prev_cnt = prev_history['previous_orders_count']
        prev_billed = float(prev_history['previous_total_billed'])
        prev_due = float(prev_history['previous_total_due'])
        net_due = float(prev_history['net_due'])

        pc._streams.append(_text_line(curr_tot_y, f'Prev Purchases ({prev_cnt} orders):', 8, box_x, bold=True, r=0.0, g=0.0, b=0.0))
        pc._streams.append(_text_right(curr_tot_y, f'BDT {prev_billed:.2f}', 8.5, 558, r=0.0, g=0.0, b=0.0))

        if prev_due > 0:
            curr_tot_y -= 12
            pc._streams.append(_text_line(curr_tot_y, 'Previous Unpaid Due:', 8, box_x, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_right(curr_tot_y, f'BDT {prev_due:.2f}', 8.5, 558, r=0.0, g=0.0, b=0.0))
            
            curr_tot_y -= 12
            pc._streams.append(_text_line(curr_tot_y, 'NET TOTAL DUE:', 9, box_x, bold=True, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_right(curr_tot_y, f'BDT {net_due:.2f}', 10, 558, bold=True, r=0.0, g=0.0, b=0.0))

    curr_tot_y -= 8
    pc._streams.append(_line(54, curr_tot_y, 558, curr_tot_y, 0.0, 0.0, 0.0, 1.5))

    # Friendly Note & Signatures on left
    pc._streams.append(_text_line(y - 12, 'Thank you for your purchase!', 10, 54, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_line(y - 26, 'Please keep this invoice for warranty and support.', 8, 54, r=0.25, g=0.25, b=0.25))
    if has_prev and prev_history.get('last_previous_order_date'):
        pc._streams.append(_text_line(y - 38, f"Last previous order on {prev_history['last_previous_order_date']}", 7.5, 54, r=0.2, g=0.2, b=0.2))

    # Customer & Seller Signatures
    sign_y = curr_tot_y - 24
    pc._streams.append(_line(54, sign_y, 170, sign_y, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(sign_y - 10, "Customer's Signature", 8, 54, bold=True, r=0.0, g=0.0, b=0.0))

    pc._streams.append(_line(200, sign_y, 316, sign_y, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(sign_y - 10, "Seller's Signature", 8, 200, bold=True, r=0.0, g=0.0, b=0.0))

    pc.skip(abs(y - sign_y) + 20)
    pc.finish()
    return builder.build()


# ── 2. Customer Account Statement PDF ─────────────────────────────────────────
def build_customer_statement_pdf(data: dict[str, Any]) -> bytes:
    """Generate executive consolidated customer account statement PDF in pure black & white."""
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
            ops.append(_text_line(762, 'MTRONIX', 20, 54, bold=True, r=0.0, g=0.0, b=0.0))
            sub_title = 'CONSOLIDATED SALES & CUSTOMER LEDGER' if is_multi_customer else 'CUSTOMER ACCOUNT STATEMENT & LEDGER'
            ops.append(_text_line(748, sub_title, 8.5, 54, bold=True, r=0.2, g=0.2, b=0.2))
            ops.append(_text_line(735, '124 BCC Road, Ibrahim Market, Dhaka, Bangladesh', 8, 54, r=0.25, g=0.25, b=0.25))
            ops.append(_text_line(723, f'Phone: {MTRONIX_PHONE}  |  {MTRONIX_EMAIL}', 8, 54, r=0.25, g=0.25, b=0.25))

            if qr_matrix:
                qr_size = len(qr_matrix) * qr_cell
                card_w = qr_size + 14
                card_h = qr_size + 20
                card_x = 558 - card_w
                card_y = 712
                qr_x = card_x + 7
                qr_y = card_y + 4
                ops.append(_rect_card(card_x, card_y, card_w, card_h, bg=(1.0, 1.0, 1.0), border=(0.0, 0.0, 0.0)))
                ops.append(_text_line(card_y + card_h - 10, 'SCAN LOCATION', 6.0, card_x + 4, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_qr_pdf_stream(qr_matrix, qr_x, qr_y, qr_cell))

            ops.append(_line(54, 710, 558, 710, r=0.0, g=0.0, b=0.0, width=1.5))

            # ── Customer / Account Info (Clean Open Layout, No Box) ──
            if is_multi_customer:
                ops.append(_text_line(695, 'STATEMENT TYPE', 7.5, 54, bold=True, r=0.3, g=0.3, b=0.3))
                ops.append(_text_line(681, f'Consolidated Ledger ({distinct_count} Accounts)', 10.5, 54, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(667, 'Combined transaction ledger across customer accounts', 7.5, 54, r=0.25, g=0.25, b=0.25))
            else:
                ops.append(_text_line(695, 'ACCOUNT FOR', 7.5, 54, bold=True, r=0.3, g=0.3, b=0.3))
                ops.append(_text_line(681, customer_name, 11, 54, bold=True, r=0.0, g=0.0, b=0.0))
                c_meta = f'Phone: {customer_phone}' if customer_phone else ''
                if customer_address:
                    c_meta += f'  |  {customer_address}' if c_meta else customer_address
                if c_meta:
                    ops.append(_text_line(667, c_meta[:50], 8, 54, r=0.25, g=0.25, b=0.25))

            ops.append(_text_line(695, 'STATEMENT CRITERIA', 7.5, 340, bold=True, r=0.3, g=0.3, b=0.3))
            ops.append(_text_line(681, f'{filter_label}', 9.5, 340, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(667, f'Generated: {generated}', 8, 340, r=0.25, g=0.25, b=0.25))
            ops.append(_line(54, 654, 558, 654, r=0.8, g=0.8, b=0.8, width=0.5))

            curr_y = 636
            # ── Table Header Bar (Clean White Background, Black Lines) ──
            ops.append(_line(54, curr_y + 12, 558, curr_y + 12, r=0.0, g=0.0, b=0.0, width=1.5))
            if is_multi_customer:
                ops.append(_text_line(curr_y + 2, 'DATE', 7.5, 60, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 2, 'INVOICE', 7.5, 118, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 2, 'CUSTOMER', 7.5, 175, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 2, 'PRODUCT', 7.5, 262, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 2, 'QTY', 7.5, 375, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 2, 'PRICE (BDT)', 7.5, 435, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 2, 'TOTAL (BDT)', 7.5, 495, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 2, 'STATUS', 7.5, 514, bold=True, r=0.0, g=0.0, b=0.0))
            else:
                ops.append(_text_line(curr_y + 2, 'DATE', 8, 64, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 2, 'INVOICE', 8, 135, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 2, 'PRODUCT DESCRIPTION', 8, 195, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 2, 'QTY', 8, 360, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 2, 'PRICE (BDT)', 8, 430, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 2, 'TOTAL (BDT)', 8, 495, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 2, 'STATUS', 8, 516, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))
        else:
            header_title = f'Mtronix Consolidated Statement (Page {page_no})' if is_multi_customer else f'Mtronix Customer Statement - {customer_name} (Page {page_no})'
            ops.append(_text_line(760, header_title, 9, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, 750, 558, 750, r=0.0, g=0.0, b=0.0, width=0.75))
            curr_y = 732
            ops.append(_line(54, curr_y + 10, 558, curr_y + 10, r=0.0, g=0.0, b=0.0, width=1.5))
            if is_multi_customer:
                ops.append(_text_line(curr_y + 1, 'DATE', 7.5, 60, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 1, 'INVOICE', 7.5, 118, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 1, 'CUSTOMER', 7.5, 175, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 1, 'PRODUCT', 7.5, 262, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 1, 'QTY', 7.5, 375, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 1, 'PRICE (BDT)', 7.5, 435, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 1, 'TOTAL (BDT)', 7.5, 495, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 1, 'STATUS', 7.5, 514, bold=True, r=0.0, g=0.0, b=0.0))
            else:
                ops.append(_text_line(curr_y + 1, 'DATE', 8, 64, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 1, 'INVOICE', 8, 135, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 1, 'PRODUCT DESCRIPTION', 8, 195, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 1, 'QTY', 8, 360, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 1, 'PRICE (BDT)', 8, 430, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_right(curr_y + 1, 'TOTAL (BDT)', 8, 495, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_text_line(curr_y + 1, 'STATUS', 8, 516, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, curr_y - 4, 558, curr_y - 4, r=0.0, g=0.0, b=0.0, width=1.5))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer)

    if not items:
        pc.ensure(40)
        pc.add_line('No records matching criteria.', 10, r=0.25, g=0.25, b=0.25)
    else:
        for idx, it in enumerate(items):
            pc.ensure(18)
            y = pc.y
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.80, 0.80, 0.80, 0.5))

            date_str = _sanitize_text(it.get('date', '-'))
            inv_str = _sanitize_text(it.get('sale_code', f"#{it.get('sale_id', '')}"))
            cust_str = _sanitize_text(str(it.get('customer_name', 'Walk-in'))[:14])
            prod_str = _sanitize_text(str(it.get('product_name', ''))[:(14 if is_multi_customer else 22)])
            qty_str = str(it.get('quantity', 0))
            price_str = f"{float(it.get('unit_price', 0)):.2f}"
            total_str = f"{float(it.get('total_amount', 0)):.2f}"
            st_raw = str(it.get('status', 'PAID')).upper()

            if is_multi_customer:
                pc._streams.append(_text_line(y, date_str, 7.5, 60, r=0.2, g=0.2, b=0.2))
                pc._streams.append(_text_line(y, inv_str, 7.5, 118, bold=True, r=0.0, g=0.0, b=0.0))
                pc._streams.append(_text_line(y, cust_str, 7.5, 175, bold=True, r=0.0, g=0.0, b=0.0))
                pc._streams.append(_text_line(y, prod_str, 7.5, 262, bold=True, r=0.0, g=0.0, b=0.0))
                pc._streams.append(_text_right(y, qty_str, 7.5, 375, r=0.0, g=0.0, b=0.0))
                pc._streams.append(_text_right(y, price_str, 7.5, 435, r=0.0, g=0.0, b=0.0))
                pc._streams.append(_text_right(y, total_str, 7.5, 495, bold=True, r=0.0, g=0.0, b=0.0))
                badge_x = 512
            else:
                pc._streams.append(_text_line(y, date_str, 8, 64, r=0.2, g=0.2, b=0.2))
                pc._streams.append(_text_line(y, inv_str, 8, 135, bold=True, r=0.0, g=0.0, b=0.0))
                pc._streams.append(_text_line(y, prod_str, 8.5, 195, bold=True, r=0.0, g=0.0, b=0.0))
                pc._streams.append(_text_right(y, qty_str, 8.5, 360, r=0.0, g=0.0, b=0.0))
                pc._streams.append(_text_right(y, price_str, 8.5, 430, r=0.0, g=0.0, b=0.0))
                pc._streams.append(_text_right(y, total_str, 8.5, 495, bold=True, r=0.0, g=0.0, b=0.0))
                badge_x = 510

            if st_raw == 'PAID':
                pc._streams.append(_badge(badge_x, y - 2, 'PAID', bg=(1.0, 1.0, 1.0), fg=(0.0, 0.0, 0.0), w=(40 if is_multi_customer else 44), h=13, size=6.5))
            elif st_raw == 'PARTIAL':
                pc._streams.append(_badge(badge_x, y - 2, 'PARTIAL', bg=(1.0, 1.0, 1.0), fg=(0.0, 0.0, 0.0), w=(40 if is_multi_customer else 44), h=13, size=6.5))
            else:
                pc._streams.append(_badge(badge_x, y - 2, 'UNPAID', bg=(1.0, 1.0, 1.0), fg=(0.0, 0.0, 0.0), w=(40 if is_multi_customer else 44), h=13, size=6.5))

            pc.skip(18)

    # ── Summary Block at End (Clean Open Layout, No Box) ──
    pc.ensure(110)
    pc.skip(10)
    y = pc.y
    box_w = 230.0
    box_x = 558.0 - box_w

    pc._streams.append(_line(54, y + 6, 558, y + 6, 0.0, 0.0, 0.0, 1.5))
    pc._streams.append(_text_line(y - 12, 'TOTAL BILLED:', 9, box_x, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y - 12, f'BDT {total_billed:.2f}', 10.5, 558, bold=True, r=0.0, g=0.0, b=0.0))

    pc._streams.append(_text_line(y - 28, 'TOTAL PAID:', 9, box_x, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y - 28, f'BDT {total_paid:.2f}', 10.5, 558, bold=True, r=0.0, g=0.0, b=0.0))

    pc._streams.append(_line(box_x, y - 36, 558, y - 36, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(y - 50, 'BALANCE DUE:', 9.5, box_x, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y - 50, f'BDT {total_due:.2f}', 11.5, 558, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_line(54, y - 58, 558, y - 58, 0.0, 0.0, 0.0, 1.5))

    # Statement Signatures (Manager & CEO Abdul Mannan)
    stmt_sign_y = y - 88
    pc._streams.append(_line(54, stmt_sign_y, 180, stmt_sign_y, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(stmt_sign_y - 10, "Manager Signature", 8, 54, bold=True, r=0.0, g=0.0, b=0.0))

    pc._streams.append(_line(400, stmt_sign_y, 558, stmt_sign_y, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(stmt_sign_y - 10, "CEO Abdul Mannan Signature", 8, 400, bold=True, r=0.0, g=0.0, b=0.0))

    pc.skip(abs(y - stmt_sign_y) + 20)
    pc.finish()
    return builder.build()


# ── 3. Sales Summary Report PDF ──────────────────────────────────────────────
def build_sales_report_pdf(report_data: dict[str, Any]) -> bytes:
    """Generate executive sales summary report PDF in pure black & white."""
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
    total_tx = int(report_data.get("total_transactions", 0))
    sales_tx = report_data.get("sales_transactions") or []
    product_sales = report_data.get("product_sales") or []

    def header(page_no: int) -> List[str]:
        ops = []
        if page_no == 1:
            ops.append(_text_line(762, 'MTRONIX', 20, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_text_line(748, 'SALES TRANSCRIPT & AUDIT REPORT', 8.5, 54, bold=True, r=0.2, g=0.2, b=0.2))
            ops.append(_text_line(735, f'Period: {report_data["period_label"]}  |  Generated: {generated}', 8, 54, r=0.25, g=0.25, b=0.25))
            ops.append(_text_line(723, f'Address: {MTRONIX_ADDRESS}', 8, 54, r=0.25, g=0.25, b=0.25))

            if qr_matrix:
                qr_size = len(qr_matrix) * qr_cell
                card_w = qr_size + 14
                card_h = qr_size + 20
                card_x = 558 - card_w
                card_y = 712
                qr_x = card_x + 7
                qr_y = card_y + 4
                ops.append(_rect_card(card_x, card_y, card_w, card_h, bg=(1.0, 1.0, 1.0), border=(0.0, 0.0, 0.0)))
                ops.append(_text_line(card_y + card_h - 10, 'SCAN LOCATION', 6.0, card_x + 4, bold=True, r=0.0, g=0.0, b=0.0))
                ops.append(_qr_pdf_stream(qr_matrix, qr_x, qr_y, qr_cell))

            ops.append(_line(54, 710, 558, 710, r=0.0, g=0.0, b=0.0, width=1.5))

        else:
            ops.append(_text_line(760, f'Mtronix Sales Report & Transcript (Page {page_no})', 9, 54, bold=True, r=0.0, g=0.0, b=0.0))
            ops.append(_line(54, 750, 558, 750, r=0.0, g=0.0, b=0.0, width=0.75))

        return ops

    def footer(page_no: int, is_last: bool) -> List[str]:
        return _make_footer_ops(page_no, is_last)

    builder = PdfBuilder(auto_print=True)
    pc = PageComposer(builder, header_fn=header, footer_fn=footer, page_top=690.0)

    # ── Monthly Revenue / Performance Summary (Open Clean Layout, No Box) ──
    pc.ensure(90)
    pc.add_line('Revenue Performance Summary', 11, bold=True, r=0.0, g=0.0, b=0.0)
    pc.skip(6)

    y = pc.y
    pc._streams.append(_line(54, y + 2, 558, y + 2, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(y - 12, 'TOTAL SALES INVOICED:', 8.5, 54, bold=True, r=0.25, g=0.25, b=0.25))
    pc._streams.append(_text_line(y - 12, f'BDT {tot_rev:.2f}', 10.0, 205, bold=True, r=0.0, g=0.0, b=0.0))

    pc._streams.append(_text_line(y - 28, 'COLLECTED CASH / PAID:', 8.5, 54, bold=True, r=0.25, g=0.25, b=0.25))
    pc._streams.append(_text_line(y - 28, f'BDT {tot_paid:.2f}', 10.0, 205, bold=True, r=0.0, g=0.0, b=0.0))

    pc._streams.append(_text_line(y - 12, 'UNPAID RECEIVABLE DUE:', 8.5, 340, bold=True, r=0.25, g=0.25, b=0.25))
    pc._streams.append(_text_line(y - 12, f'BDT {tot_due:.2f}', 10.0, 480, bold=True, r=0.0, g=0.0, b=0.0))

    pc._streams.append(_text_line(y - 28, 'ORDERS / TOTAL UNITS:', 8.5, 340, bold=True, r=0.25, g=0.25, b=0.25))
    pc._streams.append(_text_line(y - 28, f'{total_tx} Orders / {items_sold} Units', 10.0, 480, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_line(54, y - 36, 558, y - 36, 0.0, 0.0, 0.0, 1.0))
    pc.skip(48)

    # ── 1. Sales Transactions Transcript (Invoice Ledger) ──
    pc.ensure(80)
    pc.add_line('Sales Transactions Audit Transcript', 11, bold=True, r=0.0, g=0.0, b=0.0)
    pc.skip(6)

    y = pc.y
    pc._streams.append(_line(54, y + 12, 558, y + 12, 0.0, 0.0, 0.0, 1.5))
    pc._streams.append(_text_line(y + 2, 'DATE & TIME', 8, 56, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_line(y + 2, 'INVOICE #', 8, 140, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_line(y + 2, 'CUSTOMER', 8, 220, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_line(y + 2, 'ITEMS SUMMARY', 8, 320, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y + 2, 'TOTAL', 8, 455, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y + 2, 'PAID', 8, 508, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y + 2, 'STATUS', 8, 554, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_line(54, y - 4, 558, y - 4, 0.0, 0.0, 0.0, 1.5))
    pc.skip(20)

    if not sales_tx:
        pc.add_line('No sales transactions recorded in this period.', 9, r=0.25, g=0.25, b=0.25)
        pc.skip(14)
    else:
        for idx, tx in enumerate(sales_tx):
            pc.ensure(18)
            y = pc.y
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.85, 0.85, 0.85, 0.5))

            pc._streams.append(_text_line(y, _sanitize_text(tx['date'])[:14], 8, 56, r=0.2, g=0.2, b=0.2))
            pc._streams.append(_text_line(y, _sanitize_text(tx['code']), 8, 140, bold=True, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_line(y, _sanitize_text(tx['customer_name'])[:16], 8, 220, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_line(y, _sanitize_text(tx['items_summary'])[:22], 8, 320, r=0.25, g=0.25, b=0.25))
            pc._streams.append(_text_right(y, f"{tx['total_amount']:.2f}", 8.5, 455, bold=True, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_right(y, f"{tx['paid_amount']:.2f}", 8.5, 508, r=0.0, g=0.0, b=0.0))

            status_txt = 'PAID' if tx['payment_status'] == 'PAID' else ('PARTIAL' if tx['payment_status'] == 'PARTIAL' else 'UNPAID')
            pc._streams.append(_text_right(y, status_txt, 7.5, 554, bold=True, r=0.0, g=0.0, b=0.0))
            pc.skip(18)

    pc.skip(14)

    # ── 2. Product Sales Breakdown ──
    pc.ensure(80)
    pc.add_line('Product Sales Volume Breakdown', 11, bold=True, r=0.0, g=0.0, b=0.0)
    pc.skip(6)

    y = pc.y
    pc._streams.append(_line(54, y + 12, 558, y + 12, 0.0, 0.0, 0.0, 1.5))
    pc._streams.append(_text_line(y + 2, 'PRODUCT NAME', 8.5, 66, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_line(y + 2, 'SKU', 8.5, 290, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y + 2, 'QTY SOLD', 8.5, 410, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_text_right(y + 2, 'TOTAL SALES (BDT)', 8.5, 550, bold=True, r=0.0, g=0.0, b=0.0))
    pc._streams.append(_line(54, y - 4, 558, y - 4, 0.0, 0.0, 0.0, 1.5))
    pc.skip(20)

    if not product_sales:
        pc.add_line('No product breakdown available.', 9.5, r=0.25, g=0.25, b=0.25)
    else:
        for idx, item in enumerate(product_sales):
            pc.ensure(18)
            y = pc.y
            pc._streams.append(_line(54, y - 4, 558, y - 4, 0.80, 0.80, 0.80, 0.5))

            pc._streams.append(_text_line(y, _sanitize_text(item['product__name'])[:34], 9, 66, bold=True, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_line(y, _sanitize_text(item.get('product__sku') or '-'), 8.5, 290, r=0.25, g=0.25, b=0.25))
            pc._streams.append(_text_right(y, str(item['total_qty']), 9, 410, r=0.0, g=0.0, b=0.0))
            pc._streams.append(_text_right(y, f"{item['total_sales']:.2f}", 9.5, 550, bold=True, r=0.0, g=0.0, b=0.0))
            pc.skip(18)

    # Report Signatures (Manager & CEO Abdul Mannan)
    pc.ensure(60)
    pc.skip(18)
    rep_sign_y = pc.y
    pc._streams.append(_line(54, rep_sign_y, 180, rep_sign_y, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(rep_sign_y - 10, "Manager Signature", 8, 54, bold=True, r=0.0, g=0.0, b=0.0))

    pc._streams.append(_line(400, rep_sign_y, 558, rep_sign_y, 0.0, 0.0, 0.0, 1.0))
    pc._streams.append(_text_line(rep_sign_y - 10, "CEO Abdul Mannan Signature", 8, 400, bold=True, r=0.0, g=0.0, b=0.0))
    pc.skip(24)

    pc.finish()
    return builder.build()