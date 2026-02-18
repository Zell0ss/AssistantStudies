# modules/ticket_decoder.py
"""
QR code and barcode decoder using zxing-cpp (primary) and pyzbar (fallback).
"""
import io
import base64
from PIL import Image, ImageOps
from loguru import logger

_ZXING_TYPE_MAP = {
    'QRCode': 'QR_CODE',
    'Aztec': 'AZTEC',
    'PDF417': 'PDF417',
    'Code128': 'CODE_128',
    'Code39': 'CODE_39',
    'EAN13': 'EAN_13',
    'EAN8': 'EAN_8',
    'DataMatrix': 'DATA_MATRIX',
    'UPCA': 'UPC_A',
    'UPCE': 'UPC_E',
}

_PYZBAR_TYPE_MAP = {
    'QRCODE': 'QR_CODE',
    'CODE128': 'CODE_128',
    'CODE39': 'CODE_39',
    'EAN13': 'EAN_13',
    'EAN8': 'EAN_8',
    'UPCA': 'UPC_A',
    'UPCE': 'UPC_E',
    'PDF417': 'PDF417',
    'AZTEC': 'AZTEC',
    'DATAMATRIX': 'DATA_MATRIX',
}


def _preprocess(image_bytes: bytes) -> tuple:
    """Grayscale + threshold to improve decode reliability."""
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    gray = ImageOps.grayscale(img)
    return gray, image_bytes


def _decode_zxing(img: Image.Image) -> list:
    try:
        import zxingcpp
        results = zxingcpp.read_barcodes(img)
        decoded = []
        for r in results:
            if not r.valid:
                continue
            # Use format.name — verified working in zxingcpp 3.x (returns e.g. 'QRCode')
            fmt_name = r.format.name if hasattr(r.format, 'name') else str(r.format)
            type_name = _ZXING_TYPE_MAP.get(fmt_name, fmt_name.upper())
            decoded.append({'type': type_name, 'value': r.text})
        return decoded
    except Exception as e:
        logger.debug(f"zxing-cpp decode failed: {e}")
        return []


def _decode_pyzbar(img: Image.Image) -> list:
    try:
        from pyzbar.pyzbar import decode
        results = decode(img)
        decoded = []
        for r in results:
            type_name = _PYZBAR_TYPE_MAP.get(r.type, r.type)
            try:
                value = r.data.decode('utf-8')
            except UnicodeDecodeError:
                value = r.data.decode('latin-1')
            decoded.append({'type': type_name, 'value': value})
        return decoded
    except Exception as e:
        logger.debug(f"pyzbar decode failed: {e}")
        return []


def decode_image(image_bytes: bytes) -> list:
    """
    Decode QR codes and barcodes from image bytes.
    Returns list of {type, value} dicts. Empty list if nothing found.
    AZTEC results include image_b64 for later display.
    """
    processed_img, original_bytes = _preprocess(image_bytes)

    results = _decode_zxing(processed_img)
    if not results:
        logger.debug("zxing-cpp found nothing, trying pyzbar")
        results = _decode_pyzbar(processed_img)

    # Deduplicate by value
    seen = set()
    deduped = []
    for r in results:
        if r['value'] not in seen:
            seen.add(r['value'])
            deduped.append(r)

    # Attach image_b64 for types with no generation library (AZTEC, DATA_MATRIX)
    NO_GEN_TYPES = {'AZTEC', 'DATA_MATRIX'}
    for r in deduped:
        if r['type'] in NO_GEN_TYPES:
            r['image_b64'] = base64.b64encode(original_bytes).decode('utf-8')

    logger.info(f"decode_image: {len(deduped)} code(s) found: {[r['type'] for r in deduped]}")
    return deduped
