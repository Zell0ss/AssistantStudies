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


def test_alfred_no_cree_que_puede_consultar_la_memoria():
    """Hallado en la pasada de H3 (honestidad H1): con la linea de search_memory, sin datos de herramientas Alfred
    contestaba «Permítame consultarlo». Solo lee lo que ya trajo la herramienta; no ejecuta ninguna."""
    texto = _ALFRED_SYSTEM.lower()
    assert "tú no ejecutas herramientas" in texto
    assert "permítame consultarlo" in texto          # citado como lo que NO hay que decir


def test_la_descripcion_excluye_las_citas_con_fecha_aunque_diga_recuerda_que():
    """R5 (H3-encargo, D39): «recuerda que» choca con la exclusión del calendario. Una cita con fecha es calendario.
    Hallado por el golden #65, que el planner resolvía con mark_as_memorable."""
    d = _tool("mark_as_memorable")["description"].lower()
    parte_no = d[d.index("no la uses"):]
    assert "citas" in parte_no and "eventos con fecha" in parte_no
    assert "aunque" in parte_no and "recuerda que" in parte_no
    assert "calendar_add_event" in parte_no          # dice a dónde va, no solo adónde no (golden #65)
    assert "recuerda que" in d[:d.index("no la uses")]          # el «sí» de «recuerda que» sigue donde estaba


# --- R8 (D43) y R11 (H3-revision) -------------------------------------------------------------------------------

def test_el_planner_llama_a_la_tool_aunque_el_historial_parezca_que_ya_se_hizo():
    """D43: el historial lleva el texto del asistente («Anotado…», «Retirado…») y el planner lo imitaba sin
    llamar a la tool (E5, 5 de 6 pasadas)."""
    from core.orchestrator import _planner_system
    from core.tools import build_capabilities_digest
    indice = "Lo que me consta de ti (nombres, sin valores; usa search_memory para los valores):\n- Paco (persona): alergia"
    texto = _planner_system(indice)
    assert "guardar, corregir u olvidar" in texto and "`mark_as_memorable`" in texto
    assert "aunque el historial parezca que ya se hizo" in texto
    assert "el historial es lo que se dijo, no lo que se ha hecho en este turno" in texto
    # Acotada a datos de memoria: «Guárdame esta nota» y «apunta leche» tienen su propia tool.
    assert "dato de memoria" in texto
    # H3-revision R8, diagnóstico de la pasada de H3: con la regla en medio del prompt el planner contestaba en texto
    # «He retirado…» (0 de 6); al final, justo antes de decidir, y más fuerte, llama a la tool (3 de 3).
    assert "tu respuesta de este turno tiene que ser una llamada a `mark_as_memorable`" in texto
    assert "nunca contestes en texto que ya está hecho" in texto.lower()
    regla = texto.index("aunque el historial parezca que ya se hizo")
    assert regla > texto.index(build_capabilities_digest()) and regla > texto.index(indice)   # al final
    assert texto.count("aunque el historial parezca que ya se hizo") == 1                      # y una sola vez


def test_alfred_no_afirma_sin_resultado():
    """D43 y D26: sin resultado de herramienta este turno, Alfred no dice que guardó, corrigió u olvidó nada."""
    texto = " ".join(_ALFRED_SYSTEM.lower().split())          # sin saltos de línea dentro de las frases
    for verbo in ("guardado", "corregido", "olvidado", "apuntado", "creado"):
        assert verbo in texto, verbo
    assert "no hay un resultado de herramienta que lo diga" in texto
    assert "di que no lo has hecho" in texto


def test_alfred_dice_que_no_puede_cambiar_el_vault():
    """D37: el vault es de solo lectura. Hallado en E8: Alfred ofrecía «si desea corregirlo, dígamelo»."""
    texto = _ALFRED_SYSTEM.lower()
    assert "no puedes cambiar el vault" in texto
    assert "hay que corregirlo en `proyecto.md`" in texto
