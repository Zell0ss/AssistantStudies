# tests/test_cuaderno_seeds.py
"""Seed gathering for Sprint 4 (El cuaderno). Best-effort: any failure degrades to
None, the despertar never crashes for a missing seed. Qdrant/filesystem are
mocked/faked — no real network calls."""
from unittest.mock import MagicMock

from scripts.cuaderno.seeds import get_random_memory, get_random_note_title


class TestGetRandomMemory:
    def test_returns_content_of_a_scrolled_point(self):
        qdrant = MagicMock()
        point = MagicMock()
        point.payload = {"content": "Mi cuñado Paco es alérgico a los frutos secos"}
        qdrant.scroll.return_value = ([point], None)

        result = get_random_memory(qdrant, collection="sebastian_memory")
        assert result == "Mi cuñado Paco es alérgico a los frutos secos"

    def test_empty_collection_returns_none(self):
        qdrant = MagicMock()
        qdrant.scroll.return_value = ([], None)

        result = get_random_memory(qdrant, collection="sebastian_memory")
        assert result is None

    def test_qdrant_failure_returns_none_not_raise(self):
        qdrant = MagicMock()
        qdrant.scroll.side_effect = RuntimeError("Qdrant is down")

        result = get_random_memory(qdrant, collection="sebastian_memory")
        assert result is None


class TestGetRandomNoteTitle:
    def test_returns_path_relative_to_vault_of_an_existing_md_file(self, tmp_path):
        wiki = tmp_path / "20-wiki"
        wiki.mkdir()
        (wiki / "RLHF.md").write_text("contenido que nunca debe leerse")

        result = get_random_note_title(tmp_path)
        assert result == "20-wiki/RLHF.md"

    def test_looks_recursively_in_subfolders(self, tmp_path):
        sub = tmp_path / "20-wiki" / "sub"
        sub.mkdir(parents=True)
        (sub / "nota.md").write_text("x")

        result = get_random_note_title(tmp_path)
        assert result == "20-wiki/sub/nota.md"

    def test_no_wiki_folder_returns_none_not_raise(self, tmp_path):
        result = get_random_note_title(tmp_path)
        assert result is None
