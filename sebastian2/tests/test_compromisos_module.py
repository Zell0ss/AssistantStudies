"""Fase 3, H1 (D45, D50, plan §2.1 y §3-H1): compromisos, su forma y su momento efectivo.

Contra `sebastian_test`, sin API y con un reloj inyectado (nunca `datetime.now()` directo). El caso es el de la
endoscopia con datos INVENTADOS (prueba, dieta, nombres y centro; la fecha de la cita, 17/12/2026, es la del calendario del plan).
"""
from datetime import date, datetime, time

import pytest

from db.connection import close_connection, get_connection
from modules.calendar import CalendarModule
from modules.compromisos import CompromisosModule, FormaInvalida, validar_forma

AHORA = datetime(2026, 12, 1, 12, 0)
USUARIO = "test_user_compromisos"
OTRO = "test_user_compromisos_otro"


def _limpiar(conn):
    cur = conn.cursor()
    for u in (USUARIO, OTRO):
        cur.execute("DELETE FROM compromisos WHERE user_id = %s", (u,))
        cur.execute("DELETE FROM events WHERE user_id = %s", (u,))
    conn.commit()


@pytest.fixture
def conn():
    c = get_connection()
    _limpiar(c)
    yield c
    _limpiar(c)
    close_connection()


@pytest.fixture
def cal(conn):
    return CalendarModule(conn, USUARIO)


@pytest.fixture
def comp(conn):
    return CompromisosModule(conn, USUARIO, reloj=lambda: AHORA)


@pytest.fixture
def cita(cal):
    """La cita del caso: jueves 17/12/2026 a las 9:30."""
    return cal.add_event("Endoscopia", date(2026, 12, 17), "09:30")["event_id"]


def _caso(evento_id):
    """Los cinco momentos del caso, todos atados al evento."""
    return [
        {"texto": "Dieta blanda", "evento_id": evento_id, "dias_inicio": -3, "dias_fin": -1},
        {"texto": "Solo líquidos claros", "evento_id": evento_id, "dias_inicio": -1},
        {"texto": "1.ª toma del preparado", "evento_id": evento_id, "dias_inicio": -1, "hora": "21:00"},
        {"texto": "2.ª toma del preparado", "evento_id": evento_id, "dias_inicio": 0, "hora": "01:00"},
        {"texto": "Última hora para líquidos", "evento_id": evento_id, "minutos": -180},
    ]


def _por_texto(resultado):
    return {c["texto"]: c for c in resultado["compromisos"]}


# ── Forma (plan §2.1: «Reglas de forma», en el repositorio) ──────────────────────────────────────────────────────────

def test_forma_suelto_exige_fecha():
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "Llamar al médico", "hora": "10:00"})
    validar_forma({"texto": "Llamar al médico", "fecha_inicio": "2026-12-10"})


def test_forma_atado_dias_o_minutos_no_ambos():
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "evento_id": 1, "dias_inicio": -1, "minutos": -60})
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "evento_id": 1})                     # atado sin ninguno de los dos
    validar_forma({"texto": "x", "evento_id": 1, "dias_inicio": -1})
    validar_forma({"texto": "x", "evento_id": 1, "minutos": -60})


def test_forma_intervalo_sin_hora():
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "fecha_inicio": "2026-12-14", "fecha_fin": "2026-12-16", "hora": "09:00"})
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "evento_id": 1, "dias_inicio": -3, "dias_fin": -1, "hora": "09:00"})


def test_forma_minutos_sin_hora():
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "evento_id": 1, "minutos": -180, "hora": "06:30"})
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "evento_id": 1, "minutos": -180, "dias_fin": 0})   # dias_fin tampoco va con minutos


def test_forma_mezclar_suelto_y_atado_es_invalido():
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "evento_id": 1, "dias_inicio": -1, "fecha_inicio": "2026-12-16"})
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "dias_inicio": -1})                  # desfase sin evento
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "minutos": -60})


def test_forma_texto_obligatorio_y_acotado():
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "  ", "fecha_inicio": "2026-12-10"})
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "a" * 501, "fecha_inicio": "2026-12-10"})


