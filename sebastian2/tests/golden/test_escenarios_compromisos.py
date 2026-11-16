"""Fase 3 H3 (plan §3 H3.2): escenario E10 de punta a punta, la preparación de una prueba médica. [API]

Usa el `Orchestrator` real (planner Haiku, síntesis de Alfred) contra `sebastian_test` y comprueba **la BD y el
texto del resumen**, no lo que diga Alfred. Datos inventados (Josem, 2026-11-16): endoscopia, dieta blanda, Marta,
Hospital Ejemplo, test de la gota seca. Nada va a Telegram: `armar_resumen` es una función pura sobre la BD.

Pasa si pasa 3 de 3 (PLAN §3 H3.2). Se lanza con:
    pytest -m golden tests/golden/test_escenarios_compromisos.py -s
"""
import json
from datetime import datetime
from unittest.mock import patch

import pytest

from bot.scheduler import armar_resumen
from core.tool_executor import ToolExecutor
from tests.golden.memoria_base import USUARIO_B, exigir_bd_de_test
from tests.golden.test_escenarios_memoria import _correr, _registrar

CITA = "Tengo la endoscopia el jueves 28 de enero a las 9:30"
PREPARACION = ("Para la endoscopia: empiezo la dieta blanda tres días antes y la mantengo hasta la víspera; "
               "la víspera a las 21:00 la primera toma del preparado y el mismo día a la una de la madrugada la segunda")
LUGAR = "En la endoscopia me acompaña Marta y es en la planta baja del Hospital Ejemplo"
RESULTADO = "El test de la gota seca me salió positivo"
CAMBIO = "Me han cambiado la endoscopia al 29 a la misma hora"

# El planner ve la fecha real de hoy (2026-11-16): «28 de enero» es el jueves 2027-01-28.
DIA_CITA = datetime(2027, 1, 28)
DIA_NUEVO = datetime(2027, 1, 29)
MENOS_3_NUEVO = datetime(2027, 1, 26, 8, 0)    # tres días antes del 29
MENOS_3_VIEJO = datetime(2027, 1, 25, 8, 0)    # tres días antes del 28, que ya no es la cita


def _limpiar_agenda(db):
    """Compromisos primero (la FK a events no lleva ON DELETE) y luego los eventos del usuario B. E10 va con el usuario B
    y no con el de goldens: este comparte agenda con la fixture de sesión («teatro»), y `_historial_limpio` ya limpia
    la conversación y la memoria del B."""
    exigir_bd_de_test(db)
    cur = db.cursor()
    cur.execute("DELETE FROM compromisos WHERE user_id = %s", (USUARIO_B,))
    cur.execute("DELETE FROM events WHERE user_id = %s", (USUARIO_B,))
    db.commit()


@pytest.fixture
def agenda_limpia(test_db):
    _limpiar_agenda(test_db)
    yield
    _limpiar_agenda(test_db)


def _eventos(db):
    db.commit()   # REPEATABLE READ: sin esto no se ve lo que confirmó la conexión del orquestador
    cur = db.cursor()
    cur.execute("SELECT id, title, event_date, start_datetime, notes FROM events WHERE user_id = %s", (USUARIO_B,))
    return cur.fetchall()


def _compromisos(db):
    db.commit()
    cur = db.cursor()
    cur.execute("SELECT id, texto, evento_id, fecha_inicio, dias_inicio, dias_fin, hora, minutos, estado "
                "FROM compromisos WHERE user_id = %s ORDER BY id", (USUARIO_B,))
    return cur.fetchall()


def _dia(ev):
    return ev["start_datetime"].date() if ev["start_datetime"] else ev["event_date"]


def _bd(eventos, compromisos):
    lineas = [f"events #{e['id']} · {e['title']!r} · {e['start_datetime'] or e['event_date']} · notas={e['notes']!r}"
              for e in eventos]
    lineas += [f"compromisos #{c['id']} · {c['texto']!r} · evento={c['evento_id']} · fecha={c['fecha_inicio']} · "
               f"dias={c['dias_inicio']}..{c['dias_fin']} · hora={c['hora']} · min={c['minutos']} · {c['estado']}"
               for c in compromisos]
    return lineas


def _filas_con_gota(db):
    """Dónde podría haber acabado el resultado del test: memoria, compromisos y notas del evento."""
    db.commit()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM mem_fuentes WHERE user_id = %s AND (texto LIKE %s OR mensaje LIKE %s)",
                (USUARIO_B, "%gota%", "%gota%"))
    en_memoria = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM mem_hechos WHERE user_id = %s AND (valor LIKE %s OR valor LIKE %s)",
                (USUARIO_B, "%gota%", "%positivo%"))
    en_hechos = cur.fetchone()["n"]
    en_compromisos = [c for c in _compromisos(db) if "gota" in c["texto"].lower()]
    en_notas = [e for e in _eventos(db) if e["notes"] and "gota" in json.dumps(e["notes"], ensure_ascii=False).lower()]
    return en_memoria, en_hechos, en_compromisos, en_notas


