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

    def test_generate_aztec_returns_png(self):
        # zxingcpp can now generate Aztec from text value directly
        ticket = {'type': 'AZTEC', 'value': 'aztec_data_test'}
        result = generate_image(ticket)
        assert result is not None
        assert result[:4] == b'\x89PNG'

    def test_generate_data_matrix_returns_png(self):
        ticket = {'type': 'DATA_MATRIX', 'value': '728515O57X69UG'}
        result = generate_image(ticket)
        assert result is not None
        assert result[:4] == b'\x89PNG'

    def test_generate_unknown_type_returns_none(self):
        ticket = {'type': 'UNKNOWN_FORMAT', 'value': 'data'}
        result = generate_image(ticket)
        assert result is None
