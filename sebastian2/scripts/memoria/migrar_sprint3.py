"""Migra los hechos de Sprint 3 (colección plana de Qdrant) a la memoria nueva de MariaDB (fase 2, H4, D18).

Uso (desde sebastian2/):  python -m scripts.memoria.migrar_sprint3 [--dry-run] [--produccion]

- **Solo lectura sobre Qdrant:** lee la colección base (`memory_collection`, la de Sprint 3) con `scroll`. No escribe
  en ninguna colección de Qdrant (ni en `<base>_catalogo` ni en `<base>_notas`): el catálogo se indexa aparte, con
  `indexar_catalogo.py`.
- **Mapa explícito en el código** (`MAPA`): solo se migra lo que está en él. Lo que no, se enseña como «sin mapa» y no
  se toca. Los hechos llevan `origen='migracion'` y `fuente_id = NULL`: no se inventa una fuente (H3-revision §5.4).
- **Idempotente:** si el hecho ya existe con origen `migracion` (vigente o retirado) no se vuelve a escribir. Lo que el
  usuario haya pedido olvidar después (D42) no resucita.
- `--dry-run` enseña lo que haría (y de qué texto sale cada hecho) sin escribir nada.
- Se niega si la BD o la colección no son de test/desarrollo, salvo con `--produccion`, que es lo que ejecutará Josem
  con `SEBASTIAN_DB_NAME` y `SEBASTIAN_MEMORY_COLLECTION` explícitos (D19): el `config.yaml` apunta a desarrollo.
"""
import argparse
import sys
from dataclasses import dataclass

from core.memoria.normalizar import normalizar
from core.memoria.repositorio import RepositorioMemoria

_BD_SEGURAS = ("sebastian_test", "sebastian_dev")
_COLECCION_SEGURA = ("_test", "_dev")


@dataclass(frozen=True)
class Regla:
    """Un hecho del mapa: el texto de Sprint 3 casa si contiene TODAS las palabras de `contiene` (normalizadas)."""
    nombre: str
    contiene: tuple[str, ...]
    entidad: str                      # «yo» es la entidad del propio usuario
    tipo_entidad: str | None
    atributo: str
    valor: str
    atributo_nuevo: dict | None = None


MAPA = (
    # «Tengo alergia al ácido acetilsalicílico» -> yo, alergia. Con R6 (H3) una alergia es memoria.
    Regla("alergia", ("acetilsalicilico",), "yo", None, "alergia", "ácido acetilsalicílico"),
    # El texto original habla de «Sebastian» por error de sujeto (lo dijo Josem de sí mismo): se corrige a primera persona.
    Regla("camisetas", ("camisetas", "uv"), "yo", None, "nota", "Uso camisetas UV para bañarme"),
    # Atributo nuevo y activo. El duplicado (la presión aparece dos veces en Sprint 3) se descarta.
    Regla("presion", ("presion", "ruedas"), "coche", "vehiculo", "presion_neumaticos", "2,30 bar",
          atributo_nuevo={"descripcion": "Presión de inflado de los neumáticos de un vehículo", "tipo_valor": "numero",
                          "tipos_entidad": "vehiculo", "cardinalidad": "uno"}),
)


def _leer_textos(qdrant, base: str) -> list[str]:
    """Todos los `content` de la colección base, página a página. Solo `scroll`."""
    textos, offset = [], None
    while True:
        puntos, offset = qdrant.scroll(collection_name=base, limit=100, offset=offset, with_payload=True,
                                       with_vectors=False)
        textos += [p.payload.get("content") or "" for p in puntos]
        if offset is None:
            return textos


def _casa(regla: Regla, texto: str) -> bool:
    return set(regla.contiene) <= set(normalizar(texto).split())


def _entidad_id(repo: RepositorioMemoria, user_id: str, regla: Regla, *, crear: bool) -> int | None:
    if regla.entidad == "yo":
        return repo.entidad_usuario(user_id) if crear else (repo.entidades_por_alias(user_id, "yo") or [{}])[0].get("id")
    existentes = repo.entidades_por_alias(user_id, regla.entidad)
    if existentes:
        return existentes[0]["id"]
    if not crear:
        return None
    return repo.crear_entidad(user_id, regla.entidad, regla.tipo_entidad or "otro", estado="activo", origen="migracion")


