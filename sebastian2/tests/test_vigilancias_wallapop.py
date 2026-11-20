"""Fase 4, H1 (D64; plan §2.3 y §3, pruebas 1-4): la fuente Wallapop con JSON grabado a mano. Sin red: `get` es un falso."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import requests

from modules.vigilancias.anuncio import FuenteError
from modules.vigilancias.fuentes import FUENTES
from modules.vigilancias.fuentes.wallapop import URL_API, Wallapop


def _ms(*args) -> int:
    return int(datetime(*args, tzinfo=timezone.utc).timestamp() * 1000)


def _item(id, titulo, slug, **extra):
    return {"id": id, "title": titulo, "description": f"Descripción de {titulo}", "price": {"amount": 900.0, "currency": "EUR"},
            "location": {"city": "Valencia"}, "web_slug": slug, "modified_at": _ms(2026, 11, 20, 7, 0),
            "reserved": {"flag": False}, "shipping": {"item_is_shippable": True}, "user_id": "u-77", **extra}


JSON_3 = {"data": {"section": {"payload": {"items": [
    _item("w1", "Mac mini M4 24 GB", "mac-mini-m4-24-gb-w1"),
    _item("w2", "Mac mini M2 Pro", "mac-mini-m2-pro-w2", price={"amount": 749.5, "currency": "EUR"}, reserved=True),
    _item("w3", "Soporte para mac mini", "soporte-w3", shipping=False, location={}),
]}}}}


class Resp:
    def __init__(self, status=200, datos=None, cuerpo="", fallo_json=False):
        self.status_code, self._datos, self.text, self._fallo_json = status, datos, cuerpo, fallo_json

    def json(self):
        if self._fallo_json:
            raise ValueError("no es JSON")
        return self._datos


class Get:
    def __init__(self, respuesta):
        self.respuesta, self.llamadas = respuesta, []

    def __call__(self, url, **kwargs):
        self.llamadas.append((url, kwargs))
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


def test_1_tres_items_dan_tres_anuncios_con_los_campos_bien():
    anuncios = Wallapop(get=Get(Resp(datos=JSON_3))).buscar("mac mini")
    assert [a.id for a in anuncios] == ["w1", "w2", "w3"]
    a, b, c = anuncios
    assert (a.fuente, a.titulo, a.precio, a.moneda, a.ciudad) == ("wallapop", "Mac mini M4 24 GB", Decimal("900.0"), "EUR", "Valencia")
    assert a.url == "https://es.wallapop.com/item/mac-mini-m4-24-gb-w1"
    assert a.modificado == datetime(2026, 11, 20, 8, 0)               # 07:00 UTC es la hora local de Madrid (CET): 08:00, sin zona
    assert a.descripcion == "Descripción de Mac mini M4 24 GB" and a.vendedor == "u-77"
    assert (a.reservado, a.envio) == (False, True)
    assert b.precio == Decimal("749.5") and b.reservado is True
    assert c.ciudad is None and c.envio is False


def test_1b_la_hora_de_verano_tambien_es_la_local():
    json_verano = {"data": {"section": {"payload": {"items": [{**_item("w9", "Mac mini", "s"), "modified_at": _ms(2026, 7, 1, 10, 0)}]}}}}
    assert Wallapop(get=Get(Resp(datos=json_verano))).buscar("mac mini")[0].modificado == datetime(2026, 7, 1, 12, 0)   # CEST


def test_1c_un_item_sin_lo_imprescindible_se_salta_y_si_son_todos_falla():
    roto = {"id": "x", "title": "sin enlace ni fecha"}
    json_mixto = {"data": {"section": {"payload": {"items": [roto, _item("w1", "Mac mini", "s")]}}}}
    assert [a.id for a in Wallapop(get=Get(Resp(datos=json_mixto))).buscar("mac mini")] == ["w1"]
    json_roto = {"data": {"section": {"payload": {"items": [roto]}}}}
    with pytest.raises(FuenteError):
        Wallapop(get=Get(Resp(datos=json_roto))).buscar("mac mini")


def test_1d_una_lista_vacia_es_una_respuesta_valida():
    assert Wallapop(get=Get(Resp(datos={"data": {"section": {"payload": {"items": []}}}}))).buscar("mac mini") == []


def test_2_un_403_lanza_fuente_error_y_el_mensaje_no_lleva_el_cuerpo():
    cuerpo = "CUERPO-SECRETO-DE-LA-RESPUESTA"
    with pytest.raises(FuenteError) as e:
        Wallapop(get=Get(Resp(status=403, cuerpo=cuerpo))).buscar("mac mini")
    assert "403" in str(e.value) and cuerpo not in str(e.value)


def test_2b_un_fallo_de_red_lanza_fuente_error_sin_la_consulta():
    class ErrorConUrl(requests.ConnectionError):
        pass
    with pytest.raises(FuenteError) as e:
        Wallapop(get=Get(ErrorConUrl("fallo en https://api.wallapop.com/api/v3/search?keywords=ZZCONSULTA"))).buscar("ZZCONSULTA")
    assert "ErrorConUrl" in str(e.value) and "ZZCONSULTA" not in str(e.value)


@pytest.mark.parametrize("datos", [{}, {"data": {}}, {"data": {"section": {"payload": {}}}}, {"data": {"section": {"payload": {"items": "no"}}}}, [], None])
def test_3_un_json_sin_data_section_payload_items_lanza_fuente_error(datos):
    with pytest.raises(FuenteError):
        Wallapop(get=Get(Resp(datos=datos))).buscar("mac mini")


def test_3b_un_cuerpo_que_no_es_json_lanza_fuente_error():
    with pytest.raises(FuenteError):
        Wallapop(get=Get(Resp(fallo_json=True))).buscar("mac mini")


def test_4_la_peticion_va_sin_coordenadas_con_order_by_newest_y_la_consulta_en_keywords():
    get = Get(Resp(datos=JSON_3))
    Wallapop(get=get).buscar("mac mini m4")
    (url, kwargs), = get.llamadas
    assert url == URL_API == "https://api.wallapop.com/api/v3/search"
    params = kwargs["params"]
    assert params["keywords"] == "mac mini m4" and params["order_by"] == "newest" and params["source"] == "search_box"
    assert "latitude" not in params and "longitude" not in params
    assert kwargs["headers"] == {"Accept": "application/json", "X-DeviceOS": "0"}
    assert kwargs["timeout"] == 15


def test_la_fuente_esta_registrada_en_fuentes():
    assert isinstance(FUENTES["wallapop"], Wallapop) and FUENTES["wallapop"].nombre == "wallapop"
