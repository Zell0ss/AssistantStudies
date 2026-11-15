"""H2 (fase 2, plan §2.2 y §3 H2.4): el contrato de mark_as_memorable que ve el planner y Alfred."""
from core.orchestrator import _ALFRED_SYSTEM
from core.tools import ALL_TOOLS, build_capabilities_digest
from core.tools.memory_tools import FAMILY_SUMMARY, MEMORY_TOOLS


def _tool(nombre):
    return next(t for t in MEMORY_TOOLS if t["name"] == nombre)


def test_mark_as_memorable_tiene_el_contrato_nuevo():
    schema = _tool("mark_as_memorable")["input_schema"]
    assert set(schema["properties"]) == {"texto"}      # sustituye a `content` y `tags`
    assert schema["required"] == ["texto"]
    assert any(t["name"] == "mark_as_memorable" for t in ALL_TOOLS)


def test_descripcion_dice_cuando_si_y_cuando_no():
    d = _tool("mark_as_memorable")["description"].lower()
    for si in ("recuerda que", "decisiones", "corrige", "olvida"):
        assert si in d, si
    # la frontera: lo operativo con tool propia y la salud no son memoria
    for no in ("notas", "listas", "calendario", "tareas", "salud"):
        assert no in d, no


def test_el_resumen_no_promete_recordatorios():
    assert FAMILY_SUMMARY in build_capabilities_digest()   # lo que dice la familia llega a los prompts
    texto = FAMILY_SUMMARY.lower()
    for prohibido in ("recordatorio", "te aviso", "avisarte", "recordarte"):
        assert prohibido not in texto, prohibido
    assert "corregir" in FAMILY_SUMMARY.lower() and "retirar" in FAMILY_SUMMARY.lower()


def test_alfred_tiene_la_linea_de_d16():
    texto = _ALFRED_SYSTEM
    assert "nuevos_pendientes" in texto           # lo dice en una frase si abrió categorías
    assert "sustituye" in texto                   # y cuenta lo que sustituyó
    assert "nota" in texto.lower()                # y no afirma una corrección que quedó como nota


def test_alfred_no_ofrece_renombrar_lo_que_no_se_puede():
    """H2-revision §2.2: confirmar o renombrar pendientes es de la fase 3; Alfred solo informa."""
    assert "otro nombre" not in _ALFRED_SYSTEM.lower()
    assert "he abierto la categoría" in _ALFRED_SYSTEM.lower()


# --- search_memory (H3, plan §2.3) ---------------------------------------------------------------

def test_search_memory_tiene_el_contrato_nuevo():
    schema = _tool("search_memory")["input_schema"]
    assert set(schema["properties"]) == {"query", "entidad", "atributo", "historial"}   # sin `k`
    assert schema["required"] == ["query"]
    assert schema["properties"]["historial"]["type"] == "boolean"


def test_search_memory_dice_cuando_usarla_y_que_es_el_indice():
    d = _tool("search_memory")["description"].lower()
    for frase in ("¿qué te dije", "historial", "índice", "alias"):
        assert frase in d, frase


def test_alfred_sabe_leer_la_salida_de_search_memory():
    texto = _ALFRED_SYSTEM
    for clave in ("search_memory", "conflictos", "vault", "historial", "notas"):
        assert clave in texto, clave
    assert "gana el vault" in texto.lower()          # D37: si chocan, el vault y se avisa
    assert "no me consta" in texto.lower()           # D26: todo vacio = no le consta
