"""Fase 3 H3b (H3-revision §4): el `estado:` de un golden se siembra y se limpia. Sin API.

Prueba `tests/golden/estado.py` contra `sebastian_test`, y que los goldens que lo llevan lo traen bien formado."""
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from db.connection import close_connection, get_connection
from tests.golden.estado import limpiar_agenda, limpiar_sembrado, sembrar_estado

A = "test_golden_estado_a"
B = "test_golden_estado_b"

ESTADO = {
    "eventos": [{"titulo": "Endoscopia", "fecha": "2027-01-28", "hora": "09:30"}],
    "compromisos": [{"texto": "Primera toma del preparado", "dias_inicio": -1, "hora": "21:00"}],
}


@pytest.fixture
def conn():
    c = get_connection()
    limpiar_agenda(c, A, B)
    yield c
    limpiar_agenda(c, A, B)
    limpiar_sembrado(c)
    close_connection()


def _filas(c, tabla, user):
    c.commit()                                                   # REPEATABLE READ
    cur = c.cursor()
    cur.execute(f"SELECT * FROM {tabla} WHERE user_id = %s", (user,))
    return list(cur.fetchall())


def test_estado_se_siembra_y_se_limpia(conn):
    sembrado = sembrar_estado(conn, A, ESTADO)
    eventos, compromisos = _filas(conn, "events", A), _filas(conn, "compromisos", A)
    assert [e["id"] for e in eventos] == sembrado["eventos"] and eventos[0]["title"] == "Endoscopia"
    assert eventos[0]["start_datetime"] == datetime(2027, 1, 28, 9, 30)
    assert len(compromisos) == 1 and compromisos[0]["evento_id"] == eventos[0]["id"]
    assert compromisos[0]["dias_inicio"] == -1 and compromisos[0]["estado"] == "pendiente"

    limpiar_agenda(conn, A)                                      # compromisos primero: la FK no lleva ON DELETE
    assert _filas(conn, "events", A) == [] and _filas(conn, "compromisos", A) == []


def test_limpiar_sembrado_borra_solo_lo_sembrado(conn):
    """El usuario de goldens comparte la agenda con la fixture de sesión (el «teatro»): eso no se toca."""
    from modules.calendar import CalendarModule
    from modules.compromisos import CompromisosModule

    teatro = CalendarModule(conn, A).add_event("teatro", date(2027, 5, 5), "20:00")["event_id"]
    sembrado = sembrar_estado(conn, A, ESTADO)
    # Un compromiso que el propio golden creó sobre la cita sembrada: sin borrarlo antes, la FK impediría borrar el evento.
    CompromisosModule(conn, A).crear([{"texto": "Dieta blanda", "evento_id": sembrado["eventos"][0], "dias_inicio": -3}])

    limpiar_sembrado(conn)
    assert [e["id"] for e in _filas(conn, "events", A)] == [teatro]
    assert _filas(conn, "compromisos", A) == []
    limpiar_sembrado(conn)                                       # y es idempotente: la lista quedó vacía


def test_el_estado_no_toca_a_otros_usuarios(conn):
    sembrar_estado(conn, B, ESTADO)
    sembrar_estado(conn, A, ESTADO)
    limpiar_agenda(conn, A)
    assert len(_filas(conn, "events", B)) == 1 and len(_filas(conn, "compromisos", B)) == 1


def test_fecha_manana_se_calcula_al_sembrar(conn):
    hoy = date(2026, 12, 5)
    sembrar_estado(conn, A, {"eventos": [{"titulo": "Endoscopia", "fecha": "manana", "hora": "09:30"}]}, hoy=hoy)
    assert _filas(conn, "events", A)[0]["start_datetime"] == datetime(2026, 12, 6, 9, 30)


def test_sin_estado_no_hace_nada(conn):
    assert sembrar_estado(conn, A, None) == {"eventos": [], "compromisos": []}
    assert _filas(conn, "events", A) == []


def test_compromisos_sin_evento_se_rechazan(conn):
    with pytest.raises(ValueError):
        sembrar_estado(conn, A, {"compromisos": [{"texto": "X", "dias_inicio": -1}]})


def test_no_siembra_fuera_de_la_bd_de_test(conn, monkeypatch):
    import tests.golden.estado as estado
    from tests.golden.memoria_base import exigir_bd_de_test

    def _otra(db):
        raise RuntimeError("solo sebastian_test")

    monkeypatch.setattr(estado, "exigir_bd_de_test", _otra)
    with pytest.raises(RuntimeError):
        estado.sembrar_estado(conn, A, ESTADO)
    with pytest.raises(RuntimeError):
        estado.limpiar_agenda(conn, A)
    exigir_bd_de_test(conn)                                      # y la guarda real sí deja pasar a sebastian_test


GOLDENS = yaml.safe_load((Path(__file__).parent / "golden" / "goldens.yaml").read_text(encoding="utf-8"))


def _golden(ident):
    return next(g for g in GOLDENS if g["id"] == ident)


@pytest.mark.parametrize("ident", [68, 69, 72, 74])
def test_los_goldens_con_la_cita_de_enero_traen_su_estado(ident):
    assert _golden(ident)["estado"] == {"eventos": [{"titulo": "Endoscopia", "fecha": "2027-01-28", "hora": "09:30"}]}


def test_el_golden_71_trae_la_cita_de_manana_y_la_primera_toma():
    estado = _golden(71)["estado"]
    assert estado["eventos"] == [{"titulo": "Endoscopia", "fecha": "manana", "hora": "09:30"}]
    assert estado["compromisos"] == [{"texto": "Primera toma del preparado", "dias_inicio": -1, "hora": "21:00"}]


def test_el_golden_67_pone_fecha_explicita_y_el_76_acepta_preguntar_en_texto():
    assert _golden(67)["phrase"] == "El lunes 14 de diciembre empiezo la dieta blanda, tres días"
    assert _golden(67)["mode"] == "any_of"                 # H3-revision §12.1: también `[]` y `[request_clarification]`
    assert _golden(67)["expected"] == [["compromisos_crear"], [], ["request_clarification"]]
    assert ["compromisos_listar", "compromisos_completar", "compromisos_listar"] in _golden(71)["expected"]   # §12.2
    assert [] in _golden(76)["expected"] and _golden(76)["mode"] == "any_of"


def test_h3c_el_golden_40_acepta_compromiso_o_pregunta_y_el_76_acepta_solo_buscar():
    """H3-revision (segunda), §9, tal cual: #40 es compromiso, cita o pregunta por el día (lo único que falla es salud)."""
    assert _golden(40)["expected"] == [["calendar_add_event"], [], ["compromisos_crear"], ["request_clarification"]]
    assert _golden(40)["validates"] == "Fase 3: «recuérdame» es compromiso, cita o pregunta por el día; lo único que falla es salud"
    assert ["calendar_search_events"] in _golden(76)["expected"]


def test_el_golden_62_sigue_exacto_y_el_74_no_cambia_sus_listas():
    assert _golden(62)["mode"] == "exact" and _golden(62)["expected"] == ["mark_as_memorable"]
    assert [["compromisos_crear"], ["calendar_search_events", "compromisos_crear"],
            ["calendar_find_by_datetime", "compromisos_crear"], ["calendar_add_note"],
            ["calendar_search_events", "calendar_add_note"]] == _golden(74)["expected"]