def test_forma_intervalo_al_reves_es_invalido():
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "fecha_inicio": "2026-12-16", "fecha_fin": "2026-12-14"})
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "evento_id": 1, "dias_inicio": -1, "dias_fin": -3})
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "evento_id": 1, "dias_fin": -1})     # fin sin inicio


def test_forma_fechas_y_horas_mal_escritas_son_invalidas():
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "fecha_inicio": "mañana"})
    with pytest.raises(FormaInvalida):
        validar_forma({"texto": "x", "fecha_inicio": "2026-12-10", "hora": "25:99"})


def test_crear_rechaza_forma_invalida_y_no_guarda_nada(comp, cita, conn):
    r = comp.crear([{"texto": "bien", "fecha_inicio": "2026-12-10"},
                    {"texto": "mal", "evento_id": cita, "dias_inicio": -1, "minutos": -60}])
    assert r["status"] == "invalid" and r["indice"] == 1
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM compromisos WHERE user_id = %s", (USUARIO,))
    assert cur.fetchone()["n"] == 0                                       # todo o nada


def test_crear_cuenta_de_items(comp):
    assert comp.crear([])["status"] == "invalid"
    assert comp.crear([{"texto": f"t{i}", "fecha_inicio": "2026-12-10"} for i in range(21)])["status"] == "invalid"
    assert comp.crear([{"texto": f"t{i}", "fecha_inicio": "2026-12-10"} for i in range(20)])["status"] == "created"


def test_evento_ajeno_o_inexistente_no_se_puede_atar(comp, conn):
    otro_evento = CalendarModule(conn, OTRO).add_event("Cita de otro", date(2026, 12, 17), "09:30")["event_id"]
    assert comp.crear([{"texto": "x", "evento_id": otro_evento, "dias_inicio": -1}])["status"] == "invalid"
    assert comp.crear([{"texto": "x", "evento_id": 999999999, "dias_inicio": -1}])["status"] == "invalid"


def test_evento_de_todo_el_dia_solo_admite_dias(comp, cal):
    todo_el_dia = cal.add_event("Revisión", date(2026, 12, 17), all_day=True)["event_id"]
    assert comp.crear([{"texto": "x", "evento_id": todo_el_dia, "minutos": -60}])["status"] == "invalid"
    r = comp.crear([{"texto": "x", "evento_id": todo_el_dia, "dias_inicio": -1, "hora": "21:00"}])
    assert r["status"] == "created"
    assert r["compromisos"][0]["cuando"] == "2026-12-16T21:00"


def test_evento_recurrente_no_admite_compromisos_atados(comp, cal):
    semanal = cal.add_event("Yoga", date(2026, 12, 17), "19:00", recurrence_rule="weekly:THU")["event_id"]
    assert comp.crear([{"texto": "x", "evento_id": semanal, "minutos": -60}])["status"] == "invalid"


# ── Momento efectivo (plan §2.1) ─────────────────────────────────────────────────────────────────────────────────────

def test_momento_atado_minutos(comp, cita):
    r = comp.crear([{"texto": "Fin de líquidos", "evento_id": cita, "minutos": -180}])
    c = r["compromisos"][0]
    assert c["cuando"] == "2026-12-17T06:30"
    assert c["fecha_inicio"] == c["fecha_fin"] == "2026-12-17"


def test_momento_atado_dias_hora(comp, cita):
    por_texto = _por_texto(comp.crear(_caso(cita)))
    assert por_texto["1.ª toma del preparado"]["cuando"] == "2026-12-16T21:00"
    assert por_texto["2.ª toma del preparado"]["cuando"] == "2026-12-17T01:00"


def test_intervalo_dieta(comp, cita):
    dieta = _por_texto(comp.crear(_caso(cita)))["Dieta blanda"]
    assert dieta["fecha_inicio"] == "2026-12-14" and dieta["fecha_fin"] == "2026-12-16"   # ambos incluidos
    assert dieta["cuando"] is None                                                         # sin hora: todo el día


