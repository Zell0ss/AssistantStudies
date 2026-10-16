"""H1-revision R3: OpenAIEmbedder acumula usage.total_tokens (sin red)."""
from types import SimpleNamespace

import pytest

from core.memoria.embedder import PRECIO_EMBEDDING_POR_MILLON, OpenAIEmbedder


class ClienteFalso:
    def __init__(self, tokens_por_llamada):
        self._tokens = list(tokens_por_llamada)
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, model, input):
        datos = [SimpleNamespace(index=i, embedding=[float(i)]) for i in reversed(range(len(input)))]
        return SimpleNamespace(data=datos, usage=SimpleNamespace(total_tokens=self._tokens.pop(0)))


def test_acumula_tokens_y_calcula_coste():
    embedder = OpenAIEmbedder("k", cliente=ClienteFalso([300_000, 700_000]))
    embedder.embed(["a", "b"])
    embedder.embed(["c"])
    assert embedder.tokens == 1_000_000
    assert embedder.coste() == pytest.approx(0.02)
    assert PRECIO_EMBEDDING_POR_MILLON == 0.02


def test_devuelve_vectores_en_orden_de_entrada():
    embedder = OpenAIEmbedder("k", cliente=ClienteFalso([5]))
    assert embedder.embed(["a", "b", "c"]) == [[0.0], [1.0], [2.0]]


def test_sin_textos_no_llama_ni_suma():
    embedder = OpenAIEmbedder("k", cliente=ClienteFalso([]))
    assert embedder.embed([]) == []
    assert embedder.tokens == 0
