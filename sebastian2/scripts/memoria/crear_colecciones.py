"""Crea las colecciones Qdrant de la memoria (fase 2, D34): `<base>_catalogo` y `<base>_notas`.

Uso (desde sebastian2/):  python -m scripts.memoria.crear_colecciones [--produccion]

La base sale de `memory_collection` (config + SEBASTIAN_MEMORY_COLLECTION, D19). Se niega si no
termina en `_test` o `_dev`, salvo con `--produccion`, que es lo que ejecutara Josem. Crear una
coleccion que ya existe no es un error.
"""
import argparse
import sys

from qdrant_client.models import Distance, VectorParams

from core.memoria.embedder import DIMENSION

SUFIJOS = ("catalogo", "notas")
_SUFIJOS_SEGUROS = ("_test", "_dev")


def nombres(base: str) -> list[str]:
    return [f"{base}_{s}" for s in SUFIJOS]


def crear_colecciones(cliente, base: str) -> list[str]:
    """Crea las que falten (1536 dimensiones, coseno). Devuelve los nombres que existen al final."""
    existentes = {c.name for c in cliente.get_collections().collections}
    for nombre in nombres(base):
        if nombre not in existentes:
            cliente.create_collection(
                collection_name=nombre,
                vectors_config=VectorParams(size=DIMENSION, distance=Distance.COSINE),
            )
    return nombres(base)


def main(argv=None, *, base=None, cliente=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--produccion", action="store_true",
                        help="permite una base que no termina en _test ni _dev")
    args = parser.parse_args(argv)

    if base is None:
        from utils.config import get_config
        base = get_config()["memory_collection"]

    # La negativa va ANTES de abrir ningun cliente: con base de produccion no se llama a Qdrant.
    if not base.endswith(_SUFIJOS_SEGUROS) and not args.produccion:
        print(f"Rechazado: '{base}' no termina en _test ni _dev. Para produccion, --produccion "
              "(lo ejecuta Josem).", file=sys.stderr)
        return 2

    if cliente is None:
        from qdrant_client import QdrantClient
        cliente = QdrantClient(url="http://localhost:6333")
    for nombre in crear_colecciones(cliente, base):
        print(f"OK {nombre}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
