# modules/ticket_generator.py
"""
Generates images from decoded ticket data.

QR_CODE        → qrcode (clean, configurable error correction)
CODE_128/EAN   → python-barcode (standard linear barcodes)
AZTEC          → zxingcpp (via value_b64 raw bytes or value text)
DATA_MATRIX    → zxingcpp (via value_b64 raw bytes or value text)
PDF417         → zxingcpp (via value_b64 raw bytes or value text)

Backward compat: tickets stored with image_b64 (old format) still work.
"""
import io
import base64
from typing import Optional
from loguru import logger

# Maps our type strings to zxingcpp.BarcodeFormat member names
_ZXING_FORMAT_MAP = {
    'AZTEC': 'Aztec',
    'DATA_MATRIX': 'DataMatrix',
    'PDF417': 'PDF417',
    'QR_CODE': 'QRCode',
}


def generate_image(ticket: dict) -> Optional[bytes]:
    type_ = ticket.get('type', '')

    if type_ == 'QR_CODE':
        return _gen_qr(ticket.get('value', ''))

    if type_ in ('CODE_128', 'CODE_39', 'EAN_13', 'EAN_8', 'UPC_A', 'UPC_E'):
        return _gen_barcode(type_, ticket.get('value', ''))

    if type_ in ('AZTEC', 'DATA_MATRIX', 'PDF417'):
        return _gen_zxing(type_, ticket)

    logger.debug(f"No generator for ticket type: {type_}")
    return None


def _gen_zxing(type_: str, ticket: dict) -> Optional[bytes]:
    """
    Generate image using zxingcpp.create_barcode().

    Uses value_b64 (raw bytes) when available for lossless round-trip.
    Falls back to value (text) for simple/text tickets.
    Falls back to stored image_b64 for tickets scanned before this version.
    """
    try:
        import zxingcpp
        import numpy as np
        from PIL import Image

        fmt_name = _ZXING_FORMAT_MAP[type_]
        fmt = getattr(zxingcpp.BarcodeFormat, fmt_name)

        value_b64 = ticket.get('value_b64')
        if value_b64:
            raw_bytes = base64.b64decode(value_b64)
            bc = zxingcpp.create_barcode(raw_bytes, fmt)
        else:
            bc = zxingcpp.create_barcode(ticket.get('value', ''), fmt)

        pil_img = Image.fromarray(np.asarray(zxingcpp.write_barcode_to_image(bc)))
        # Scale up for readability (zxingcpp produces minimal pixel images)
        w, h = pil_img.size
        scale = max(1, 300 // max(w, h))
        if scale > 1:
            pil_img = pil_img.resize((w * scale, h * scale), Image.NEAREST)

        buf = io.BytesIO()
        pil_img.save(buf, format='PNG')
        return buf.getvalue()

    except Exception as e:
        logger.error(f"{type_} generation via zxingcpp failed: {e}")

    # Backward compat: tickets stored with image_b64 (old format)
    image_b64 = ticket.get('image_b64')
    if image_b64:
        try:
            return base64.b64decode(image_b64)
        except Exception as e:
            logger.error(f"Failed to decode {type_} image_b64 fallback: {e}")

    return None


def _gen_qr(value: str) -> Optional[bytes]:
    try:
        import qrcode
        img = qrcode.make(value)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception as e:
        logger.error(f"QR generation failed: {e}")
        return None


def _gen_barcode(type_: str, value: str) -> Optional[bytes]:
    try:
        import barcode
        from barcode.writer import ImageWriter
        format_map = {
            'CODE_128': 'code128', 'CODE_39': 'code39',
            'EAN_13': 'ean13', 'EAN_8': 'ean8',
            'UPC_A': 'upca', 'UPC_E': 'upce',
        }
        barcode_name = format_map.get(type_)
        if not barcode_name:
            return None
        # EAN/UPC: python-barcode adds check digit, strip it if already present
        enc_value = value
        if type_ == 'EAN_13' and len(value) == 13:
            enc_value = value[:12]
        elif type_ == 'EAN_8' and len(value) == 8:
            enc_value = value[:7]
        elif type_ == 'UPC_A' and len(value) == 12:
            enc_value = value[:11]
        bc_class = barcode.get_barcode_class(barcode_name)
        bc = bc_class(enc_value, writer=ImageWriter())
        buf = io.BytesIO()
        bc.write(buf)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Barcode generation failed for {type_}: {e}")
        return None
