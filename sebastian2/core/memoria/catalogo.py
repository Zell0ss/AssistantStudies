"""Catalogo semantico de la memoria (fase 2, D34, D35): atributos y entidades en `<base>_catalogo`.

Se embeben **descripciones** (la frase del atributo, nombre + descripcion de la entidad), no alias
sueltos: un alias aislado no da contexto al embedder (truco de pictohistorias, briefing §4.3). El
catalogo solo devuelve candidatos con su puntuacion; quien decide si una es suficiente es el codigo
de resolucion (D8, D35), con los umbrales de `config.memoria.umbrales`.
"""
import uuid

from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

_ESPACIO_IDS = uuid.UUID("6f1e3a52-5b0a-4d0e-9a31-0c3f6c2d1b77")


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

    def indexar_atributos(self, atributos: list[dict] | None = None) -> int:
        """Embebe la `descripcion` de cada atributo (todos, o los que se pasen). Devuelve cuantos."""
        atributos = self._repo.listar_atributos() if atributos is None else atributos
        if not atributos:
            return 0
        vectores = self._embedder.embed([a["descripcion"] for a in atributos])
        puntos = [
            PointStruct(id=_punto_id("atributo", a["id"]), vector=v, payload={
                "tipo": "atributo", "id": a["id"], "nombre": a["nombre"], "estado": a["estado"],
            })
            for a, v in zip(atributos, vectores)
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
        puntos = self._qdrant.query_points(
            collection_name=self._coleccion, query=vector, limit=k,
            query_filter=Filter(must=condiciones),
        ).points
        return [{**p.payload, "score": p.score} for p in puntos]
