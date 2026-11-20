"""Fase 4, H1c: el script de diagnóstico de identificadores (`scripts/memoria/diagnostico_identificadores.py`).
Cliente falso: sin red ni API."""
from types import SimpleNamespace as NS

from scripts.memoria import diagnostico_identificadores as d


def _uso(entrada, salida, creacion=0, lectura=0):
    return NS(input_tokens=entrada, output_tokens=salida, cache_creation_input_tokens=creacion, cache_read_input_tokens=lectura)


class ClienteFalso:
    """El planner llama a `mark_as_memorable` con `texto_planner`; el extractor devuelve `hechos_por_texto[texto]` (o [])."""

    def __init__(self, texto_planner="Mi id de Telegram es 700111222 y mi usuario es @usuario_prueba", hechos_por_texto=None,
                 coste_planner=(8000, 100), coste_extractor=(1500, 150)):
        self.llamadas = []
        self.texto_planner = texto_planner
        self.hechos = hechos_por_texto or {}
        self.coste_planner, self.coste_extractor = coste_planner, coste_extractor
        self.messages = self

    def create(self, **kw):
        self.llamadas.append(kw)
        if kw["tools"] is d._PLANNER_TOOLS:
            contenido = [NS(type="tool_use", name="mark_as_memorable", input={"texto": self.texto_planner})]
            return NS(content=contenido, stop_reason="tool_use", usage=_uso(*self.coste_planner))
        texto = kw["messages"][0]["content"]
        contenido = [NS(type="tool_use", name="registrar_hechos", input={"hechos": self.hechos.get(texto, [])})]
        return NS(content=contenido, stop_reason="tool_use", usage=_uso(*self.coste_extractor))


def _hecho(**kw):
    return {"entidad": "yo", "tipo_entidad": "persona", "atributo": "telegram_id", "operacion": "afirmar", "valor": "700111222", **kw}


def test_el_planner_va_con_el_prompt_las_tools_el_modelo_y_el_techo_de_produccion():
    cliente = ClienteFalso()
    d.correr(cliente)
    primera = cliente.llamadas[0]
    assert primera["model"] == d._MODELO_PLANNER and primera["max_tokens"] == d._PLANNER_MAX_TOKENS
    assert primera["tools"] is d._PLANNER_TOOLS and primera["messages"] == [{"role": "user", "content": d.FRASE_PLANNER}]
    assert "mark_as_memorable" in primera["system"] and d.INDICE_PLANNER in primera["system"]
    assert not any(k in primera for k in ("temperature", "thinking"))        # _PLANNER_EXTRA está vacío con Haiku 4.5


def test_el_extractor_va_con_el_prompt_la_tool_y_el_catalogo_y_se_guarda_el_input_sin_validar():
    sin_marcador = {"entidad": "<UNKNOWN>", "atributo": "telegram_id", "operacion": "afirmar"}      # _validar lo descarta
    cliente = ClienteFalso(hechos_por_texto={"Mi id de Telegram es 700111222": [sin_marcador, _hecho()]})
    salida = d.correr(cliente)
    extractor = [x for x in cliente.llamadas if x["tools"] is not d._PLANNER_TOOLS]
    assert all(x["tool_choice"] == {"type": "tool", "name": "registrar_hechos"} for x in extractor)
    assert all(x["model"] == d.ext.MODELO_EXTRACTOR and "- yo (es el propio usuario)" in x["system"] for x in extractor)
    id_ = next(e for e in salida["extractor"] if e["caso"] == "id" and e["pasada"] == 1)
    assert id_["input"]["hechos"][0] == sin_marcador and len(id_["input"]["hechos"]) == 2          # tal como llega
    assert len(id_["validados"]) == 1 and id_["validados"][0]["atributo"] == "telegram_id"        # lo que deja pasar _validar


def test_el_primer_caso_es_el_texto_del_planner_tal_cual_y_hay_como_mucho_12_llamadas():
    cliente = ClienteFalso(texto_planner="El texto del planner")
    salida = d.correr(cliente, tope=1.0)
    assert salida["extractor"][0]["caso"] == "planner" and salida["extractor"][0]["texto"] == "El texto del planner"
    assert len(salida["planner"]) == 2 and len(salida["extractor"]) == 10 and len(cliente.llamadas) == 12
    primeros = [(e["caso"], e["pasada"]) for e in salida["extractor"]]
    assert primeros == [("planner", 1), ("id", 1), ("usuario", 1), ("matricula", 1), ("socio", 1), ("control", 1),
                        ("planner", 2), ("id", 2), ("usuario", 2), ("matricula", 2)]
    assert [t for _, t in d.CASOS] == ["Mi id de Telegram es 700111222", "Mi usuario de Telegram es @usuario_prueba",
                                       "La matrícula de mi coche es 1234 ABC", "Mi número de socio del gimnasio es 55821",
                                       "Mi color favorito es el verde"]


def test_el_gasto_cuenta_la_cache_y_se_para_antes_de_pasar_el_tope():
    # planner: 8000 de entrada + 100 de salida = 0,0085 $; extractor: 4000 + 300 = 0,0055 $ (12 llamadas = 0,072 $: no caben)
    cliente = ClienteFalso(coste_extractor=(4000, 300))
    salida = d.correr(cliente, tope=0.05)
    assert salida["gastado"] <= 0.05 and salida["parada"] is not None and len(cliente.llamadas) < 12
    assert abs(d.coste(NS(usage=_uso(1000, 200))) - 0.002) < 1e-9                          # 1000 × 1 $ + 200 × 5 $ por millón
    assert abs(d.coste(NS(usage=_uso(0, 0, creacion=1000, lectura=1000))) - (1.25e-3 + 0.1e-3)) < 1e-9
    caro = ClienteFalso(coste_planner=(30000, 100))                                        # 0,0305 $ cada una: la segunda no cabe
    salida = d.correr(caro, tope=0.05)
    assert len(salida["planner"]) == 1 and "planner" in salida["parada"]
    assert salida["gastado"] <= 0.05


def test_sin_texto_del_planner_el_extractor_solo_recibe_los_casos_fijos():
    cliente = ClienteFalso()
    cliente.texto_planner = ""
    salida = d.correr(cliente, tope=1.0)
    assert [e["caso"] for e in salida["extractor"] if e["pasada"] == 1] == ["id", "usuario", "matricula", "socio", "control"]


def test_el_detalle_enseña_entradas_salidas_y_gasto():
    cliente = ClienteFalso(hechos_por_texto={"Mi color favorito es el verde": [_hecho(atributo="preferencia", valor="verde")]})
    texto = d.detalle(d.correr(cliente, tope=1.0))
    assert "bloque.input" in texto and "mark_as_memorable" in texto and "Gasto total" in texto and "verde" in texto