def test_momento_suelto_con_hora_y_sin_hora(comp):
    r = comp.crear([{"texto": "Recoger el parte", "fecha_inicio": "2026-12-10", "hora": "17:30"},
                    {"texto": "Empezar la dieta", "fecha_inicio": "2026-12-14", "fecha_fin": "2026-12-16"}])
    a, b = r["compromisos"]
    assert a["cuando"] == "2026-12-10T17:30" and a["evento_id"] is None
    assert b["cuando"] is None and (b["fecha_inicio"], b["fecha_fin"]) == ("2026-12-14", "2026-12-16")


def test_crear_devuelve_momento_efectivo(comp, cita):
    """Alfred repite fechas reales: cada compromiso vuelve con el momento ya calculado y escrito en llano."""
    por_texto = _por_texto(comp.crear(_caso(cita)))
    assert por_texto["2.ª toma del preparado"]["cuando_texto"] == "jueves 17/12 a las 01:00"
    assert por_texto["1.ª toma del preparado"]["cuando_texto"] == "miércoles 16/12 a las 21:00"
    assert por_texto["Dieta blanda"]["cuando_texto"] == "del lunes 14/12 al miércoles 16/12"
    assert por_texto["Solo líquidos claros"]["cuando_texto"] == "miércoles 16/12"
    for c in por_texto.values():
        assert isinstance(c["id"], int) and c["estado"] == "pendiente" and c["evento_id"] == cita


def test_cambio_de_hora(comp, cal):
    """Lunes 29/03/2027, tras el cambio de hora del domingo 28: «la víspera a las 21:00» es 21:00 de reloj."""
    lunes = cal.add_event("Revisión", date(2027, 3, 29), "09:30")["event_id"]
    c = comp.crear([{"texto": "Cena ligera", "evento_id": lunes, "dias_inicio": -1, "hora": "21:00"}])["compromisos"][0]
    assert c["cuando"] == "2027-03-28T21:00"


def test_evento_movido_mueve_compromisos(comp, cal, cita):
    antes = _por_texto(comp.crear(_caso(cita)))
    assert cal.update_event("Endoscopia", new_date=date(2026, 12, 18))["status"] == "updated"
    despues = {c["texto"]: c for c in comp.listar(desde="2026-12-01", hasta="2026-12-31")["compromisos"]}
    assert len(despues) == 5
    assert despues["Dieta blanda"]["fecha_inicio"] == "2026-12-15"
    assert despues["Dieta blanda"]["fecha_fin"] == "2026-12-17"
    assert despues["1.ª toma del preparado"]["cuando"] == "2026-12-17T21:00"
    assert despues["2.ª toma del preparado"]["cuando"] == "2026-12-18T01:00"
    assert despues["Última hora para líquidos"]["cuando"] == "2026-12-18T06:30"
    assert despues["Solo líquidos claros"]["fecha_inicio"] == "2026-12-17"
    assert antes["2.ª toma del preparado"]["cuando"] == "2026-12-17T01:00"            # y el día 17 ya no lo tiene


def test_evento_movido_por_id_mueve_compromisos(comp, cal, cita):
    """Fase 3 H3b (R2): lo mismo que arriba, pero identificando el evento por `event_id` (título equivocado a propósito)."""
    comp.crear(_caso(cita))
    assert cal.update_event(title="Colonoscopia", event_id=cita, new_date=date(2026, 12, 18))["status"] == "updated"
    despues = {c["texto"]: c for c in comp.listar(desde="2026-12-01", hasta="2026-12-31")["compromisos"]}
    assert len(despues) == 5
    assert despues["1.ª toma del preparado"]["cuando"] == "2026-12-17T21:00"
    assert despues["2.ª toma del preparado"]["cuando"] == "2026-12-18T01:00"


def test_evento_movido_de_hora_mueve_los_relativos_a_la_hora(comp, cal, cita):
    comp.crear([{"texto": "Fin de líquidos", "evento_id": cita, "minutos": -180}])
    cal.update_event("Endoscopia", new_time="11:00")
    assert comp.listar(desde="2026-12-17", hasta="2026-12-17")["compromisos"][0]["cuando"] == "2026-12-17T08:00"


