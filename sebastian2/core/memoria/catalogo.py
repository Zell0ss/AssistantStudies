"""Catalogo semantico de la memoria (fase 2, D34, D35): atributos y entidades en `<base>_catalogo`.

Se embeben **descripciones** (la frase del atributo, nombre + descripcion de la entidad), no alias
sueltos: un alias aislado no da contexto al embedder (truco de pictohistorias, briefing §4.3). El
catalogo solo devuelve candidatos con su puntuacion; quien decide si una es suficiente es el codigo
de resolucion (D8, D35), con los umbrales de `config.memoria.umbrales`.
"""
import uuid

from logcentral_client import get_logger
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

logger = get_logger("sebastian")

_ESPACIO_IDS = uuid.UUID("6f1e3a52-5b0a-4d0e-9a31-0c3f6c2d1b77")


# Que se embebe por atributo (H1-revision §2.2). La puntuacion de un atributo es la de su mejor punto.
REPRESENTACIONES = ("descripcion", "nombre_descripcion", "con_ejemplos")
MAX_EJEMPLOS = 3


def textos_de(atributo: dict, representacion: str) -> list[str]:
    """Los textos que se embeben para un atributo, cada uno como punto propio con el mismo id."""
    if representacion == "descripcion":
        return [atributo["descripcion"]]
    if representacion == "nombre_descripcion":
        return [f"{atributo['nombre']}: {atributo['descripcion']}"]
    if representacion == "con_ejemplos":
        return [atributo["descripcion"], *(atributo.get("ejemplos") or [])[:MAX_EJEMPLOS]]
    raise ValueError(f"representacion desconocida: {representacion!r}")


def sufijo_catalogo(base: str) -> str:
    return f"{base}_catalogo"


def _punto_id(tipo: str, ident: int) -> str:
    # Determinista: reindexar la misma fila pisa el mismo punto (idempotente).
    return str(uuid.uuid5(_ESPACIO_IDS, f"{tipo}:{ident}"))


class Catalogo:
    def __init__(self, repo, embedder, qdrant, base: str):
        self._repo = repo
        self._embedder = embedder
        self._qdrant = qdrant
        self._coleccion = sufijo_catalogo(base)

    # --- Indexado ------------------------------------------------------------------------

    def indexar_atributos(self, atributos: list[dict] | None = None,
                          representacion: str = "descripcion") -> int:
        """Embebe cada atributo (todos, o los que se pasen) segun `representacion`. Devuelve cuantos puntos."""
        atributos = self._repo.listar_atributos() if atributos is None else atributos
        pares = [(a, n, t) for a in atributos for n, t in enumerate(textos_de(a, representacion))]
        if not pares:
            return 0
        vectores = self._embedder.embed([t for _, _, t in pares])
        puntos = [
            PointStruct(id=_punto_id(f"atributo:{n}", a["id"]), vector=v, payload={
                "tipo": "atributo", "id": a["id"], "nombre": a["nombre"], "estado": a["estado"],
            })
            for (a, n, _), v in zip(pares, vectores)
        ]
        self._qdrant.upsert(collection_name=self._coleccion, points=puntos)
        return len(puntos)

    def indexar_entidad(self, entidad: dict) -> None:
        texto = f"{entidad['nombre']}: {entidad.get('descripcion') or entidad['tipo']}"
        vector = self._embedder.embed([texto])[0]
        self._qdrant.upsert(collection_name=self._coleccion, points=[PointStruct(
            id=_punto_id("entidad", entidad["id"]), vector=vector, payload={
                "tipo": "entidad", "id": entidad["id"], "user_id": entidad["user_id"],
                "nombre": entidad["nombre"], "tipo_entidad": entidad["tipo"],
            })])

    # --- Busqueda ------------------------------------------------------------------------

    def buscar_atributos(self, texto: str, k: int = 3) -> list[dict]:
        """Atributos candidatos, de mayor a menor puntuacion (coseno)."""
        return self._buscar(texto, [FieldCondition(key="tipo", match=MatchValue(value="atributo"))], k)

    def buscar_entidades(self, user_id: str, texto: str, k: int = 3) -> list[dict]:
        """Entidades candidatas **de ese usuario** (D33): el filtro va en la consulta, no despues."""
        return self._buscar(texto, [
            FieldCondition(key="tipo", match=MatchValue(value="entidad")),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ], k)

    @staticmethod
    def margen(candidatos: list[dict]) -> float:
        """Distancia entre la mejor y la segunda. Con una sola candidata, su propia puntuacion."""
        if not candidatos:
            return 0.0
        if len(candidatos) == 1:
            return candidatos[0]["score"]
        return candidatos[0]["score"] - candidatos[1]["score"]

    def _buscar(self, texto: str, condiciones: list, k: int) -> list[dict]:
        vector = self._embedder.embed([texto])[0]
        # Un atributo puede tener varios puntos (descripcion + ejemplos): se piden de mas y se queda
        # cada uno una sola vez, con su mejor puntuacion.
        puntos = self._qdrant.query_points(
            collection_name=self._coleccion, query=vector, limit=k * (MAX_EJEMPLOS + 2),
            query_filter=Filter(must=condiciones),
        ).points
        vistos, candidatos = set(), []
        for p in puntos:
            clave = (p.payload["tipo"], p.payload["id"])
            if clave in vistos:
                continue
            vistos.add(clave)
            candidatos.append({**p.payload, "score": p.score})
        return candidatos[:k]
