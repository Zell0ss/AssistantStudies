# tests/test_cuaderno_protocol.py
"""Pure protocol logic for Sprint 4 (El cuaderno): truncation, response parsing,
entry formatting. No I/O — file/API/Telegram side effects live in despertar.py."""
from scripts.cuaderno.protocol import truncate_notebook, parse_response, format_entry


class TestTruncateNotebook:
    def test_short_text_returned_unchanged(self):
        text = "algo corto"
        assert truncate_notebook(text, max_chars=20000, head_chars=2000, tail_chars=15000) == text

    def test_long_text_keeps_head_and_tail_and_says_what_was_cut(self):
        text = "A" * 10 + "M" * 30 + "Z" * 10  # 50 chars total
        result = truncate_notebook(text, max_chars=25, head_chars=10, tail_chars=10)

        assert result.startswith("A" * 10)
        assert result.endswith("Z" * 10)
        assert "M" * 30 not in result
        assert "truncad" in result.lower()
        assert "30" in result  # cuántos caracteres se omitieron


class TestParseResponse:
    def test_with_telegram_block_extracts_its_content(self):
        text = "Hoy pensé en X.\n\n<telegram>Buenas noches, señor.</telegram>\n\nMañana sigo."
        result = parse_response(text)
        assert result["telegram_message"] == "Buenas noches, señor."

    def test_without_telegram_block_returns_none(self):
        text = "Hoy no le digo nada a Josem, solo pienso por escrito."
        result = parse_response(text)
        assert result["telegram_message"] is None

    def test_malformed_unclosed_block_returns_none_not_raise(self):
        text = "Empiezo a escribirle algo <telegram>pero se corta"
        result = parse_response(text)
        assert result["telegram_message"] is None


class TestFormatEntry:
    def test_wraps_raw_text_with_dated_separator(self):
        entry = format_entry("Hoy pensé en X.", timestamp="2026-07-23 18:04")
        assert entry == "\n\n---\n## Despertar 2026-07-23 18:04\nHoy pensé en X."

    def test_keeps_telegram_tags_visible_in_notebook(self):
        raw = "Pensé esto.\n\n<telegram>Buenas noches.</telegram>"
        entry = format_entry(raw, timestamp="2026-07-23 18:04")
        assert "<telegram>" in entry
        assert raw in entry
