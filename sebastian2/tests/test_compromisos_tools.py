"""Fase 3, H1 (plan §2.2): la familia `compromisos`, sus descripciones y su despacho en el ejecutor. Sin API.

Las descripciones las escribe el programador, pero las líneas del plan §2.2 son normativas: aquí se comprueba que están.
"""
from datetime import date, datetime
from unittest.mock import patch

import pytest

from core.tool_executor import ToolExecutor
from core.tools import ALL_TOOLS, build_capabilities_digest
from db.connection import close_connection, get_connection
from modules.calendar import CalendarModule

USUARIO = "test_user_compromisos_tools"
NOMBRES = ["compromisos_crear", "compromisos_listar", "compromisos_completar", "compromisos_borrar"]


def _tool(nombre):
    return next(t for t in ALL_TOOLS if t["name"] == nombre)


def _desc(nombre):
    return " ".join(_tool(nombre)["description"].split())


# ── Definiciones ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_las_cuatro_tools_estan_registradas_y_en_el_digest():
    nombres = [t["name"] for t in ALL_TOOLS]
    for n in NOMBRES:
        assert nombres.count(n) == 1
    from core.tools.compromisos_tools import FAMILY_SUMMARY
    assert FAMILY_SUMMARY in build_capabilities_digest()


def test_crear_esquema():
    schema = _tool("compromisos_crear")["input_schema"]
    assert schema["required"] == ["items"]
    items = schema["properties"]["items"]
    assert items["type"] == "array" and items["minItems"] == 1 and items["maxItems"] == 20
    props = items["items"]["properties"]
    assert set(props) == {"texto", "evento_id", "fecha_inicio", "fecha_fin", "dias_inicio", "dias_fin", "hora", "minutos"}
    assert items["items"]["required"] == ["texto"]


def test_las_otras_tres_esquemas():
    assert _tool("compromisos_listar")["input_schema"]["required"] == []
    assert set(_tool("compromisos_listar")["input_schema"]["properties"]) == {"desde", "hasta", "evento_id"}
    assert _tool("compromisos_completar")["input_schema"]["required"] == ["id"]
    borrar = _tool("compromisos_borrar")["input_schema"]
    assert borrar["required"] == ["id", "motivo"]
    assert borrar["properties"]["motivo"]["enum"] == ["olvidar", "cancelar"]


def test_descripcion_de_crear_nombra_que_hacer_con_cada_cosa_que_no_es_suya():
    """Lección de R5: nombrar el destino correcto, no solo prohibir. Plan §2.2, normativo."""
    d = _desc("compromisos_crear")
    assert 'cosas que el usuario **tiene que hacer**'.replace("**", "") in d.replace("**", "")
    assert "evento_id" in d and "dias_inicio" in d and "minutos" in d
    assert "calendar_add_event" in d and "mark_as_memorable" in d and "`salud`" in d
    assert "request_clarification" in d and "si toma zinc" in d.lower()
    assert "no lo crees" in d.lower()


def test_descripcion_de_borrar_distingue_olvidar_de_cancelar():
    d = _desc("compromisos_borrar").lower()
    assert "olvidar" in d and "cancelar" in d and "borra" in d


def test_descripcion_de_borrar_manda_los_datos_a_mark_as_memorable():
    """H3b R6: sin esta frase, «Olvida lo de las camisetas UV» (golden #62) acababa en `search_memory`, porque
    «olvida ese compromiso» competía con el camino de borrado de la memoria. Aislado con A–E (informe, anexo)."""
    d = " ".join(_desc("compromisos_borrar").split())
    assert "tiene que hacer con un día u hora" in d
    assert "olvida lo de las camisetas UV" in d and "`mark_as_memorable`" in d


def test_calendar_add_note_admite_datos_de_cita_y_nunca_resultados():
    """D49 y D52 (plan §2.2): la nota del evento lleva lugar, planta, teléfono, código y acompañante."""
    d = _desc("calendar_add_note")
    assert "llevar dinero" in d                                   # lo de antes se conserva
    for dato in ("lugar", "planta", "teléfono", "código", "quién acompaña"):
        assert dato in d
    assert "Nunca" in d and "resultados" in d and "diagnósticos" in d


# ── Ejecutor ─────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def conn():
    c = get_connection()
    cur = c.cursor()
    cur.execute("DELETE FROM compromisos WHERE user_id = %s", (USUARIO,))
    cur.execute("DELETE FROM events WHERE user_id = %s", (USUARIO,))
    c.commit()
    yield c
    cur = c.cursor()
    cur.execute("DELETE FROM compromisos WHERE user_id = %s", (USUARIO,))
    cur.execute("DELETE FROM events WHERE user_id = %s", (USUARIO,))
    c.commit()
    close_connection()


def test_el_ejecutor_despacha_las_cuatro_con_la_bd_real(conn):
    cita = CalendarModule(conn, USUARIO).add_event("Endoscopia", date(2026, 12, 17), "09:30")["event_id"]
    ex = ToolExecutor(conn, USUARIO)
    creado = ex.execute("compromisos_crear", {"items": [
        {"texto": "2.ª toma", "evento_id": cita, "dias_inicio": 0, "hora": "01:00"},
        {"texto": "Llamar", "fecha_inicio": "2026-12-10"}]})
    assert creado["status"] == "created" and creado["compromisos"][0]["cuando"] == "2026-12-17T01:00"
    primero, segundo = (c["id"] for c in creado["compromisos"])

    listado = ex.execute("compromisos_listar", {"desde": "2026-12-01", "hasta": "2026-12-31"})
    assert [c["texto"] for c in listado["compromisos"]] == ["Llamar", "2.ª toma"]
    assert [c["id"] for c in ex.execute("compromisos_listar", {"desde": "2026-12-01", "hasta": "2026-12-31",
                                                                   "evento_id": cita})["compromisos"]] == [primero]

    assert ex.execute("compromisos_completar", {"id": primero})["status"] == "completed"
    assert ex.execute("compromisos_borrar", {"id": segundo, "motivo": "olvidar"})["status"] == "deleted"
    assert ex.execute("compromisos_listar", {"desde": "2026-12-01", "hasta": "2026-12-31"})["compromisos"] == []


def test_el_ejecutor_devuelve_el_error_de_forma_a_alfred(conn):
    r = ToolExecutor(conn, USUARIO).execute("compromisos_crear", {"items": [{"texto": "x"}]})
    assert r["status"] == "invalid" and "fecha_inicio" in r["message"]


def test_listar_sin_argumentos_usa_hoy_mas_catorce(conn):
    hoy = datetime.now().date().isoformat()
    ex = ToolExecutor(conn, USUARIO)
    ex.execute("compromisos_crear", {"items": [{"texto": "hoy", "fecha_inicio": hoy}]})
    assert [c["texto"] for c in ex.execute("compromisos_listar", {})["compromisos"]] == ["hoy"]


@patch("core.tool_executor.logger")
def test_el_texto_de_un_compromiso_no_va_a_los_logs_del_ejecutor(mock_logger, conn):
    """Lección de la fase 2 (R12) y D52: la preparación de una prueba médica no se vuelca en LogCentral."""
    ex = ToolExecutor(conn, USUARIO)
    secreto = "preparado-de-la-prueba-xyz"
    r = ex.execute("compromisos_crear", {"items": [{"texto": secreto, "fecha_inicio": "2026-12-10"}]})
    ex.execute("compromisos_listar", {"desde": "2026-12-01", "hasta": "2026-12-31"})
    volcado = " ".join(str(c) for c in mock_logger.mock_calls)
    assert secreto not in volcado
    assert r["status"] == "created"
