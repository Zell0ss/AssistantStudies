# tests/test_ticket_decoder.py
import io
import pytest
import qrcode
from PIL import Image
from modules.ticket_decoder import decode_image


def _make_qr_bytes(value: str) -> bytes:
    img = qrcode.make(value)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_barcode_bytes(value: str) -> bytes:
    import barcode
    from barcode.writer import ImageWriter
    bc = barcode.get_barcode_class('code128')(value, writer=ImageWriter())
    buf = io.BytesIO()
    bc.write(buf)
    return buf.getvalue()


class TestDecodeImage:
    def test_decode_qr_returns_result(self):
        image_bytes = _make_qr_bytes("https://example.com/ticket/ABC123")
        results = decode_image(image_bytes)
        assert len(results) >= 1
        assert any(r['value'] == "https://example.com/ticket/ABC123" for r in results)

    def test_decode_qr_type_is_qr_code(self):
        image_bytes = _make_qr_bytes("test_value")
        results = decode_image(image_bytes)
        assert any(r['type'] == 'QR_CODE' for r in results)

    def test_decode_returns_type_and_value_keys(self):
        image_bytes = _make_qr_bytes("keys_test")
        results = decode_image(image_bytes)
        assert len(results) >= 1
        for r in results:
            assert 'type' in r
            assert 'value' in r

    def test_empty_image_returns_empty_list(self):
        img = Image.new('RGB', (200, 200), color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        results = decode_image(buf.getvalue())
        assert results == []

    def test_qr_no_image_b64(self):
        image_bytes = _make_qr_bytes("no_aztec")
        results = decode_image(image_bytes)
        qr_results = [r for r in results if r['type'] == 'QR_CODE']
        if qr_results:
            assert 'image_b64' not in qr_results[0]
