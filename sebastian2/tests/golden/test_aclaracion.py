"""Fase 2 H0 (D28): flujo real de aclaración y reanudación con el planner en Haiku 5.5. [API]

El primer turno provoca `request_clarification`; el segundo responde. En el segundo turno se llama a
_is_plan_reply y al planner con los mensajes guardados en `pending_plans`, que ahora pueden llevar
bloques `thinking` con `signature`. No puede dar un 400 (p. ej. por el chequeo de historial editado de
Haiku 5.5: el prompt del planner lleva la hora, que cambia entre turnos).

Se lanza con: pytest -m golden tests/golden/test_aclaracion.py -s
"""
import pytest

from tests.golden.conftest import GOLDEN_USER_ID

PRIMERA = "Apunta en el calendario una cita"
RESPUESTA = "Mañana a las 10:30, es con el dentista"


@pytest.mark.golden
def test_aclaracion_y_reanudacion_real(orchestrator_runner, test_db):
    cur = test_db.cursor()
    cur.execute("DELETE FROM pending_plans WHERE user_id = %s", (GOLDEN_USER_ID,))
    cur.execute("DELETE FROM events WHERE user_id = %s AND title LIKE %s", (GOLDEN_USER_ID, "%dentista%"))
    test_db.commit()

    # Turno 1: tiene que pedir una aclaración y guardar el plan.
    llamadas1, respuesta1 = orchestrator_runner(PRIMERA)
    print(f"\n[turno 1] tools={llamadas1} | Alfred: {respuesta1['text']}")
    assert "request_clarification" in llamadas1, f"el planner no pidió aclaración: {llamadas1}"

    cur.execute("SELECT messages_json FROM pending_plans WHERE user_id = %s", (GOLDEN_USER_ID,))
    fila = cur.fetchone()
    assert fila, "no se guardó ningún plan pendiente"
    plan_json = fila["messages_json"] if isinstance(fila, dict) else fila[0]
    con_thinking = '"type": "thinking"' in plan_json
    print(f"[plan guardado] contiene bloques thinking: {con_thinking}")

    # Turno 2: la respuesta reanuda el plan (esto es lo que no puede dar un 400).
    llamadas2, respuesta2 = orchestrator_runner(RESPUESTA)
    print(f"[turno 2] tools={llamadas2} | Alfred: {respuesta2['text']}")
    assert respuesta2["text"].strip(), "la reanudación no devolvió texto"
    assert "Error en el servicio" not in respuesta2["text"], respuesta2["text"]

    cur.execute("SELECT COUNT(*) AS n FROM pending_plans WHERE user_id = %s", (GOLDEN_USER_ID,))
    fila = cur.fetchone()
    assert (fila["n"] if isinstance(fila, dict) else fila[0]) == 0, "el plan pendiente no se consumió"

    # Limpieza: lo que haya creado la cita de prueba.
    cur.execute("DELETE FROM events WHERE user_id = %s AND title LIKE %s", (GOLDEN_USER_ID, "%dentista%"))
    test_db.commit()
