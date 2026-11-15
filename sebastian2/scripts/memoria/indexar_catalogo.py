"""Indexa el catálogo de la memoria en `<base>_catalogo` (fase 2, H4: adición, ver H4-informe).

Uso (desde sebastian2/):  python -m scripts.memoria.indexar_catalogo [--produccion]

**[API, OpenAI, menos de 0,001 $]**: embebe la descripción de todos los atributos (las semillas y los que la migración o
una conversación hayan creado) y las entidades del propietario del vault. Sin esto, en producción `<base>_catalogo` está
vacío —`crear_colecciones.py` solo crea las colecciones— y la resolución semántica (D35) no encuentra ningún atributo.

Escribe SOLO en `<base>_catalogo`, con ids deterministas: repetirlo pisa los mismos puntos (idempotente). No escribe en la
BD ni en `<base>_notas`. Va después de `migrar_sprint3.py`, para que `presion_neumaticos` y la entidad «coche» entren.
Se niega si la base no termina en `_test` o `_dev`, salvo con `--produccion` (lo ejecuta Josem).
"""
import argparse
import sys

from core.memoria.catalogo import Catalogo
from core.memoria.repositorio import RepositorioMemoria

_COLECCION_SEGURA = ("_test", "_dev")


def indexar(db, qdrant, embedder, base: str, user_id: str) -> dict:
    repo = RepositorioMemoria(db)
    catalogo = Catalogo(repo, embedder, qdrant, base)
    atributos = catalogo.indexar_atributos()
    entidades = repo.listar_entidades(user_id)
    for e in entidades:
        catalogo.indexar_entidad(e)
    return {"atributos": atributos, "entidades": len(entidades)}


def main(argv=None, *, base=None, db=None, qdrant=None, embedder=None, user_id=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--produccion", action="store_true", help="permite una base que no termina en _test ni _dev")
    args = parser.parse_args(argv)

    config = None
    if base is None or user_id is None or embedder is None:
        from utils.config import get_config
        config = get_config()
    base = base if base is not None else config["memory_collection"]

    # La negativa va ANTES de abrir ningún cliente: con base de producción no se llama a OpenAI ni a Qdrant.
    if not base.endswith(_COLECCION_SEGURA) and not args.produccion:
        print(f"Rechazado: '{base}' no termina en _test ni _dev. Para producción, --produccion (lo ejecuta Josem).",
              file=sys.stderr)
        return 2
    if user_id is None:
        from core.memoria.ajustes import propietario_vault
        user_id = propietario_vault(config)
    if not user_id:
        print("Rechazado: no hay propietario del vault (memoria.propietario_vault o cuaderno_chat_id).", file=sys.stderr)
        return 2
    if db is None:
        from db.connection import get_connection
        db = get_connection()
    if qdrant is None:
        from qdrant_client import QdrantClient
        qdrant = QdrantClient(url=(config or {}).get("qdrant_url", "http://localhost:6333"))
    if embedder is None:
        from core.memoria.embedder import OpenAIEmbedder
        embedder = OpenAIEmbedder(config["openai_apikey"])

    resultado = indexar(db, qdrant, embedder, base, user_id)
    print(f"OK {base}_catalogo: {resultado['atributos']} atributo(s) y {resultado['entidades']} entidad(es) de {user_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
