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


def test_h3d_el_golden_49_acepta_solo_lecturas_y_nunca_escribir():
    """H3-revision (cuarta), §15.2: mirar el inventario o la memoria antes de proponer una cena es una lectura inofensiva."""
    g = _golden(49)
    assert g["mode"] == "any_of" and g["phrase"] == "¿qué ceno hoy?"
    assert g["expected"] == [[], ["inventory_list"], ["search_memory"], ["inventory_list", "search_memory"],
                             ["search_memory", "inventory_list"]]
    assert not any("salud" in seq or "mark_as_memorable" in seq for seq in g["expected"])


def test_h5_los_goldens_77_y_78_son_los_del_arquitecto_tal_cual():
    """H5-encargo §3: copiados tal cual. Solo comparan nombres de tools; el `time_window` sale en el informe."""
    lista = [["calendar_list_events"], ["calendar_list_events", "compromisos_listar"],
             ["compromisos_listar", "calendar_list_events"]]
    for ident, frase in ((77, "¿Cómo se presenta el mes de diciembre?"), (78, "¿Qué tengo el mes que viene?")):
        g = _golden(ident)
        assert g["phrase"] == frase and g["mode"] == "any_of" and g["expected"] == lista
        assert "estado" not in g and "historia" not in g
    assert _golden(77)["validates"].startswith("Fase 3 H5 (R14)") and "next_month" in _golden(78)["validates"]


def test_el_golden_62_sigue_exacto_y_el_74_no_cambia_sus_listas():
    assert _golden(62)["mode"] == "exact" and _golden(62)["expected"] == ["mark_as_memorable"]
    assert [["compromisos_crear"], ["calendar_search_events", "compromisos_crear"],
            ["calendar_find_by_datetime", "compromisos_crear"], ["calendar_add_note"],
            ["calendar_search_events", "calendar_add_note"]] == _golden(74)["expected"]


# ── H7: goldens #79 y #80 y su criterio (qué se creó, no solo qué tools) ─────────────────────────────────────────────

def test_h7_los_goldens_79_y_80_son_los_del_encargo_adaptados_al_arnes():
    g79, g80 = _golden(79), _golden(80)
    assert g79["phrase"] == "Recuérdame esta noche a la una de la madrugada que me duerma ya"
    assert g80["phrase"] == "Recuérdame mañana martes 17 de noviembre a la 01:00 que me duerma ya"
    assert g79["ahora"] == g80["ahora"] == "2026-11-16T16:30"                    # lunes, 16:30: la hora del encargo
    assert g79["entrada"] == g80["entrada"] == {"fecha_inicio": "2026-11-17", "hora": "01:00"}
    assert g79["alfred_menciona"] == ["17"] and "alfred_menciona" not in g80
    assert [p["user"] for p in g80["historia"]] == [
        "¿Qué tengo el mes que viene?", "Recuérdame el 17 a la una de la madrugada que me duerma ya",
        "Borra el recordatorio «Duérmete ya» del 17 de diciembre"]
    assert g80["estado"] == {"eventos": [{"titulo": "Endoscopia", "fecha": "2026-12-17", "hora": "09:30"}]}


def _crea(fecha, hora="01:00", texto="Duerme ya"):
    return [{"items": [{"texto": texto, "fecha_inicio": fecha, "hora": hora}]}]


def test_h7_el_79_pasa_con_la_fecha_de_manana_y_alfred_diciendo_el_17():
    from tests.golden.criterios import evaluar_compromiso
    g = _golden(79)
    assert evaluar_compromiso(g, ["compromisos_crear"], _crea("2026-11-17"), "Anotado: martes 17/11 a las 01:00, señor.")
    assert not evaluar_compromiso(g, ["compromisos_crear"], _crea("2026-11-17"), "A la una de la madrugada le aviso.")
    assert not evaluar_compromiso(g, ["compromisos_crear"], _crea("2026-11-16"), "Anotado: lunes 16/11, el 17 no.")
    assert not evaluar_compromiso(g, ["compromisos_crear"], _crea("2026-11-17", "02:00"), "martes 17/11")
    assert not evaluar_compromiso(g, [], [], "¿Lo quiere esta noche o mañana?")          # el 79 no admite preguntar


