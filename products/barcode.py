"""
Barcode generation and utilities for Mtronix.
Supports Code 128 alphanumeric barcodes in pure Python (vector SVG and Base64 Data URI),
label formatting for thermal printers and A4 sticker sheets, and auto-SKU generation.
"""

import base64
import random
import time


# Standard Code 128 Pattern Table (indices 0 to 106)
# Each 6-digit string defines the module widths of 3 bars and 3 spaces.
# The stop code (index 106) has 7 digits (4 bars, 3 spaces).
CODE128_PATTERNS = [
    '212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312', '132212', '221213',
    '221312', '231212', '112232', '122132', '122231', '113222', '123122', '123221', '223211', '221132',
    '221231', '213212', '223112', '312131', '311222', '321122', '321221', '312212', '322112', '322211',
    '212123', '212321', '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313',
    '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121', '313121', '211331',
    '231131', '213113', '213311', '213131', '311123', '311321', '331121', '312113', '312311', '332111',
    '314111', '221411', '431111', '111224', '111422', '121124', '121421', '141122', '141221', '112214',
    '112412', '122114', '122411', '142112', '142211', '241211', '221114', '413111', '241112', '134111',
    '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112', '421211', '212141',
    '214121', '412121', '111143', '111341', '131141', '114113', '114311', '411113', '411311', '113141',
    '114131', '311141', '411131', '211412', '211214', '211232', '2331112'
]


def generate_code128_svg(
    data: str,
    height: int = 48,
    module_width: float = 1.8,
    include_text: bool = True,
    font_size: int = 12,
    quiet_zone_modules: int = 10,
    show_text: bool = None,
) -> str:
    """
    Generate an SVG vector string representing a Code 128 barcode for the given data.
    Code 128-B covers ASCII 32 to 126 (all standard letters, digits, and symbols).
    """
    if show_text is not None:
        include_text = show_text

    cleaned = (data or '').strip()
    if not cleaned:
        return ''

    # Values start with Start Code B (104)
    values = [104]
    for char in cleaned:
        code = ord(char) - 32
        if 0 <= code <= 94:
            values.append(code)
        else:
            # Fallback for characters outside standard printable ASCII
            values.append(ord('?') - 32)

    # Calculate Code 128 checksum: (StartCode + sum(position * code_val)) % 103
    checksum = (values[0] + sum(pos * val for pos, val in enumerate(values[1:], 1))) % 103
    values.append(checksum)
    values.append(106)  # Stop code

    pattern_str = ''.join(CODE128_PATTERNS[v] for v in values)

    quiet_zone = quiet_zone_modules * module_width
    current_x = quiet_zone
    rects = []
    is_bar = True

    for digit in pattern_str:
        width = int(digit) * module_width
        if is_bar:
            rects.append(f'<rect x="{current_x:.2f}" y="0" width="{width:.2f}" height="{height}" fill="#000000"/>')
        current_x += width
        is_bar = not is_bar

    total_width = current_x + quiet_zone
    total_height = height + (font_size + 6 if include_text else 0)

    text_element = ''
    if include_text:
        text_y = height + font_size + 1
        safe_text = cleaned.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        text_element = (
            f'<text x="{total_width / 2:.2f}" y="{text_y}" '
            f'text-anchor="middle" font-family="monospace, Courier New, monospace" '
            f'font-size="{font_size}" font-weight="700" fill="#000000" letter-spacing="1.5">{safe_text}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width:.2f} {total_height}" '
        f'width="{total_width:.2f}" height="{total_height}">'
        f'<rect width="100%" height="100%" fill="#ffffff"/>'
        f'{"".join(rects)}'
        f'{text_element}'
        f'</svg>'
    )
    return svg


def generate_code128_data_uri(
    data: str,
    height: int = 48,
    module_width: float = 1.8,
    include_text: bool = True,
    font_size: int = 12,
    show_text: bool = None,
) -> str:
    """
    Generate a base64 encoded SVG data URI ready to be used in <img src="...">.
    """
    svg = generate_code128_svg(
        data,
        height=height,
        module_width=module_width,
        include_text=include_text,
        font_size=font_size,
        show_text=show_text,
    )
    if not svg:
        return ''
    b64 = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    return f'data:image/svg+xml;base64,{b64}'


def generate_unique_product_sku(prefix: str = "MTX", name_hint: str = "") -> str:
    """
    Generate a unique, scannable SKU/barcode string in format [PREFIX]-XXXXX.
    Verifies uniqueness against the Product database.
    """
    import re
    from products.models import Product

    used_prefix = prefix.strip().upper() or "MTX"
    if name_hint and used_prefix == "MTX":
        clean_hint = re.sub(r'[^A-Za-z0-9]', '', name_hint).upper()
        if len(clean_hint) >= 3:
            used_prefix = clean_hint[:4]

    for _ in range(50):
        code_num = random.randint(10000, 99999)
        candidate = f"{used_prefix}-{code_num}"
        if not Product.objects.filter(sku__iexact=candidate).exists():
            return candidate

    ts_suffix = str(int(time.time()))[-5:]
    return f"{used_prefix}-{ts_suffix}"
