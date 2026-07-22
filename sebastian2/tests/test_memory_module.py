# tests/test_memory_module.py
"""MemoryModule tests. OpenAI + Qdrant are mocked — no real network calls, no cost.
Real-API integration is exercised separately by the golden harness (Sprint 3 Phase 3)."""
from unittest.mock import MagicMock, patch

import pytest

from modules.memory import MemoryModule

FAKE_VECTOR = [0.1] * 1536


def _mock_openai_embedding_response(vector=FAKE_VECTOR):
    resp = MagicMock()
    resp.data = [MagicMock(embedding=vector)]
    return resp


@pytest.fixture
def memory_module():
    with patch("modules.memory.OpenAI") as MockOpenAI, patch("modules.memory.QdrantClient") as MockQdrant:
        module = MemoryModule("sebastian_memory_test", openai_api_key="sk-fake")
        module._openai_mock = MockOpenAI.return_value
        module._qdrant_mock = MockQdrant.return_value
        yield module


class TestEmbed:
    def test_embed_returns_vector_from_openai(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        vector = memory_module.embed("cuñado alérgico a los frutos secos")
        assert vector == FAKE_VECTOR
        memory_module._openai_mock.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small", input="cuñado alérgico a los frutos secos"
        )


class TestStore:
    def test_store_success_returns_success_dict_with_id(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        result = memory_module.store("Paco es alérgico a los frutos secos", tags=["familia"])
        assert result["success"] is True
        assert "id" in result["data"]

    def test_store_calls_qdrant_upsert_with_correct_payload(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        memory_module.store("Paco es alérgico a los frutos secos", tags=["familia"])

        memory_module._qdrant_mock.upsert.assert_called_once()
        call_kwargs = memory_module._qdrant_mock.upsert.call_args.kwargs
        assert call_kwargs["collection_name"] == "sebastian_memory_test"
        point = call_kwargs["points"][0]
        assert point.payload["content"] == "Paco es alérgico a los frutos secos"
        assert point.payload["tags"] == ["familia"]
        assert point.payload["source"] == "conversation"
        assert "created_at" in point.payload

    def test_store_defaults_tags_to_empty_list(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        memory_module.store("contenido sin tags")
        point = memory_module._qdrant_mock.upsert.call_args.kwargs["points"][0]
        assert point.payload["tags"] == []

    def test_store_embedding_failure_returns_success_false_and_does_not_raise(self, memory_module):
        memory_module._openai_mock.embeddings.create.side_effect = RuntimeError("OpenAI is down")
        result = memory_module.store("algo importante")
        assert result["success"] is False
        assert result["data"] == {}

    def test_store_qdrant_failure_returns_success_false_and_does_not_raise(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        memory_module._qdrant_mock.upsert.side_effect = RuntimeError("Qdrant is down")
        result = memory_module.store("algo importante")
        assert result["success"] is False
        assert result["data"] == {}


class TestSearch:
    def test_search_returns_matches_from_qdrant(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        hit = MagicMock(score=0.87)
        hit.payload = {"content": "Paco es alérgico a los frutos secos", "tags": ["familia"]}
        memory_module._qdrant_mock.query_points.return_value = MagicMock(points=[hit])

        result = memory_module.search("alergia de paco")
        assert result["success"] is True
        assert len(result["data"]["matches"]) == 1
        assert result["data"]["matches"][0]["content"] == "Paco es alérgico a los frutos secos"
        assert result["data"]["matches"][0]["score"] == 0.87

    def test_search_passes_k_as_limit(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        memory_module._qdrant_mock.query_points.return_value = MagicMock(points=[])
        memory_module.search("algo", k=3)
        call_kwargs = memory_module._qdrant_mock.query_points.call_args.kwargs
        assert call_kwargs["limit"] == 3

    def test_search_defaults_k_to_5(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        memory_module._qdrant_mock.query_points.return_value = MagicMock(points=[])
        memory_module.search("algo")
        call_kwargs = memory_module._qdrant_mock.query_points.call_args.kwargs
        assert call_kwargs["limit"] == 5

    def test_search_no_matches_returns_success_true_empty_list(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        memory_module._qdrant_mock.query_points.return_value = MagicMock(points=[])
        result = memory_module.search("nada que ver")
        assert result["success"] is True
        assert result["data"]["matches"] == []

    def test_search_embedding_failure_returns_success_false_and_does_not_raise(self, memory_module):
        memory_module._openai_mock.embeddings.create.side_effect = RuntimeError("OpenAI is down")
        result = memory_module.search("algo")
        assert result["success"] is False
        assert result["data"] == {}

    def test_search_qdrant_failure_returns_success_false_and_does_not_raise(self, memory_module):
        memory_module._openai_mock.embeddings.create.return_value = _mock_openai_embedding_response()
        memory_module._qdrant_mock.query_points.side_effect = RuntimeError("Qdrant is down")
        result = memory_module.search("algo")
        assert result["success"] is False
        assert result["data"] == {}
