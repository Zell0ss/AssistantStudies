"""Proyectos del vault, solo lectura (fase 2, D37).

Los proyectos con `proyecto.md` son entidades del propietario del vault, con nombre = carpeta (D13), y los
campos del contrato (`estado`, `host`, `stack`, `repo`, `db`) se leen en vivo: Sebastian no los copia ni los
escribe. Si chocan con un hecho de conversacion, gana el vault y la respuesta lo avisa.

Mismo confinamiento que `modules/consult_docs.py`: solo carpetas directas de `vault_docs_path` (que es la
carpeta `30-projects`), y se ignora todo lo que, resuelto con `realpath`, caiga fuera de ella (un symlink
que salga). Se lee solo el frontmatter, con `yaml.safe_load`.
"""
import os
import re

import yaml
from logcentral_client import get_logger

from core.memoria.normalizar import normalizar

logger = get_logger("sebastian")

# Los campos de `proyecto.md` que coinciden con atributos `contrato_vault` del catalogo (011).
CAMPOS_CONTRATO = ("estado", "host", "stack", "repo", "db")

_MAX_BYTES = 32 * 1024   # el frontmatter cabe de sobra; el cuerpo no se lee
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


def leer_proyectos(vault_docs_path: str | None) -> dict[str, dict[str, str]]:
    """{carpeta: {campo: valor}} con solo los campos del contrato que el `proyecto.md` declara.

    Nunca lanza: un vault ausente o un `proyecto.md` roto cuenta como «ese proyecto no esta»."""
    if not vault_docs_path:
        return {}
    base = os.path.realpath(vault_docs_path)
    try:
        carpetas = sorted(os.listdir(base))
    except OSError:
        return {}
    proyectos = {}
    for carpeta in carpetas:
        campos = _leer_proyecto(base, carpeta)
        if campos is not None:
            proyectos[carpeta] = campos
    return proyectos


def proyecto_por_nombre(proyectos: dict, nombre: str) -> tuple[str, dict] | None:
    """El proyecto cuya carpeta, normalizada como un alias, coincide con `nombre` («Proyecto Prueba»)."""
    buscado = normalizar(nombre or "")
    if not buscado:
        return None
    for carpeta, campos in proyectos.items():
        if normalizar(carpeta) == buscado:
            return carpeta, campos
    return None


def _leer_proyecto(base: str, carpeta: str) -> dict[str, str] | None:
    ruta = os.path.realpath(os.path.join(base, carpeta, "proyecto.md"))
    if not ruta.startswith(base + os.sep) or not os.path.isfile(ruta):
        if os.path.lexists(os.path.join(base, carpeta, "proyecto.md")) and not ruta.startswith(base + os.sep):
            logger.warning("memoria.vault: ruta fuera del vault ignorada")   # sin la ruta: puede ser ajena
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            texto = f.read(_MAX_BYTES)
        m = _FRONTMATTER.match(texto)
        datos = yaml.safe_load(m.group(1)) if m else None
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        logger.warning(f"memoria.vault: un proyecto.md no se pudo leer: {type(e).__name__}")
        return None
    if not isinstance(datos, dict):
        return None
    return {c: str(datos[c]) for c in CAMPOS_CONTRATO if datos.get(c) is not None}