def test_evento_que_pierde_su_hora_no_rompe_el_listado(comp, cal, cita):
    comp.crear([{"texto": "Fin de líquidos", "evento_id": cita, "minutos": -180}])
    # Pasar un evento a «todo el día» con fecha le quita la hora (start_datetime = NULL).
    cal.update_event("Endoscopia", new_date=date(2026, 12, 17), new_all_day=True)
    items = comp.listar(desde="2026-12-01", hasta="2026-12-31")["compromisos"]
    assert len(items) == 1                                                  # no explota ni se esconde
    assert items[0]["cuando"] is None and items[0]["problema"]              # y el problema se declara


# ── Evento borrado (D50) ─────────────────────────────────────────────────────────────────────────────────────────────

def test_evento_borrado_cancela_compromisos(comp, cal, cita, conn):
    ids = [c["id"] for c in comp.crear(_caso(cita))["compromisos"]]
    assert cal.remove_event("Endoscopia")["status"] == "removed"
    cur = conn.cursor()
    cur.execute("SELECT estado, evento_id FROM compromisos WHERE id IN %s", (tuple(ids),))
    filas = cur.fetchall()
    assert len(filas) == 5 and {f["estado"] for f in filas} == {"cancelado"}
    assert comp.listar(desde="2026-12-01", hasta="2026-12-31")["compromisos"] == []


def test_evento_borrado_por_id_tambien_cancela(comp, cal, cita, conn):
    cid = comp.crear(_caso(cita))["compromisos"][0]["id"]
    assert cal.remove_event_by_id(cita) is True
    cur = conn.cursor()
    cur.execute("SELECT estado FROM compromisos WHERE id = %s", (cid,))
    assert cur.fetchone()["estado"] == "cancelado"


def test_evento_borrado_respeta_los_hechos_y_los_sueltos(comp, cal, cita, conn):
    atado, suelto = comp.crear([{"texto": "atado", "evento_id": cita, "dias_inicio": -1},
                                {"texto": "suelto", "fecha_inicio": "2026-12-20"}])["compromisos"]
    comp.completar(atado["id"])
    cal.remove_event("Endoscopia")
    cur = conn.cursor()
    cur.execute("SELECT id, estado FROM compromisos WHERE user_id = %s", (USUARIO,))
    estados = {f["id"]: f["estado"] for f in cur.fetchall()}
    assert estados[atado["id"]] == "hecho"                                  # lo hecho sigue hecho
    assert estados[suelto["id"]] == "pendiente"                             # el suelto no es de ningún evento


def test_borrar_un_evento_sin_compromisos_sigue_funcionando(cal):
    cal.add_event("Dentista", date(2026, 12, 5), "17:00")
    assert cal.remove_event("Dentista")["status"] == "removed"


def test_borrar_un_evento_de_otro_usuario_no_toca_mis_compromisos(comp, cal, cita, conn):
    cid = comp.crear(_caso(cita))["compromisos"][0]["id"]
    CalendarModule(conn, OTRO).add_event("Endoscopia", date(2026, 12, 17), "09:30")
    CalendarModule(conn, OTRO).remove_event("Endoscopia")
    cur = conn.cursor()
    cur.execute("SELECT estado FROM compromisos WHERE id = %s", (cid,))
    assert cur.fetchone()["estado"] == "pendiente"


# ── Listar, completar, borrar ────────────────────────────────────────────────────────────────────────────────────────

def test_listar_por_defecto_de_hoy_a_catorce_dias_en_orden(comp, cita):
    comp.crear(_caso(cita) + [{"texto": "Lejano", "fecha_inicio": "2027-02-01"}])
    textos = [c["texto"] for c in comp.listar()["compromisos"]]
    # El reloj es el 1/12: de ahí a 14 días llega al 15/12. Solo la dieta (14→16) cae dentro; «Lejano» no.
    assert textos == ["Dieta blanda"]
    todos = comp.listar(desde="2026-12-01", hasta="2026-12-31")["compromisos"]
    assert [c["texto"] for c in todos] == [
        "Dieta blanda", "Solo líquidos claros", "1.ª toma del preparado",
        "2.ª toma del preparado", "Última hora para líquidos"]


