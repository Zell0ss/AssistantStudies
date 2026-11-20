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
    assert "nunca contestes un dato de memoria copiándolo del historial" in primera["system"]       # la frase de R25b va en el prompt


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


def _perfecta_2(excepto=None):
    por_mensaje = {m: "search_memory" for m in ("¿Cuál es mi id de Telegram?", "¿Cuándo es mi cumpleaños?",
                                                  "¿Qué datos tienes de mí en Telegram?", "¿Qué sabes de Paco?")}
    por_mensaje["Recuerda que mi color favorito es el verde"] = "mark_as_memorable"
    por_mensaje.update(excepto or {})
    return por_mensaje


def test_segunda_vuelta_son_6_llamadas_con_g2b_nuevo_y_su_historial():
    cliente = ClienteFalso(_perfecta_2())
    salida = g.correr(cliente, tope=0.10, vuelta=2)
    assert [f["escenario"] for f in salida["filas"]] == ["G2", "G2", "G2b", "G1", "G3", "G4"] and len(cliente.llamadas) == 6
    g2b = cliente.llamadas[2]
    assert g2b["messages"][-1] == {"role": "user", "content": "¿Cuándo es mi cumpleaños?"}
    assert "- yo (tú): cumpleanos, telegram_id, nota" in g2b["system"]
    assert len(g2b["messages"]) == 13 and g2b["messages"][7]["content"] == "Su cumpleaños es el 12 de marzo, señor."   # misma pregunta ya contestada
    r = g.resumen_segunda_vuelta(salida)
    assert r == {"g2_g2b": (3, 3), "sin_regresion": (3, 3), "aprobado": True}
    assert "vuelta 2" in g.detalle(salida, 2) and "G2 y G2b: 3/3" in g.detalle(salida, 2) and "NO APROBADO" not in g.detalle(salida, 2)


def test_segunda_vuelta_no_se_aprueba_si_g2b_falla_o_hay_regresion():
    sin_g2b = g.correr(ClienteFalso(_perfecta_2({"¿Cuándo es mi cumpleaños?": None})), vuelta=2)
    assert g.resumen_segunda_vuelta(sin_g2b) == {"g2_g2b": (2, 3), "sin_regresion": (3, 3), "aprobado": False}
    regresion = g.correr(ClienteFalso(_perfecta_2({"¿Qué sabes de Paco?": None})), vuelta=2)
    assert g.resumen_segunda_vuelta(regresion) == {"g2_g2b": (3, 3), "sin_regresion": (2, 3), "aprobado": False}
    assert "NO APROBADO" in g.detalle(regresion, 2)


def test_segunda_vuelta_se_para_antes_del_tope_y_no_se_aprueba():
    cliente = ClienteFalso(_perfecta_2(), coste=(30000, 100))
    salida = g.correr(cliente, tope=0.06, vuelta=2)
    assert len(cliente.llamadas) == 1 and "tope" in salida["parada"] and g.resumen_segunda_vuelta(salida)["aprobado"] is False


def test_tercera_vuelta_son_5_llamadas_y_la_posicion_nueva_se_queda_si_g2_mejora_sin_regresion():
    cliente = ClienteFalso(_perfecta_2())
    salida = g.correr(cliente, tope=0.10, vuelta=3)
    assert [f["escenario"] for f in salida["filas"]] == ["G2", "G2", "G2b", "G1", "G3"] and len(cliente.llamadas) == 5
    assert g.resumen_tercera_vuelta(salida) == {"g2": (2, 2), "otras": (3, 3), "se_queda_la_posicion_nueva": True}
    assert "SE QUEDA LA POSICIÓN NUEVA" in g.detalle(salida, 3)
    una = g.correr(ClienteFalso(_perfecta_2()), vuelta=3)
    una["filas"][0]["acierta"] = False                                                     # mejora solo 1 de 2: sigue siendo mejora
    assert g.resumen_tercera_vuelta(una)["se_queda_la_posicion_nueva"] is True


def test_tercera_vuelta_vuelve_atras_si_g2_no_mejora_o_algo_empeora():
    sin_mejora = g.correr(ClienteFalso(_perfecta_2({"¿Cuál es mi id de Telegram?": None})), vuelta=3)
    assert g.resumen_tercera_vuelta(sin_mejora) == {"g2": (0, 2), "otras": (3, 3), "se_queda_la_posicion_nueva": False}
    assert "VUELVE A LA POSICIÓN ANTERIOR" in g.detalle(sin_mejora, 3)
    empeora = g.correr(ClienteFalso(_perfecta_2({"¿Qué sabes de Paco?": None})), vuelta=3)
    assert g.resumen_tercera_vuelta(empeora)["se_queda_la_posicion_nueva"] is False        # G2 mejora, pero G3 empeora
    parcial = g.correr(ClienteFalso(_perfecta_2(), coste=(30000, 100)), tope=0.05, vuelta=3)
    assert g.resumen_tercera_vuelta(parcial)["se_queda_la_posicion_nueva"] is False        # incompleto no cuenta


def test_se_para_antes_de_pasar_el_tope():
    cliente = ClienteFalso(_perfecto(), coste=(30000, 100))                           # 0,0305 $ por llamada
    salida = g.correr(cliente, tope=0.10)
    assert len(cliente.llamadas) == 3 and salida["gastado"] <= 0.10 and "tope" in salida["parada"]
    assert g.resumen(salida)["aprobado"] is False                                      # incompleto no es aprobado
