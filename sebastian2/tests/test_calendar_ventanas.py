"""Fase 3 H5 (H5-encargo R14–R16): las ventanas de tiempo de `calendar_list_events`. Sin API, con `hoy` fijado.

Producción, 2026-11-16: «¿Cómo se presenta el mes de diciembre?» se leyó como noviembre porque la tool no tenía forma de pedir
otro mes, y Alfred ofreció crear de nuevo una cita y sus pasos, que ya existían. `weekend` estaba en el esquema y caía en «hoy»."""
from datetime import date

import pytest

from core.tool_executor import ToolExecutor
from core.tools.calendar_tools import CALENDAR_TOOLS
from db.connection import close_connection, get_connection
from modules.calendar import CalendarModule

USUARIO = "test_user_ventanas"
LUNES = date(2026, 11, 16)
MIERCOLES = date(2026, 11, 18)
SABADO = date(2026, 11, 21)
DOMINGO = date(2026, 11, 22)


@pytest.fixture
def conn():
    c = get_connection()
    cur = c.cursor()
    cur.execute("DELETE FROM events WHERE user_id = %s", (USUARIO,))
    c.commit()
    yield c
    cur = c.cursor()
    cur.execute("DELETE FROM events WHERE user_id = %s", (USUARIO,))
    c.commit()
    close_connection()


@pytest.fixture
def cal(conn):
    return CalendarModule(conn, USUARIO)


def test_los_dias_de_la_semana_de_las_fechas_de_las_pruebas():
    assert (LUNES.weekday(), MIERCOLES.weekday(), SABADO.weekday(), DOMINGO.weekday()) == (0, 2, 5, 6)


# ── R14: next_month y YYYY-MM ────────────────────────────────────────────────────────────────────────────────────────

def test_next_month_desde_noviembre_es_diciembre_entero(cal):
    assert cal._time_window_to_range("next_month", LUNES) == (date(2026, 12, 1), date(2026, 12, 31))


def test_next_month_desde_diciembre_es_enero_del_año_siguiente(cal):
    assert cal._time_window_to_range("next_month", date(2026, 12, 20)) == (date(2027, 1, 1), date(2027, 1, 31))


def test_next_month_desde_enero_acaba_en_febrero_de_28_o_29_dias(cal):
    assert cal._time_window_to_range("next_month", date(2027, 1, 31)) == (date(2027, 2, 1), date(2027, 2, 28))
    assert cal._time_window_to_range("next_month", date(2027, 12, 31)) == (date(2028, 1, 1), date(2028, 1, 31))
    assert cal._time_window_to_range("next_month", date(2028, 1, 15)) == (date(2028, 2, 1), date(2028, 2, 29))


def test_yyyy_mm_es_el_mes_entero(cal):
    assert cal._time_window_to_range("2026-12", LUNES) == (date(2026, 12, 1), date(2026, 12, 31))
    assert cal._time_window_to_range("2027-02", LUNES) == (date(2027, 2, 1), date(2027, 2, 28))


def test_month_sigue_siendo_el_mes_en_curso_desde_hoy(cal):
    assert cal._time_window_to_range("month", LUNES) == (LUNES, date(2026, 11, 30))


@pytest.mark.parametrize("valor", ["2026-13", "2026-00", "2026-1", "26-12", "2026-12-01", "diciembre", "next_week", "", "2026/12"])
def test_un_mes_mal_escrito_es_error_y_no_hoy(cal, valor):
    with pytest.raises(ValueError):
        cal._time_window_to_range(valor, LUNES)


def test_list_events_lee_diciembre_con_next_month_y_con_yyyy_mm(cal):
    cal.add_event("Endoscopia", date(2026, 12, 17), "09:30")
    cal.add_event("Cena de noviembre", date(2026, 11, 20), "21:00")
    cal.add_event("Concierto de enero", date(2027, 1, 8), "20:00")
    for ventana in ("next_month", "2026-12"):
        titulos = [e["title"] for e in cal.list_events(ventana, hoy=LUNES)]
        assert titulos == ["Endoscopia"], ventana


