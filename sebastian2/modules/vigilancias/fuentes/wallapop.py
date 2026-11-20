# modules/vigilancias/fuentes/wallapop.py
"""Wallapop por su API JSON, por HTTP directo (D64, plan §2.3). Sin MCP ni navegador.

Una petición por consulta y ronda, sin paginar, y SIN coordenadas (así devuelve anuncios de toda España). No oficial y sin
clave: si Wallapop la cambia o la corta, `buscar` lanza `FuenteError` con el código y la ronda sigue con lo demás. La consulta
no va al log (D42), ni el cuerpo de la respuesta a ningún mensaje de error.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from modules.vigilancias.anuncio import Anuncio, FuenteError

URL_API = "https://api.wallapop.com/api/v3/search"
URL_ANUNCIO = "https://es.wallapop.com/item/{web_slug}"
CABECERAS = {"Accept": "application/json", "X-DeviceOS": "0"}
TIMEOUT = 15
_MADRID = ZoneInfo("Europe/Madrid")


def _booleano(valor, *claves) -> Optional[bool]:
    """`reserved` y `shipping` llegan como booleano o como un objeto con una bandera dentro; si no se sabe, `None`."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, dict):
        for clave in claves:
            if isinstance(valor.get(clave), bool):
                return valor[clave]
    return None


def _a_anuncio(item: dict) -> Anuncio:
    """Un item de la API a `Anuncio`. Lanza KeyError/TypeError/ValueError/InvalidOperation si le falta lo imprescindible."""
    precio = item.get("price") or {}
    cantidad = precio.get("amount")
    ciudad = (item.get("location") or {}).get("city")
    vendedor = item.get("user_id")
    return Anuncio(
        fuente="wallapop",
        id=str(item["id"]),
        titulo=str(item["title"]),
        descripcion=str(item.get("description") or ""),
        precio=Decimal(str(cantidad)) if cantidad is not None else None,
        moneda=str(precio.get("currency") or "EUR"),
        ciudad=str(ciudad) if ciudad else None,
        url=URL_ANUNCIO.format(web_slug=item["web_slug"]),
        # `modified_at` son milisegundos epoch; la hora local de Madrid, sin zona, como `events`.
        modificado=datetime.fromtimestamp(int(item["modified_at"]) / 1000, _MADRID).replace(tzinfo=None),
        reservado=bool(_booleano(item.get("reserved"), "flag")),
        envio=_booleano(item.get("shipping"), "item_is_shippable", "user_allows_shipping"),
        vendedor=str(vendedor) if vendedor is not None else None,
    )


class Wallapop:
    nombre = "wallapop"

    def __init__(self, get=None):
        self._get = get or requests.get          # inyectable: las pruebas no tocan la red

    def buscar(self, consulta: str) -> list[Anuncio]:
        params = {"keywords": consulta, "source": "search_box", "order_by": "newest"}
        try:
            respuesta = self._get(URL_API, params=params, headers=CABECERAS, timeout=TIMEOUT)
        except requests.RequestException as e:
            raise FuenteError(f"wallapop: {type(e).__name__}") from None       # la excepción de requests lleva la URL, con la consulta
        if respuesta.status_code >= 400:
            raise FuenteError(f"wallapop: HTTP {respuesta.status_code}")
        try:
            items = respuesta.json()["data"]["section"]["payload"]["items"]
        except (ValueError, KeyError, TypeError):
            raise FuenteError("wallapop: la respuesta no tiene data.section.payload.items") from None
        if not isinstance(items, list):
            raise FuenteError("wallapop: items no es una lista")

        anuncios = []
        for item in items:
            try:
                anuncios.append(_a_anuncio(item))
            except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError, OSError):
                continue                                                          # un item raro no tumba la consulta
        if items and not anuncios:
            raise FuenteError("wallapop: ningún item tiene la forma esperada")
        return anuncios
