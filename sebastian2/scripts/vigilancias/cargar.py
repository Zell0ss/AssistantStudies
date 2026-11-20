"""Carga de vigilancias desde un YAML (fase 4, H1, plan §2.7). Uso (desde sebastian2/):

    python -m scripts.vigilancias.cargar <fichero.yaml> --user <id>

Hace upsert por `(user_id, nombre)` y escribe en la BD que diga el entorno: con el `.env`, en desarrollo; en producción, con
`SEBASTIAN_DB_NAME=sebastian_db` (lo hace Josem en el despliegue). Valida igual que el módulo (`repositorio.validar`: límites
del plan §2.1) y es atómico: si una vigilancia del fichero no vale, no se escribe ninguna.

El YAML es un mapa (una vigilancia) o una lista de mapas, con `nombre`, `fuente`, `consultas`, `filtros`
(`precio_min`, `precio_max`, `excluir`), `reglas`, `hora` («HH:MM») y, opcional, `activa` (por defecto, verdadero).
Las vigilancias reales de Josem NO van al repo: viven en el vault.
"""
import argparse
import sys
from pathlib import Path

import yaml

from db.connection import close_connection, get_connection
from modules.vigilancias import repositorio


def cargar(ruta: Path, user_id: str, conn) -> list:
    """Valida y guarda todas las vigilancias del fichero en una sola transacción. Devuelve [{id, creada, nombre}]."""
    contenido = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    entradas = contenido if isinstance(contenido, list) else [contenido]
    for entrada in entradas:
        repositorio.validar(entrada)                     # todo se valida antes de escribir nada
    resultados = []
    try:
        for entrada in entradas:
            resultados.append(repositorio.guardar(conn, user_id, entrada, confirmar=False))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return resultados


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Carga vigilancias desde un YAML (upsert por usuario y nombre).")
    parser.add_argument("fichero", type=Path)
    parser.add_argument("--user", required=True, help="id de Telegram del dueño de las vigilancias")
    args = parser.parse_args(argv)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DATABASE() AS db")
        print(f"Escribiendo en BD: {cur.fetchone()['db']}")
        cur.close()
        try:
            resultados = cargar(args.fichero, args.user, conn)
        except (repositorio.VigilanciaInvalida, OSError, yaml.YAMLError) as e:
            print(f"FALLO: {type(e).__name__}: {e}. No se ha escrito nada.", file=sys.stderr)
            return 1
        for r in resultados:
            print(f"  {'creada ' if r['creada'] else 'actualizada'} id={r['id']} «{r['nombre']}»")
        return 0
    finally:
        close_connection()


if __name__ == "__main__":
    sys.exit(main())