def test_un_evento_recurrente_sale_en_next_month_igual_que_en_month(cal):
    cal.add_event("Inglés", date(2026, 11, 2), "19:00", recurrence_rule="weekly:MON")
    este = [e for e in cal.list_events("month", hoy=LUNES) if e["title"] == "Inglés"]
    proximo = [e for e in cal.list_events("next_month", hoy=LUNES) if e["title"] == "Inglés"]
    assert [e["date"] for e in este] == [date(2026, 11, 16), date(2026, 11, 23), date(2026, 11, 30)]
    assert [e["date"] for e in proximo] == [date(2026, 12, 7), date(2026, 12, 14), date(2026, 12, 21), date(2026, 12, 28)]
    assert all(e["recurring"] for e in proximo)


# ── R15: weekend ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_weekend_desde_un_miercoles_es_el_proximo_sabado_y_domingo(cal):
    assert cal._time_window_to_range("weekend", MIERCOLES) == (SABADO, DOMINGO)
    assert cal._time_window_to_range("weekend", LUNES) == (SABADO, DOMINGO)
    assert cal._time_window_to_range("weekend", date(2026, 11, 20)) == (SABADO, DOMINGO)       # viernes


def test_weekend_desde_un_sabado_es_hoy_y_mañana(cal):
    assert cal._time_window_to_range("weekend", SABADO) == (SABADO, DOMINGO)


def test_weekend_desde_un_domingo_es_solo_hoy(cal):
    assert cal._time_window_to_range("weekend", DOMINGO) == (DOMINGO, DOMINGO)


def test_weekend_lista_los_eventos_del_fin_de_semana_y_no_los_de_hoy(cal):
    cal.add_event("Hoy lunes", LUNES, "10:00")
    cal.add_event("Paseo", SABADO, "11:00")
    cal.add_event("Comida", DOMINGO, "14:00")
    cal.add_event("Lunes siguiente", date(2026, 11, 23), "10:00")
    assert [e["title"] for e in cal.list_events("weekend", hoy=LUNES)] == ["Paseo", "Comida"]


# ── R16: un valor desconocido no se lee como hoy ─────────────────────────────────────────────────────────────────────

def test_el_error_nombra_los_valores_validos(cal):
    with pytest.raises(ValueError) as e:
        cal.list_events("el_mes_que_viene", hoy=LUNES)
    mensaje = str(e.value)
    for valido in ("today", "tomorrow", "week", "month", "next_month", "weekend", "YYYY-MM"):
        assert valido in mensaje, valido


def test_el_ejecutor_devuelve_el_error_y_no_lanza(conn):
    r = ToolExecutor(conn, USUARIO).execute("calendar_list_events", {"time_window": "el_mes_que_viene"})
    assert isinstance(r, dict) and r["status"] == "invalid"
    assert "next_month" in r["message"] and "YYYY-MM" in r["message"]


def test_el_ejecutor_sin_time_window_tambien_devuelve_error(conn):
    r = ToolExecutor(conn, USUARIO).execute("calendar_list_events", {})
    assert isinstance(r, dict) and r["status"] == "invalid"


def test_el_ejecutor_sigue_devolviendo_una_lista_con_una_ventana_valida(conn):
    assert ToolExecutor(conn, USUARIO).execute("calendar_list_events", {"time_window": "next_month"}) == []
    assert ToolExecutor(conn, USUARIO).execute("calendar_list_events", {"time_window": "2026-12"}) == []


# ── Esquema y descripción ────────────────────────────────────────────────────────────────────────────────────────────

def _tool():
    return next(t for t in CALENDAR_TOOLS if t["name"] == "calendar_list_events")


def test_el_esquema_no_cierra_los_valores_y_la_descripcion_los_lista():
    """JSON Schema no deja combinar `enum` y `pattern`: sin `enum`, los valores van en la descripción y valida el ejecutor."""
    prop = _tool()["input_schema"]["properties"]["time_window"]
    assert "enum" not in prop
    d = " ".join(prop["description"].split())
    for valor in ("today", "tomorrow", "week", "month", "next_month", "weekend", "YYYY-MM"):
        assert valor in d, valor


def test_la_descripcion_manda_el_mes_que_viene_a_next_month_y_un_mes_con_nombre_a_yyyy_mm():
    d = " ".join(_tool()["description"].split())
    assert "el mes que viene" in d and "`next_month`" in d
    assert "diciembre" in d and "`YYYY-MM`" in d and "año" in d


def test_la_descripcion_dice_que_lo_que_hay_que_hacer_esta_en_compromisos_listar():
    """D55: cada familia de tools dice qué no es suya."""
    d = " ".join(_tool()["description"].split())
    assert "compromisos_listar" in d and "pasos" in d and "preparaciones" in d