@pytest.mark.golden
def test_E10_preparacion_de_una_prueba_medica(escenario_runner, test_db, agenda_limpia):
    # H3b (H3-revision §4): se anotan las entradas de cada tool para ver si el `calendar_update_event` del turno 5 lleva
    # `event_id` (R2). Es informativo: no hace fallar la prueba.
    llamadas, original = [], ToolExecutor.execute

    def registrando(self, nombre, entrada):
        llamadas.append((nombre, dict(entrada)))
        return original(self, nombre, entrada)

    turnos, por_turno = [], []
    with patch.object(ToolExecutor, "execute", registrando):
        for frase in (CITA, PREPARACION, LUGAR, RESULTADO, CAMBIO):
            antes = len(llamadas)
            turnos += _correr(escenario_runner, [frase], user_id=USUARIO_B)
            por_turno.append(llamadas[antes:])
    eventos, compromisos = _eventos(test_db), _compromisos(test_db)
    cambios = [entrada for nombre, entrada in por_turno[4] if nombre == "calendar_update_event"]
    if not cambios:
        r2 = "turno 5: ninguna llamada a calendar_update_event"
    else:
        r2 = "turno 5: calendar_update_event " + ("CON event_id" if all("event_id" in c for c in cambios) else
                                                  "SIN event_id") + f" ({len(cambios)} llamada(s))"
    _registrar("E10", "Preparación de una endoscopia (cita, pasos atados, lugar, resultado, cambio de día)", turnos,
               _bd(eventos, compromisos) + [r2])

    # 1. La cita se creó una sola vez, el jueves 28 a las 9:30, y luego se movió al 29 a la misma hora.
    assert len(eventos) == 1, f"se esperaba 1 evento (la endoscopia), hay {len(eventos)}"
    ev = eventos[0]
    assert ev["start_datetime"] == datetime(2027, 1, 29, 9, 30), \
        f"la cita debía acabar el 29/01/2027 a las 9:30, está en {ev['start_datetime'] or ev['event_date']}"

    # 2. Los pasos de la preparación son compromisos pendientes ATADOS al evento (D50), no con fechas sueltas.
    pendientes = [c for c in compromisos if c["estado"] == "pendiente"]
    assert len(pendientes) >= 3, f"se esperaban al menos 3 compromisos pendientes: {_bd([], compromisos)}"
    sueltos = [c for c in pendientes if c["evento_id"] is None]
    assert not sueltos, f"compromisos sin evento_id (D50 no se cumple): {_bd([], sueltos)}"
    assert all(c["evento_id"] == ev["id"] for c in pendientes)
    assert any("dieta" in c["texto"].lower() for c in pendientes), "no hay ningún compromiso de la dieta"

    # 3. El lugar y el acompañante acabaron en la nota del evento, no en memoria.
    notas = json.dumps(ev["notes"], ensure_ascii=False).lower() if ev["notes"] else ""
    assert "marta" in notas or "hospital ejemplo" in notas, f"el lugar y el acompañante no están en la nota: {ev['notes']!r}"

    # 4. El resultado del test no se guardó en ninguna parte (D52).
    en_memoria, en_hechos, en_compromisos, en_notas = _filas_con_gota(test_db)
    assert en_memoria == 0 and en_hechos == 0, "el resultado del test llegó a la memoria"
    assert not en_compromisos and not en_notas, "el resultado del test llegó a un compromiso o a la nota del evento"

    # 5. Con la cita movida, los compromisos siguen siendo los mismos (no se recrearon) y se mueven con ella.
    #    Tres días antes del 29 (el 26) la dieta aparece en el resumen; tres días antes del 28 (el 25), no.
    conn = test_db
    resumen_nuevo = armar_resumen(USUARIO_B, MENOS_3_NUEVO, conn=conn)
    resumen_viejo = armar_resumen(USUARIO_B, MENOS_3_VIEJO, conn=conn)
    RESULTADOS_RESUMEN = [f"resumen del 26/01 (día −3 de la fecha nueva): {resumen_nuevo!r}",
                          f"resumen del 25/01 (día −3 de la fecha vieja): {resumen_viejo!r}"]
    _registrar("E10b", "Resúmenes tras el cambio de día", [], RESULTADOS_RESUMEN)
    assert resumen_nuevo and "dieta" in resumen_nuevo.lower(), f"el resumen del día −3 nuevo no trae la dieta: {resumen_nuevo!r}"
    assert not resumen_viejo or "dieta" not in resumen_viejo.lower(), \
        f"el resumen del día −3 viejo todavía trae la dieta: {resumen_viejo!r}"