def test_listar_el_intervalo_se_solapa_con_la_ventana(comp, cita):
    comp.crear(_caso(cita))
    en_el_15 = comp.listar(desde="2026-12-15", hasta="2026-12-15")["compromisos"]
    assert [c["texto"] for c in en_el_15] == ["Dieta blanda"]       # el 15 está dentro de 14→16


def test_listar_por_evento_y_solo_pendientes(comp, cal, cita):
    otra = cal.add_event("Dentista", date(2026, 12, 9), "17:00")["event_id"]
    comp.crear(_caso(cita) + [{"texto": "Llevar la tarjeta", "evento_id": otra, "minutos": -30}])
    de_la_cita = comp.listar(desde="2026-12-01", hasta="2026-12-31", evento_id=cita)["compromisos"]
    assert len(de_la_cita) == 5 and all(c["evento_id"] == cita for c in de_la_cita)
    primero = de_la_cita[0]["id"]
    comp.completar(primero)
    assert primero not in [c["id"] for c in comp.listar(desde="2026-12-01", hasta="2026-12-31")["compromisos"]]


def test_completar_pasa_a_hecho_y_no_repite(comp, cita, conn):
    cid = comp.crear([{"texto": "x", "evento_id": cita, "dias_inicio": -1}])["compromisos"][0]["id"]
    assert comp.completar(cid)["status"] == "completed"
    cur = conn.cursor()
    cur.execute("SELECT estado FROM compromisos WHERE id = %s", (cid,))
    assert cur.fetchone()["estado"] == "hecho"
    assert comp.completar(cid)["status"] == "no_pendiente"
    assert comp.completar(999999999)["status"] == "not_found"


def test_borrar_olvidar_hace_delete(comp, cita, conn):
    """D42: «olvida ese compromiso» borra la fila; no la deja cancelada."""
    cid = comp.crear([{"texto": "secreto", "evento_id": cita, "dias_inicio": -1}])["compromisos"][0]["id"]
    assert comp.borrar(cid, "olvidar")["status"] == "deleted"
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM compromisos WHERE id = %s", (cid,))
    assert cur.fetchone()["n"] == 0
    assert comp.borrar(cid, "olvidar")["status"] == "not_found"


def test_borrar_cancelar_conserva(comp, cita, conn):
    cid = comp.crear([{"texto": "x", "evento_id": cita, "dias_inicio": -1}])["compromisos"][0]["id"]
    assert comp.borrar(cid, "cancelar")["status"] == "cancelled"
    cur = conn.cursor()
    cur.execute("SELECT estado FROM compromisos WHERE id = %s", (cid,))
    assert cur.fetchone()["estado"] == "cancelado"


def test_borrar_motivo_desconocido_es_error(comp, cita):
    cid = comp.crear([{"texto": "x", "evento_id": cita, "dias_inicio": -1}])["compromisos"][0]["id"]
    assert comp.borrar(cid, "archivar")["status"] == "invalid"
    assert comp.borrar(cid, None)["status"] == "invalid"


def test_aislamiento_usuarios(conn, cita):
    a = CompromisosModule(conn, USUARIO, reloj=lambda: AHORA)
    b = CompromisosModule(conn, OTRO, reloj=lambda: AHORA)
    cid = a.crear([{"texto": "de A", "evento_id": cita, "dias_inicio": -1}])["compromisos"][0]["id"]
    assert b.listar(desde="2026-12-01", hasta="2026-12-31")["compromisos"] == []
    assert b.completar(cid)["status"] == "not_found"
    assert b.borrar(cid, "olvidar")["status"] == "not_found"
    assert b.borrar(cid, "cancelar")["status"] == "not_found"
    assert [c["texto"] for c in a.listar(desde="2026-12-01", hasta="2026-12-31")["compromisos"]] == ["de A"]
    # Y B no puede atar un compromiso a la cita de A (cubierto también en test_evento_ajeno_...).
    assert b.crear([{"texto": "robo", "evento_id": cita, "dias_inicio": -1}])["status"] == "invalid"


