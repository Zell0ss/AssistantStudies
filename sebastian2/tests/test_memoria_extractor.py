"""H2 (fase 2, D32): el extractor llama a Haiku 4.5 con una tool forzada. Cliente falso: sin API."""
from datetime import date
from types import SimpleNamespace

import pytest

from core.memoria.extractor import (
    MAX_HECHOS, MODELO_EXTRACTOR, TOOL_REGISTRAR_HECHOS, Extractor, _validar,
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


# --- R6 (H3-encargo): la regla 5 del prompt dice lo que el plan ya decidio -----------------------------------

def test_prompt_extractor_alergia_es_memoria():
    """`alergia` es un atributo semilla (plan §2.1) y E1 guarda la de Paco: el prompt no puede decir que «cualquier
    dato de salud» no es memoria. Lo de Tristras son los registros del día; la frontera completa es de la fase 3."""
    from pathlib import Path
    texto = (Path(__file__).parent.parent / "core" / "memoria" / "prompts" / "extractor_hechos.md").read_text(
        encoding="utf-8").lower()
    assert "alergias sí son memoria" in texto
    assert "cualquier dato de salud" not in texto
    for sigue_fuera in ("cómo ha dormido", "qué ha comido", "hambre", "síntomas", "tristras"):
        assert sigue_fuera in texto, sigue_fuera                  # lo del día a día sigue sin ser memoria


# --- R10 (H3-revision §2.5): una entidad marcador no es una entidad -------------------------------------------

@pytest.mark.parametrize("marcador", ["<UNKNOWN>", "<desconocido>", "<usuario>", "", "   "])
def test_validar_descarta_entidad_marcador(marcador):
    """Hallado en el A/B de H3: a veces el modelo devuelve la entidad literal `<UNKNOWN>` y el servicio habría
    creado una entidad con ese nombre."""
    assert _validar(_hecho(entidad=marcador)) is None


@pytest.mark.parametrize("nombre", ["Paco", "yo", "el coche", "Ana <3", "a<b>c", "<3"])
def test_validar_conserva_las_entidades_normales(nombre):
    assert _validar(_hecho(entidad=nombre))["entidad"] == nombre


def test_el_extractor_cuenta_los_marcadores_que_descarta():
    cliente = ClienteFalso([_hecho(entidad="<UNKNOWN>"), _hecho(entidad="Paco")])
    extractor = Extractor(cliente)
    hechos = extractor.extraer("x", "c", date(2026, 11, 15))
    assert [h["entidad"] for h in hechos] == ["Paco"] and extractor.marcadores_descartados == 1
    extractor.extraer("y", "c", date(2026, 11, 15))                    # se cuenta por llamada, no se acumula
    assert extractor.marcadores_descartados == 1
    extractor_sin = Extractor(ClienteFalso([_hecho()]))
    extractor_sin.extraer("z", "c", date(2026, 11, 15))
    assert extractor_sin.marcadores_descartados == 0


# --- H1c R10b (D42): el extractor dice qué devuelve, sin contenido -------------------------------------------------

def _log_del_extractor(hechos, stop_reason="tool_use", entrada=None):
    from unittest.mock import patch
    cliente = ClienteFalso(bloques=[SimpleNamespace(type="tool_use", name="registrar_hechos",
                                                    input=entrada if entrada is not None else {"hechos": hechos})])
    original = cliente._create
    cliente.messages = SimpleNamespace(create=lambda **kw: _con_stop(original(**kw), stop_reason))
    with patch("core.memoria.extractor.logger") as log:
        resultado = Extractor(cliente).extraer("x", "c", date(2026, 10, 16))
    lineas = [c.args[0] for c in log.info.call_args_list]
    return resultado, lineas, [str(c) for c in log.mock_calls]


def _con_stop(respuesta, stop_reason):
    respuesta.stop_reason = stop_reason
    return respuesta


def test_h1c_con_lista_vacia_el_log_dice_crudos_0_validados_0():
    resultado, lineas, _ = _log_del_extractor([])
    assert resultado == []
    assert lineas == ["Extractor: stop=tool_use crudos=0 validados=0"]


def test_h1c_un_hecho_bueno_y_uno_sin_atributo_dice_descartes_sin_atributo():
    resultado, lineas, _ = _log_del_extractor([_hecho(), _hecho(atributo="")])
    assert len(resultado) == 1
    assert lineas == ["Extractor: stop=tool_use crudos=2 validados=1 descartes=sin_atributo"]


def test_h1c_cada_motivo_de_descarte_tiene_su_etiqueta_fija():
    crudos = [_hecho(entidad="<UNKNOWN>"), _hecho(atributo="  "), _hecho(operacion="borrar"), _hecho(operacion=None), "texto", 7, _hecho()]
    resultado, lineas, _ = _log_del_extractor(crudos)
    assert len(resultado) == 1
    assert lineas == ["Extractor: stop=tool_use crudos=7 validados=1 "
                      "descartes=marcador,sin_atributo,operacion_invalida,operacion_invalida,no_es_dict,no_es_dict"]


def test_h1c_el_motivo_de_descarte_coincide_con_lo_que_decide_validar():
    from core.memoria.extractor import _motivo_de_descarte
    casos = [_hecho(), _hecho(entidad="<desconocido>"), _hecho(entidad=""), _hecho(atributo=None), _hecho(operacion="x"),
             _hecho(entidad="<3"), None, [], "x"]
    for crudo in casos:
        assert (_motivo_de_descarte(crudo) is None) == (_validar(crudo) is not None), crudo


def test_h1c_con_hechos_como_texto_no_hay_excepcion_y_el_log_dice_hechos_no_lista():
    resultado, lineas, _ = _log_del_extractor(None, entrada={"hechos": "no soy una lista"})
    assert resultado == []
    assert lineas == ["Extractor: stop=tool_use crudos=0 validados=0 descartes=hechos_no_lista"]


def test_h1c_sin_hechos_en_la_entrada_es_una_lista_vacia_sin_descartes():
    _, lineas, _ = _log_del_extractor(None, entrada={})
    assert lineas == ["Extractor: stop=tool_use crudos=0 validados=0"]


def test_h1c_el_log_lleva_el_stop_reason():
    _, lineas, _ = _log_del_extractor([], stop_reason="max_tokens")
    assert lineas == ["Extractor: stop=max_tokens crudos=0 validados=0"]


def test_h1c_una_marca_en_el_valor_y_en_el_texto_no_sale_en_ningun_log():
    from unittest.mock import patch
    marca = "ZZEXTR"
    cliente = ClienteFalso([_hecho(valor=f"valor {marca}", entidad=f"<{marca}>"), _hecho(atributo="", valor=marca),
                            _hecho(operacion=f"op-{marca}"), f"crudo-{marca}", _hecho(valor=marca)])
    with patch("core.memoria.extractor.logger") as log:
        Extractor(cliente).extraer(f"frase {marca}", f"catalogo {marca}", date(2026, 10, 16))
    llamadas = [str(c) for c in log.mock_calls]
    assert llamadas and not any(marca in l for l in llamadas)
