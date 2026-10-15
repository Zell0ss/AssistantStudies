"""Dobles para las pruebas de la memoria (fase 2, H1): ningun test unitario llama a OpenAI ni a Qdrant."""
import hashlib
import math
import re

from qdrant_client import QdrantClient

from core.memoria.embedder import Embedder

DIMENSION = 1536


class EmbedderFalso(Embedder):
    """Determinista y sin red: cada palabra suma 1 en un hueco fijo (hash) de un vector de 1536.

    Dos textos que comparten palabras puntuan alto con coseno; dos que no, ~0. Basta para probar
    el catalogo sin depender de lo que opine OpenAI.
    """

    dimension = DIMENSION

    def __init__(self):
        self.llamadas = []

    def embed(self, textos):
        self.llamadas.append(list(textos))
        return [self._vector(t) for t in textos]

    def _vector(self, texto):
        v = [0.0] * DIMENSION
        for palabra in re.findall(r"\w+", texto.lower()):
            hueco = int(hashlib.sha256(palabra.encode()).hexdigest(), 16) % DIMENSION
            v[hueco] += 1.0
        norma = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norma for x in v]


def qdrant_en_memoria():
    """Cliente Qdrant que vive en el proceso (sin servidor): misma API y mismo coseno que el real."""
    return QdrantClient(":memory:")


class QdrantQueDejaMarca:
    """Cliente falso: cualquier uso queda anotado en `llamadas`."""

    def __init__(self):
        self.llamadas = []

    def __getattr__(self, nombre):
        def registrar(*args, **kwargs):
            self.llamadas.append(nombre)
            return None

        return registrar