def test_h7_el_80_acepta_crear_el_17_11_o_preguntar_y_rechaza_el_17_12_y_el_no_he_podido():
    from tests.golden.criterios import evaluar_compromiso
    g = _golden(80)
    assert evaluar_compromiso(g, ["compromisos_crear"], _crea("2026-11-17"), "Anotado, señor.")
    assert evaluar_compromiso(g, [], [], "¿Se refiere al martes 17 de noviembre o al 17 de diciembre, señor?")
    assert evaluar_compromiso(g, ["request_clarification"], [], "¿A qué día se refiere, señor?")
    assert not evaluar_compromiso(g, ["compromisos_crear"], _crea("2026-12-17"), "Anotado, señor.")
    assert not evaluar_compromiso(g, [], [], "Lo siento, señor: no he podido programar ese recordatorio.")
    # Observado en la pasada de H7 (ejecución 2): lleva «?» pero es el «no he podido» de producción con una oferta de reintento.
    assert not evaluar_compromiso(
        g, [], [], "Lo siento, señor — no he podido crear el recordatorio en este turno. ¿Lo intento de nuevo?")
    assert not evaluar_compromiso(g, ["compromisos_crear", "compromisos_crear"], _crea("2026-11-17"), "Anotado.")


# ── H9: goldens #81–#85 y su criterio (qué fecha llevó el evento creado o movido, y lo que dice Alfred) ──────────────

def test_h9_los_goldens_81_a_85_son_los_del_encargo_adaptados_al_arnes():
    g = {i: _golden(i) for i in range(81, 86)}
    assert all(g[i]["mode"] == "calendario" for i in g)
    assert g[81]["phrase"] == ("Este viernes tengo cena de Navidad de BNP. Es en calle de las Huertas 41, Madrid, a las 20:30")
    assert g[81]["ahora"] == "2026-11-19T08:06" and g[81]["expected"] == ["calendar_add_event"]
    assert g[81]["entrada"] == {"date": "2026-11-20", "time": "20:30"} and g[81]["alfred_menciona"] == ["20"]
    assert g[82]["phrase"] == "El lunes a las 10 tengo dentista" and g[82]["ahora"] == "2026-11-19T08:06"
    assert g[82]["entrada"] == {"date": "2026-11-23", "time": "10:00"}
    assert g[83]["phrase"] == "El miércoles a las 9 tengo reunión con el gestor" and g[83]["ahora"] == "2026-11-21T12:00"
    assert g[83]["entrada"] == {"date": "2026-11-25", "time": "09:00"}
    assert g[84]["phrase"] == "Mueve la cena de Navidad de BNP al viernes 20 de noviembre a las 20:30"
    assert g[84]["ahora"] == "2026-11-19T08:34" and g[84]["expected"] == ["calendar_search_events", "calendar_update_event"]
    assert g[84]["estado"] == {"eventos": [{"titulo": "Cena de Navidad BNP - TBC", "fecha": "2026-11-27", "hora": "20:30"}]}
    assert g[84]["entrada_update"] == {"new_date": "2026-11-20"}
    assert g[85]["phrase"] == "¿Cuándo es la cena con los de la uni?" and g[85]["ahora"] == "2026-11-19T09:00"
    assert g[85]["estado"] == {"eventos": [{"titulo": "Cena de Navidad BNP - TBC", "fecha": "2026-11-20", "hora": "20:30"}]}
    assert g[85]["expected_any"] == ["calendar_search_events", "calendar_list_events"]
    for i in (84, 85):
        assert {"no llegó a guardarse", "no se guardó", "no quedó guardada"} <= set(g[i]["alfred_no_menciona"])


def test_h9_el_arnes_fija_el_reloj_nuevo_y_no_el_que_ya_no_existe():
    """`patch("core.orchestrator._now_str")` daría AttributeError en todos los goldens con `ahora`."""
    fuente = (Path(__file__).parent / "golden" / "conftest.py").read_text(encoding="utf-8")
    assert "_now_str" not in fuente and "core.orchestrator._reloj" in fuente


def _add(fecha, hora):
    return {"calendar_add_event": [{"title": "Cena de Navidad BNP", "date": fecha, "time": hora}]}


