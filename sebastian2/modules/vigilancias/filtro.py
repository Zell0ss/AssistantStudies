# modules/vigilancias/filtro.py
"""Filtro simple y novedad de una vigilancia (D65, plan §2.4). Funciones puras: las aplica el código, no cuestan nada.

Orden: duplicados → novedad → filtro. Un anuncio «nuevo» se guarda como visto aunque el filtro o el juez lo descarten, para
que no vuelva; solo los que pasan el filtro llegan al juez.
"""
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from modules.vigilancias.anuncio import Anuncio

VENTANA_NOVEDAD = timedelta(hours=48)
_CAPACIDAD = re.compile(r"(\d+)\s*(gb|tb)")
_NO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


def normalizar(texto: str) -> list[str]:
    """Minúsculas y sin acentos (NFD), «8 GB» → «8gb», troceado por lo que no es letra ni número."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")
    return [p for p in _NO_ALFANUMERICO.split(_CAPACIDAD.sub(r"\1\2", sin_acentos)) if p]


def firma(anuncio: Anuncio) -> str:
    """sha1 de título + descripción normalizados: cambia si el vendedor cambia el texto, no si solo «sube» el anuncio."""
    base = " ".join(normalizar(anuncio.titulo)) + " | " + " ".join(normalizar(anuncio.descripcion))
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def precio_2(precio: Optional[Decimal]) -> Optional[Decimal]:
    """El precio como lo guarda la BD (DECIMAL(10,2)), para poder compararlo con lo visto."""
    return None if precio is None else precio.quantize(Decimal("0.01"))


def _contiene(palabras: list[str], termino: list[str]) -> bool:
    n = len(termino)
    return any(palabras[i:i + n] == termino for i in range(len(palabras) - n + 1))


def pasa_filtro(anuncio: Anuncio, filtros: dict) -> bool:
    """No reservado, con precio dentro de [precio_min, precio_max] (un extremo nulo no limita) y sin ningún término de
    `excluir` como secuencia contigua de palabras en título + descripción: «8gb» no casa con «128gb», ni «i7» con «i7x»."""
    if anuncio.reservado or anuncio.precio is None:
        return False
    minimo, maximo = filtros.get("precio_min"), filtros.get("precio_max")
    if minimo is not None and anuncio.precio < Decimal(str(minimo)):
        return False
    if maximo is not None and anuncio.precio > Decimal(str(maximo)):
        return False
    palabras = normalizar(anuncio.titulo) + normalizar(anuncio.descripcion)
    for termino in filtros.get("excluir") or []:
        buscado = normalizar(termino)
        if buscado and _contiene(palabras, buscado):
            return False
    return True


def es_nuevo(anuncio: Anuncio, visto: Optional[dict], ahora: datetime) -> bool:
    """Modificado en las últimas 48 h y, además, no visto, o visto con otro precio u otra firma. `visto` trae `precio` y `firma`."""
    if anuncio.modificado < ahora - VENTANA_NOVEDAD:
        return False
    if visto is None:
        return True
    return precio_2(visto["precio"]) != precio_2(anuncio.precio) or visto["firma"] != firma(anuncio)


@dataclass
class Seleccion:
    nuevos: list      # anuncios nuevos de la ronda (sin repetir el id): todos se guardan como vistos si la ronda sale
    candidatos: list  # los nuevos que pasan el filtro y no repiten firma: los que ve el juez, del más reciente al más antiguo


def seleccionar(anuncios: list, vistos: dict, filtros: dict, ahora: datetime) -> Seleccion:
    """Duplicados (mismo `id` de varias consultas), novedad frente a `vistos` ({anuncio_id: {precio, firma}}) y filtro.

    Dos `id` con la misma firma cuentan una vez como candidato; el segundo sigue siendo «nuevo» y se guarda como visto,
    para que mañana no vuelva a salir por no estar en `vistos`."""
    por_id = {}
    for a in anuncios:
        por_id.setdefault(a.id, a)
    nuevos = [a for a in por_id.values() if es_nuevo(a, vistos.get(a.id), ahora)]
    candidatos, firmas = [], set()
    for a in sorted(nuevos, key=lambda x: x.modificado, reverse=True):
        f = firma(a)
        if f in firmas or not pasa_filtro(a, filtros):
            continue
        firmas.add(f)
        candidatos.append(a)
    return Seleccion(nuevos=nuevos, candidatos=candidatos)