def test_el_reloj_inyectado_fija_created_at(comp, cita, conn):
    cid = comp.crear([{"texto": "x", "fecha_inicio": "2026-12-10"}])["compromisos"][0]["id"]
    cur = conn.cursor()
    cur.execute("SELECT created_at, updated_at FROM compromisos WHERE id = %s", (cid,))
    f = cur.fetchone()
    assert f["created_at"] == AHORA and f["updated_at"] == AHORA


def test_la_hora_vuelve_de_la_bd_como_hora(comp):
    """PyMySQL devuelve TIME como timedelta: no puede colarse en el resultado."""
    c = comp.crear([{"texto": "x", "fecha_inicio": "2026-12-10", "hora": "17:30"}])["compromisos"][0]
    assert c["hora"] == "17:30"
    listado = comp.listar(desde="2026-12-10", hasta="2026-12-10")["compromisos"][0]
    assert listado["hora"] == "17:30" and listado["cuando"] == "2026-12-10T17:30"


# ── R1 (H1-revision §4): Alfred tiene que poder contar qué se ha cancelado ────────────────────────────────────────────

def test_remove_event_informa_compromisos_cancelados(comp, cal, cita):
    comp.crear(_caso(cita))
    hecho = comp.listar(desde="2026-12-01", hasta="2026-12-31")["compromisos"][0]["id"]
    comp.completar(hecho)                                                   # los hechos no cuentan como cancelados
    r = cal.remove_event("Endoscopia")
    assert r["status"] == "removed" and r["compromisos_cancelados"] == 4


def test_remove_event_sin_compromisos_no_lleva_el_campo(cal):
    cal.add_event("Dentista", date(2026, 12, 5), "17:00")
    assert "compromisos_cancelados" not in cal.remove_event("Dentista")


def test_remove_event_de_varios_eventos_suma_los_cancelados(comp, cal, cita):
    otra = cal.add_event("Endoscopia", date(2027, 1, 20), "09:30")["event_id"]
    comp.crear([{"texto": "a", "evento_id": cita, "dias_inicio": -1}, {"texto": "b", "evento_id": otra, "dias_inicio": -1}])
    assert cal.remove_event("Endoscopia")["compromisos_cancelados"] == 2


def test_la_cuenta_de_cancelados_no_incluye_hechos_ni_cancelados(comp, cal, cita):
    a, b, c = (x["id"] for x in comp.crear(_caso(cita)[:3])["compromisos"])
    comp.completar(a)
    comp.borrar(b, "cancelar")
    assert cal.remove_event("Endoscopia")["compromisos_cancelados"] == 1


# ── R13 (H3-revision, cuarta, §16): crear no duplica ────────────────────────────────────────────────────────────────
# El caso de E10, turno 5: al mover la cita sus pasos ya se movieron solos (D50) y el planner los volvió a crear.

def _filas(conn, user=USUARIO):
    conn.commit()                                                                # REPEATABLE READ
    cur = conn.cursor()
    cur.execute("SELECT id, texto, dias_inicio, estado FROM compromisos WHERE user_id = %s ORDER BY id", (user,))
    return list(cur.fetchall())


def test_crear_no_duplica_pendiente_del_mismo_evento(comp, cita, conn):
    primero = comp.crear(_caso(cita))["compromisos"]
    # Misma frase, otros desfases (lo que hizo el planner tras mover la cita): no se inserta nada.
    segundo = comp.crear([{"texto": c["texto"], "evento_id": cita, "dias_inicio": -2} for c in primero])
    assert segundo["status"] == "exists"
    assert [c["id"] for c in segundo["compromisos"]] == [c["id"] for c in primero]
    assert all(c["ya_existe"] is True for c in segundo["compromisos"])
    assert all(c["cuando_texto"] for c in segundo["compromisos"])                # con su momento, para repetirlo al usuario
    assert len(_filas(conn)) == len(primero)