def test_h9_el_81_pide_el_viernes_20_a_las_20_30_y_que_alfred_diga_el_20():
    from tests.golden.criterios import evaluar_calendario
    g = _golden(81)
    assert evaluar_calendario(g, ["calendar_add_event"], _add("2026-11-20", "20:30"), "Apuntado: viernes 20/11 a las 20:30.")
    assert not evaluar_calendario(g, ["calendar_add_event"], _add("2026-11-27", "20:30"), "Apuntado: viernes 20/11.")   # la fecha del 19/11
    assert not evaluar_calendario(g, ["calendar_add_event"], _add("2026-11-20", "21:00"), "viernes 20/11")
    assert not evaluar_calendario(g, ["calendar_add_event"], _add("2026-11-20", "20:30"), "Apuntado, señor.")           # no dice el 20
    assert not evaluar_calendario(g, ["calendar_search_events", "calendar_add_event"], _add("2026-11-20", "20:30"), "viernes 20")
    assert not evaluar_calendario(g, [], {}, "¿Qué día, señor? 20")
    assert not evaluar_calendario(g, ["calendar_add_event", "calendar_add_event"],
                                  {"calendar_add_event": _add("2026-11-20", "20:30")["calendar_add_event"] * 2}, "viernes 20")


def test_h9_el_82_y_el_83_cruzan_el_fin_de_semana_y_no_exigen_texto():
    from tests.golden.criterios import evaluar_calendario
    assert evaluar_calendario(_golden(82), ["calendar_add_event"], _add("2026-11-23", "10:00"), "Apuntado.")
    assert not evaluar_calendario(_golden(82), ["calendar_add_event"], _add("2026-11-30", "10:00"), "Apuntado.")
    assert evaluar_calendario(_golden(83), ["calendar_add_event"], _add("2026-11-25", "09:00"), "Apuntado.")
    assert not evaluar_calendario(_golden(83), ["calendar_add_event"], _add("2026-11-18", "09:00"), "Apuntado.")


def _upd(fecha):
    return {"calendar_update_event": [{"event_id": 1, "new_date": fecha, "new_time": "20:30"}]}


def test_h9_el_84_busca_y_mueve_al_20_y_no_dice_que_no_se_guardo():
    from tests.golden.criterios import evaluar_calendario
    g = _golden(84)
    sec = ["calendar_search_events", "calendar_update_event"]
    assert evaluar_calendario(g, sec, _upd("2026-11-20"), "Movida al viernes 20/11 a las 20:30, señor.")
    assert not evaluar_calendario(g, sec, _upd("2026-11-27"), "Movida.")
    assert not evaluar_calendario(g, ["calendar_search_events"], {}, "No la encuentro.")
    assert not evaluar_calendario(g, ["calendar_search_events", "calendar_add_event"], _add("2026-11-20", "20:30"), "Creada.")
    for frase in ("Parece que no llegó a guardarse. ¿La anoto?", "Creo que NO SE GUARDÓ.", "No quedó guardada, señor."):
        assert not evaluar_calendario(g, sec, _upd("2026-11-20"), frase)


def test_h9_el_85_acepta_buscar_o_listar_y_rechaza_dar_la_de_bnp_por_la_de_la_uni():
    from tests.golden.criterios import evaluar_calendario
    g = _golden(85)
    assert evaluar_calendario(g, ["calendar_search_events"], {}, "No encuentro una cena con los de la uni. Hay una cena de Navidad BNP el 20/11.")
    assert evaluar_calendario(g, ["calendar_list_events"], {}, "No consta, señor.")
    assert evaluar_calendario(g, ["calendar_search_events", "calendar_list_events"], {}, "No consta.")
    assert not evaluar_calendario(g, [], {}, "No consta.")                                   # sin mirar no vale
    assert not evaluar_calendario(g, ["calendar_search_events", "calendar_add_event"], {}, "No consta.")   # nunca escribe
    assert not evaluar_calendario(g, ["calendar_search_events"], {}, "Su cena con los de la uni es el viernes 20.")
    assert not evaluar_calendario(g, ["calendar_search_events"], {}, "Parece que no se guardó la cena. ¿La anoto?")