def _atributo_id(repo: RepositorioMemoria, regla: Regla, *, crear: bool) -> int | None:
    existentes = repo.atributos_por_alias(regla.atributo)
    if existentes:
        return existentes[0]["id"]
    if not crear or not regla.atributo_nuevo:
        return None
    a = regla.atributo_nuevo
    return repo.crear_atributo(regla.atributo, a["descripcion"], tipo_valor=a["tipo_valor"],
                               tipos_entidad=a["tipos_entidad"], cardinalidad=a["cardinalidad"], estado="activo",
                               fuente="semilla")


def _ya_migrado(repo: RepositorioMemoria, user_id: str, entidad_id, atributo_id) -> bool:
    if entidad_id is None or atributo_id is None:
        return False
    filas = repo.hechos_con_nombres(user_id, entidad_id, atributo_id, solo_vigentes=False)
    return any(f["origen"] == "migracion" for f in filas)


def migrar(db, qdrant, base: str, user_id: str, *, dry_run: bool = False) -> dict:
    """Aplica `MAPA` a la colección `base`. Devuelve {escritos, ya_estaban, descartados, sin_mapa, dry_run}."""
    repo = RepositorioMemoria(db)
    elegidas: dict[str, tuple[Regla, str]] = {}
    sin_mapa, descartados = [], 0
    for texto in _leer_textos(qdrant, base):
        regla = next((r for r in MAPA if _casa(r, texto)), None)
        if regla is None:
            sin_mapa.append(texto)
        elif regla.nombre in elegidas:
            descartados += 1                                          # el duplicado
        else:
            elegidas[regla.nombre] = (regla, texto)

    escritos = ya_estaban = 0
    for regla, original in elegidas.values():
        entidad_id = _entidad_id(repo, user_id, regla, crear=False)
        atributo_id = _atributo_id(repo, regla, crear=False)
        if _ya_migrado(repo, user_id, entidad_id, atributo_id):
            ya_estaban += 1
            print(f"  ya estaba   {regla.entidad} · {regla.atributo}")
            continue
        escritos += 1
        print(f"  {'escribiría ' if dry_run else 'escribo    '} {regla.entidad} · {regla.atributo}: «{regla.valor}»"
              f"   (de: «{original}»)")
        if dry_run:
            continue
        entidad_id = _entidad_id(repo, user_id, regla, crear=True)
        atributo_id = _atributo_id(repo, regla, crear=True)
        hid = repo.anadir_hecho(user_id, entidad_id, atributo_id, regla.valor, origen="migracion")
        repo.registrar_decision(user_id, "anadir", {"regla": "migracion_sprint3", "mapa": regla.nombre},
                                f"hecho={hid} regla=migracion_sprint3", hecho_id=hid)
    for texto in sin_mapa:
        print(f"  sin mapa    «{texto}» (no se migra)")
    if descartados:
        print(f"  descartados {descartados} duplicado(s)")
    print(f"  {'DRY-RUN: no se ha escrito nada. ' if dry_run else ''}"
          f"escritos={escritos} ya_estaban={ya_estaban} descartados={descartados} sin_mapa={len(sin_mapa)}")
    return {"escritos": escritos, "ya_estaban": ya_estaban, "descartados": descartados, "sin_mapa": sin_mapa,
            "dry_run": dry_run}


def main(argv=None, *, base=None, nombre_bd=None, db=None, qdrant=None, user_id=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="enseña lo que haría sin escribir nada")
    parser.add_argument("--produccion", action="store_true",
                        help="permite una BD o una colección que no son de test ni de desarrollo")
    args = parser.parse_args(argv)

    config = None
    if base is None or nombre_bd is None or user_id is None:
        from utils.config import get_config
        config = get_config()
    base = base if base is not None else config["memory_collection"]
    nombre_bd = nombre_bd if nombre_bd is not None else config["mariadb"]["database"]

    # La negativa va ANTES de abrir ninguna conexión: con producción no se toca nada sin el flag.
    segura = nombre_bd in _BD_SEGURAS and base.endswith(_COLECCION_SEGURA)
    if not segura and not args.produccion:
        print(f"Rechazado: BD '{nombre_bd}' y colección '{base}' no son de test ni de desarrollo. Para producción, "
              "--produccion (lo ejecuta Josem, con SEBASTIAN_DB_NAME y SEBASTIAN_MEMORY_COLLECTION explícitos).",
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
    print(f"Migrando Sprint 3: BD={nombre_bd} colección={base} usuario={user_id}{' (dry-run)' if args.dry_run else ''}")
    migrar(db, qdrant, base, user_id, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
