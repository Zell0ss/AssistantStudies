# modules/ticket_generator.py
"""
Generates images from decoded ticket data.
QR_CODE → qrcode, CODE_128/EAN → python-barcode, PDF417 → pdf417gen, AZTEC → image_b64.
"""
import io
import base64
from typing import Optional
from loguru import logger


def generate_image(ticket: dict) -> Optional[bytes]:
    type_ = ticket.get('type', '')
    value = ticket.get('value', '')

    if type_ == 'QR_CODE':
        return _gen_qr(value)
    if type_ in ('CODE_128', 'CODE_39', 'EAN_13', 'EAN_8', 'UPC_A', 'UPC_E'):
        return _gen_barcode(type_, value)
    if type_ == 'PDF417':
        return _gen_pdf417(value)
    if type_ == 'AZTEC':
        b64 = ticket.get('image_b64')
        if b64:
            try:
                return base64.b64decode(b64)
            except Exception as e:
                logger.error(f"Failed to decode AZTEC image_b64: {e}")
        return None

    logger.debug(f"No generator for ticket type: {type_}")
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


def _gen_pdf417(value: str) -> Optional[bytes]:
    try:
        from pdf417 import encode, render_image
        codes = encode(value)
        image = render_image(codes, scale=3, ratio=3)
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return buf.getvalue()
    except Exception as e:
        logger.error(f"PDF417 generation failed: {e}")
        return None
