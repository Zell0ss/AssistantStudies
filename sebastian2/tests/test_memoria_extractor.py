"""H2 (fase 2, D32): el extractor llama a Haiku 4.5 con una tool forzada. Cliente falso: sin API."""
from datetime import date
from types import SimpleNamespace

import pytest

from core.memoria.extractor import (
    MAX_HECHOS, MODELO_EXTRACTOR, TOOL_REGISTRAR_HECHOS, Extractor,
)


class ClienteFalso:
    def __init__(self, hechos=None, bloques=None):
        self.llamadas = []
        self._bloques = bloques if bloques is not None else [
            SimpleNamespace(type="tool_use", name="registrar_hechos", input={"hechos": hechos or []})]
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.llamadas.append(kwargs)
        return SimpleNamespace(content=self._bloques,
                               usage=SimpleNamespace(input_tokens=11, output_tokens=7))


def _hecho(**kw):
    base = {"entidad": "Paco", "tipo_entidad": "persona", "atributo": "alergia", "tipo_valor": "texto",
            "cardinalidad": "varios", "valor": "frutos secos", "operacion": "afirmar",
            "descripcion_atributo": "Sustancia que da alergia"}
    return {**base, **kw}


def test_llamada_forzada_a_registrar_hechos_con_haiku_45():
    cliente = ClienteFalso([_hecho()])
    Extractor(cliente).extraer("Mi cuñado Paco es alérgico a los frutos secos", "CATALOGO-X", date(2026, 10, 16))

    llamada = cliente.llamadas[0]
    assert llamada["model"] == MODELO_EXTRACTOR == "claude-haiku-4-5-20251001"
    assert llamada["tool_choice"] == {"type": "tool", "name": "registrar_hechos"}
    assert llamada["tools"] == [TOOL_REGISTRAR_HECHOS]
    assert "temperature" not in llamada   # anthropic 1.14 ya no acepta `temperature` en messages.create
    assert llamada["messages"] == [{"role": "user", "content": "Mi cuñado Paco es alérgico a los frutos secos"}]


def test_el_prompt_lleva_catalogo_y_fecha_de_hoy():
    cliente = ClienteFalso([])
    Extractor(cliente).extraer("hola", "CATALOGO-X: alergia, parentesco", date(2026, 10, 16))
    system = cliente.llamadas[0]["system"]
    assert "CATALOGO-X: alergia, parentesco" in system
    assert "2026-10-16" in system
    assert "{catalogo}" not in system and "{hoy}" not in system


def test_el_prompt_pide_usar_nombres_existentes_y_no_inventar():
    cliente = ClienteFalso([])
    Extractor(cliente).extraer("x", "c", date(2026, 10, 16))
    system = cliente.llamadas[0]["system"].lower()
    assert "nombre que ya existe" in system or "nombre existente" in system
    assert "no inventes" in system
    assert "iso" in system


def test_esquema_de_la_tool():
    props = TOOL_REGISTRAR_HECHOS["input_schema"]["properties"]["hechos"]
    assert props["maxItems"] == MAX_HECHOS == 8
    campos = props["items"]["properties"]
    # H2-revision R4: sin `ejemplos` (con la representacion (a) no se usa y cuesta tokens)
    assert set(campos) == {"entidad", "tipo_entidad", "atributo", "tipo_valor", "cardinalidad", "valor",
                           "operacion", "descripcion_atributo"}
    assert campos["operacion"]["enum"] == ["afirmar", "corregir", "retirar"]
    obligatorios = set(props["items"]["required"])
    assert {"entidad", "atributo", "operacion"} <= obligatorios


def test_devuelve_hechos_validados_con_valores_por_defecto():
    cliente = ClienteFalso([{"entidad": "yo", "atributo": "cumpleanos", "valor": "--03-12",
                             "operacion": "afirmar"}])
    [h] = Extractor(cliente).extraer("x", "c", date(2026, 10, 16))
    assert h["tipo_entidad"] == "otro" and h["cardinalidad"] == "uno" and h["tipo_valor"] == "texto"
    assert "ejemplos" not in h and h["descripcion_atributo"] == ""


def test_descarta_los_malformados_y_recorta_a_8():
    malos = [{"entidad": "x"}, {"atributo": "a", "operacion": "afirmar"},
             _hecho(operacion="inventada"), "no soy un dict", _hecho(entidad="  ")]
    cliente = ClienteFalso([_hecho(entidad=f"E{i}") for i in range(12)] + malos)
    hechos = Extractor(cliente).extraer("x", "c", date(2026, 10, 16))
    assert len(hechos) == 8 and all(h["entidad"].startswith("E") for h in hechos)


def test_tipo_de_entidad_desconocido_pasa_a_otro():
    cliente = ClienteFalso([_hecho(tipo_entidad="extraterrestre")])
    [h] = Extractor(cliente).extraer("x", "c", date(2026, 10, 16))
    assert h["tipo_entidad"] == "otro"


def test_el_prompt_pide_atributo_especifico_para_estados_y_decisiones():
    """H2-revision R4: una decision que puede cambiar no va a `nota`: una correccion no la sustituiria."""
    cliente = ClienteFalso([])
    Extractor(cliente).extraer("x", "c", date(2026, 10, 16))
    system = cliente.llamadas[0]["system"].lower()
    assert "estados y decisiones" in system and "cardinalidad `uno`" in system
    assert "`nota` solo para" in system


def test_sin_tool_use_devuelve_vacio():
    cliente = ClienteFalso(bloques=[SimpleNamespace(type="text", text="no")])
    assert Extractor(cliente).extraer("x", "c", date(2026, 10, 16)) == []


def test_informa_del_uso():
    usos = []
    Extractor(ClienteFalso([]), on_usage=lambda r, m: usos.append((r.usage.input_tokens, m))).extraer(
        "x", "c", date(2026, 10, 16))
    assert usos == [(11, "claude-haiku-4-5-20251001")]


def test_un_fallo_de_la_api_se_propaga():
    class Roto:
        messages = SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("api caida")))
    with pytest.raises(RuntimeError):
        Extractor(Roto()).extraer("x", "c", date(2026, 10, 16))
