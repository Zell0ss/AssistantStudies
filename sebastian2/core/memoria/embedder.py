"""Embedder de la memoria (fase 2, D34): una interfaz y, hoy, una sola implementacion (OpenAI)."""
from abc import ABC, abstractmethod

from openai import OpenAI

MODELO_EMBEDDING = "text-embedding-3-small"
DIMENSION = 1536


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

    def embed(self, textos: list[str]) -> list[list[float]]:
        if not textos:
            return []
        respuesta = self._cliente.embeddings.create(model=self._modelo, input=list(textos))
        return [d.embedding for d in sorted(respuesta.data, key=lambda d: d.index)]
