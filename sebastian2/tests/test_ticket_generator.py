# tests/test_ticket_generator.py
import io
import pytest
from modules.ticket_generator import generate_image


class TestGenerateImage:
    def test_generate_qr_returns_bytes(self):
        ticket = {'type': 'QR_CODE', 'value': 'https://example.com/ticket/ABC'}
        result = generate_image(ticket)
        assert result is not None
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_generate_qr_is_valid_png(self):
        ticket = {'type': 'QR_CODE', 'value': 'test_value_123'}
        result = generate_image(ticket)
        assert result[:4] == b'\x89PNG'

    def test_generate_code128_returns_bytes(self):
        ticket = {'type': 'CODE_128', 'value': '1234567890'}
        result = generate_image(ticket)
        assert result is not None
        assert isinstance(result, bytes)

    def test_generate_pdf417_returns_bytes(self):
        ticket = {'type': 'PDF417', 'value': 'test_pdf417_data'}
        result = generate_image(ticket)
        assert result is not None
        assert isinstance(result, bytes)

    def test_generate_aztec_from_image_b64(self):
        import base64
        from PIL import Image
        img = Image.new('RGB', (10, 10), color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        fake_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        ticket = {'type': 'AZTEC', 'value': 'aztec_data', 'image_b64': fake_b64}
        result = generate_image(ticket)
        assert result is not None
        assert result == buf.getvalue()

    def test_generate_aztec_without_b64_returns_none(self):
        ticket = {'type': 'AZTEC', 'value': 'aztec_data'}
        result = generate_image(ticket)
        assert result is None

    def test_generate_unknown_type_returns_none(self):
        ticket = {'type': 'UNKNOWN_FORMAT', 'value': 'data'}
        result = generate_image(ticket)
        assert result is None
