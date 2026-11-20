"""Fase 4, H1j: el script de goldens de las consultas con historial (`scripts/memoria/golden_consultas.py`). Cliente falso: sin API."""
from types import SimpleNamespace as NS

from scripts.memoria import golden_consultas as g


def _uso(entrada=8000, salida=100):
    return NS(input_tokens=entrada, output_tokens=salida, cache_creation_input_tokens=0, cache_read_input_tokens=0)


class ClienteFalso:
    """Llama a la tool que dicte `por_mensaje[mensaje]` (o a ninguna); anota cada llamada."""

    def __init__(self, por_mensaje=None, coste=(8000, 100)):
        self.llamadas, self.por_mensaje, self.coste = [], por_mensaje or {}, coste
        self.messages = self

    def create(self, **kw):
        self.llamadas.append(kw)
        mensaje = kw["messages"][-1]["content"]
        tool = self.por_mensaje.get(mensaje)
        contenido = [NS(type="tool_use", name=tool, input={"query": "x"})] if tool else [NS(type="text", text="Su id es…")]
        return NS(content=contenido, stop_reason="tool_use" if tool else "end_turn", usage=_uso(*self.coste))


def _perfecto():
    return {m: ("search_memory" if esperada == "search_memory" else "mark_as_memorable" if esperada else "weather_get")
            for _, m, _, _, esperada, _, _ in g.ESCENARIOS}


def test_son_8_llamadas_con_el_planner_real_y_los_historiales_inventados():
    cliente = ClienteFalso(_perfecto())
    salida = g.correr(cliente)
    assert len(cliente.llamadas) == 8 and [f["escenario"] for f in salida["filas"]] == ["G1", "G1", "G2", "G2", "G3", "G3", "G4", "G5"]
    primera = cliente.llamadas[0]
    assert primera["model"] == g._MODELO_PLANNER and primera["max_tokens"] == g._PLANNER_MAX_TOKENS
    assert primera["tools"] is g._PLANNER_TOOLS and g.INDICE_YO in primera["system"]
    assert len(primera["messages"]) == 13 and primera["messages"][-1] == {"role": "user", "content": "¿Qué datos tienes de mí en Telegram?"}
    assert "Su telegram_id es 700111222" in primera["messages"][7]["content"]                       # el historial ya trae el valor
    paco = cliente.llamadas[4]
    assert g.INDICE_YO_Y_PACO in paco["system"] and "Paco es alérgico" in paco["messages"][3]["content"]
    assert "mark_as_memorable" in primera["system"] and "search_memory" in primera["system"]
    assert "`search_memory`, aunque el historial" in primera["system"]                               # la frase de R25 va en el prompt


def test_el_criterio_es_6_de_6_y_2_de_2():
    salida = g.correr(ClienteFalso(_perfecto()))
    r = g.resumen(salida)
    assert r == {"consultas": (6, 6), "controles": (2, 2), "aprobado": True}
    assert "APROBADO" in g.detalle(salida) and "NO APROBADO" not in g.detalle(salida)


def test_una_consulta_contestada_en_texto_falla_y_no_se_aprueba():
    por_mensaje = _perfecto()
    por_mensaje["¿Cuál es mi id de Telegram?"] = None                                  # el planner contesta en texto, como en producción
    salida = g.correr(ClienteFalso(por_mensaje))
    assert g.resumen(salida) == {"consultas": (4, 6), "controles": (2, 2), "aprobado": False}
    texto = g.detalle(salida)
    assert "FALLA" in texto and "ninguna tool" in texto and "NO APROBADO" in texto and "Su id es…" in texto


def test_los_controles_fallan_si_el_planner_hace_lo_contrario():
    por_mensaje = _perfecto()
    por_mensaje["¿Qué tiempo hace en Madrid?"] = "search_memory"                      # G5 no debe consultar la memoria
    por_mensaje["Recuerda que mi color favorito es el verde"] = "search_memory"       # G4 debe guardar
    r = g.resumen(g.correr(ClienteFalso(por_mensaje)))
    assert r["controles"] == (0, 2) and r["consultas"] == (6, 6) and r["aprobado"] is False


def test_se_para_antes_de_pasar_el_tope():
    cliente = ClienteFalso(_perfecto(), coste=(30000, 100))                           # 0,0305 $ por llamada
    salida = g.correr(cliente, tope=0.10)
    assert len(cliente.llamadas) == 3 and salida["gastado"] <= 0.10 and "tope" in salida["parada"]
    assert g.resumen(salida)["aprobado"] is False                                      # incompleto no es aprobado