def test_crear_compara_el_texto_normalizado(comp, cita, conn):
    creado = comp.crear([{"texto": "Dieta blanda", "evento_id": cita, "dias_inicio": -3, "dias_fin": -1}])["compromisos"][0]
    r = comp.crear([{"texto": "  dieta   BLANDA ", "evento_id": cita, "dias_inicio": -3, "dias_fin": -1}])
    assert r["status"] == "exists" and r["compromisos"][0]["id"] == creado["id"]
    assert len(_filas(conn)) == 1


def test_crear_si_el_otro_esta_hecho_o_cancelado_si_crea(comp, cita, conn):
    a, b = (x["id"] for x in comp.crear([{"texto": "1.ª toma", "evento_id": cita, "dias_inicio": -1, "hora": "21:00"},
                                         {"texto": "2.ª toma", "evento_id": cita, "dias_inicio": 0, "hora": "01:00"}])["compromisos"])
    comp.completar(a)
    comp.borrar(b, "cancelar")
    r = comp.crear([{"texto": "1.ª toma", "evento_id": cita, "dias_inicio": -1, "hora": "21:00"},
                    {"texto": "2.ª toma", "evento_id": cita, "dias_inicio": 0, "hora": "01:00"}])
    assert r["status"] == "created" and not any(c.get("ya_existe") for c in r["compromisos"])
    assert len(_filas(conn)) == 4


def test_crear_otro_evento_si_crea(comp, cal, cita, conn):
    otra = cal.add_event("Endoscopia", date(2027, 1, 20), "09:30")["event_id"]
    comp.crear([{"texto": "Dieta blanda", "evento_id": cita, "dias_inicio": -3}])
    r = comp.crear([{"texto": "Dieta blanda", "evento_id": otra, "dias_inicio": -3}])
    assert r["status"] == "created" and len(_filas(conn)) == 2


def test_crear_otro_usuario_no_cuenta_como_duplicado(conn, comp, cita):
    comp.crear([{"texto": "Dieta blanda", "evento_id": cita, "dias_inicio": -3}])
    # Un evento y un compromiso de otro usuario con el mismo texto no se ven entre sí.
    ajeno = CalendarModule(conn, OTRO).add_event("Endoscopia", date(2026, 12, 17), "09:30")["event_id"]
    r = CompromisosModule(conn, OTRO, reloj=lambda: AHORA).crear(
        [{"texto": "Dieta blanda", "evento_id": ajeno, "dias_inicio": -3}])
    assert r["status"] == "created" and len(_filas(conn, OTRO)) == 1


def test_crear_sin_evento_no_compara_los_sueltos_se_pueden_repetir(comp, conn):
    pan = {"texto": "Comprar pan", "fecha_inicio": "2026-12-10"}
    comp.crear([pan])
    r = comp.crear([{**pan, "fecha_inicio": "2026-12-11"}])
    assert r["status"] == "created" and len(_filas(conn)) == 2


def test_crear_lote_mixto_crea_lo_nuevo_y_marca_lo_que_ya_estaba(comp, cita, conn):
    ya = comp.crear([{"texto": "Dieta blanda", "evento_id": cita, "dias_inicio": -3, "dias_fin": -1}])["compromisos"][0]
    r = comp.crear([{"texto": "Dieta blanda", "evento_id": cita, "dias_inicio": -3, "dias_fin": -1},
                    {"texto": "Llevar el volante", "evento_id": cita, "dias_inicio": -1}])
    assert r["status"] == "created"
    primero, segundo = r["compromisos"]                                          # en el orden en que se pidieron
    assert primero["ya_existe"] is True and primero["id"] == ya["id"]
    assert not segundo.get("ya_existe") and segundo["id"] != ya["id"]
    assert [f["texto"] for f in _filas(conn)] == ["Dieta blanda", "Llevar el volante"]


def test_crear_un_lote_invalido_no_deja_nada_aunque_algo_ya_existiera(comp, cita, conn):
    comp.crear([{"texto": "Dieta blanda", "evento_id": cita, "dias_inicio": -3}])
    r = comp.crear([{"texto": "Dieta blanda", "evento_id": cita, "dias_inicio": -3},
                    {"texto": "Mal", "evento_id": cita}])                         # atado sin cuándo: inválido
    assert r["status"] == "invalid" and len(_filas(conn)) == 1
