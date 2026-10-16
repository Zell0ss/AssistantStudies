"""Embedder de la memoria (fase 2, D34): una interfaz y, hoy, una sola implementacion (OpenAI)."""
from abc import ABC, abstractmethod

from openai import OpenAI

MODELO_EMBEDDING = "text-embedding-3-small"
DIMENSION = 1536
# Dolares por millon de tokens de entrada de text-embedding-3-small (los embeddings no tienen salida).
# Fuente: H1-revision §2.4 (arquitecto, 2026-10-16); tarifa publica de OpenAI. Si cambia, se cambia aqui.
PRECIO_EMBEDDING_POR_MILLON = 0.02


class Embedder(ABC):
    """Detras de esta interfaz puede entrar el embedder local (D11) sin tocar el esquema."""

    dimension: int = DIMENSION

    @abstractmethod
    def embed(self, textos: list[str]) -> list[list[float]]:
        """Un vector por texto, en el mismo orden. Lanza si falla: quien llama decide degradar."""


class OpenAIEmbedder(Embedder):
    def __init__(self, api_key: str, modelo: str = MODELO_EMBEDDING, cliente=None):
        self._cliente = cliente or OpenAI(api_key=api_key)
        self._modelo = modelo
        self.tokens = 0  # suma de usage.total_tokens de cada llamada (como Orchestrator._track_usage)

    def embed(self, textos: list[str]) -> list[list[float]]:
        if not textos:
            return []
        respuesta = self._cliente.embeddings.create(model=self._modelo, input=list(textos))
        usage = getattr(respuesta, "usage", None)
        self.tokens += getattr(usage, "total_tokens", 0) or 0
        return [d.embedding for d in sorted(respuesta.data, key=lambda d: d.index)]

    def coste(self) -> float:
        return self.tokens * PRECIO_EMBEDDING_POR_MILLON / 1_000_000
