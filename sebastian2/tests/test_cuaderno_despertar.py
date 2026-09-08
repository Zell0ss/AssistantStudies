# tests/test_cuaderno_despertar.py
"""Orchestration for a single despertar. Anthropic/Qdrant/Telegram are injected and
mocked — real network calls only happen in the supervised manual run (FASE 4)."""
from unittest.mock import MagicMock

from scripts.cuaderno.despertar import despertar, _build_seeds_block, _resolve_chat_id


def _fake_client(response_text: str) -> MagicMock:
    client = MagicMock()
    content_block = MagicMock(text=response_text)
    client.messages.create.return_value = MagicMock(content=[content_block])
    return client


def _fake_qdrant_no_memories() -> MagicMock:
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([], None)
    return qdrant


class TestDespertar:
    def test_appends_raw_response_to_notebook_file(self, tmp_path):
        notebook = tmp_path / "cuaderno.md"
        notebook.write_text("Contenido previo.")
        client = _fake_client("Hoy pensé en X.")

        despertar(
            client=client, qdrant_client=_fake_qdrant_no_memories(), bot=MagicMock(),
            notebook_path=notebook, vault_path=tmp_path, chat_id=123,
        )

        content = notebook.read_text()
        assert content.startswith("Contenido previo.")
        assert "Hoy pensé en X." in content
        assert "## Despertar" in content

    def test_no_telegram_block_does_not_send_message(self, tmp_path):
        notebook = tmp_path / "cuaderno.md"
        notebook.write_text("")
        bot = MagicMock()
        client = _fake_client("Hoy no le digo nada a Josem.")

        despertar(
            client=client, qdrant_client=_fake_qdrant_no_memories(), bot=bot,
            notebook_path=notebook, vault_path=tmp_path, chat_id=123,
        )

        bot.send_message.assert_not_called()

    def test_telegram_block_sends_message_with_marker(self, tmp_path):
        notebook = tmp_path / "cuaderno.md"
        notebook.write_text("")
        bot = MagicMock()
        client = _fake_client("Pensando...\n\n<telegram>Buenas noches, señor.</telegram>")

        despertar(
            client=client, qdrant_client=_fake_qdrant_no_memories(), bot=bot,
            notebook_path=notebook, vault_path=tmp_path, chat_id=123,
        )

        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == 123
        assert call_kwargs["text"] == "🌱 — Buenas noches, señor."

    def test_dry_run_does_not_write_notebook_or_send_telegram(self, tmp_path):
        notebook = tmp_path / "cuaderno.md"
        notebook.write_text("Contenido original.")
        bot = MagicMock()
        client = _fake_client("<telegram>Hola.</telegram>")

        despertar(
            client=client, qdrant_client=_fake_qdrant_no_memories(), bot=bot,
            notebook_path=notebook, vault_path=tmp_path, chat_id=123, dry_run=True,
        )

        assert notebook.read_text() == "Contenido original."
        bot.send_message.assert_not_called()

    def test_dry_run_still_reports_what_would_have_happened(self, tmp_path):
        notebook = tmp_path / "cuaderno.md"
        notebook.write_text("")
        client = _fake_client("<telegram>Hola.</telegram>")

        result = despertar(
            client=client, qdrant_client=_fake_qdrant_no_memories(), bot=MagicMock(),
            notebook_path=notebook, vault_path=tmp_path, chat_id=123, dry_run=True,
        )

        assert result["spoke"] is True
        assert result["telegram_message"] == "Hola."

    def test_memory_seed_does_not_attribute_the_fact_to_sebastian(self, tmp_path):
        # Regression: memories stored via mark_as_memorable are things Josem asked
        # Sebastian to remember (often about Josem himself, e.g. "Tengo alergia..."),
        # not facts about Sebastian the bot. "de Sebastian" reads as the latter and
        # led a real despertar to write "Sebastian es alérgico al ácido acetilsalicílico".
        qdrant = MagicMock()
        point = MagicMock()
        point.payload = {"content": "Tengo alergia al ácido acetilsalicílico"}
        qdrant.scroll.return_value = ([point], None)

        seeds_block = _build_seeds_block(tmp_path, qdrant, "sebastian_memory")

        assert "Tengo alergia al ácido acetilsalicílico" in seeds_block
        assert "memoria al azar de Sebastian" not in seeds_block

    def test_missing_notebook_file_starts_from_empty(self, tmp_path):
        notebook = tmp_path / "does_not_exist_yet.md"
        client = _fake_client("Primer despertar.")

        despertar(
            client=client, qdrant_client=_fake_qdrant_no_memories(), bot=MagicMock(),
            notebook_path=notebook, vault_path=tmp_path, chat_id=123,
        )

        assert "Primer despertar." in notebook.read_text()


class TestResolveChatId:
    # Regression: despertar.py usaba authorized_ids[0] como chat_id — con más de
    # un authorized_id en config.yaml, el cuaderno llevaba desde el primer
    # despertar mandando sus mensajes <telegram> a un chat que no era el de Josem.

    def test_usa_cuaderno_chat_id_si_esta_en_config(self):
        config = {"cuaderno_chat_id": 815566372, "authorized_ids": [111, 222, 815566372]}
        assert _resolve_chat_id(config) == 815566372

    def test_cae_a_authorized_ids_0_si_no_esta_configurado(self):
        config = {"authorized_ids": [111, 222, 815566372]}
        assert _resolve_chat_id(config) == 111

    def test_cuaderno_chat_id_tiene_prioridad_aunque_no_sea_el_primero(self):
        config = {"cuaderno_chat_id": 815566372, "authorized_ids": [815566372, 111]}
        assert _resolve_chat_id(config) == 815566372
