"""Fase 3 H3c (R7, D54): un turno en el que solo corrieron tools de lectura. Sin API.

D44 vigila los turnos SIN ninguna tool. E10 enseñó el hueco de al lado: el planner busca (`calendar_search_events`), cierra el
turno, y Alfred cuenta como hecho lo que no se hizo («actualizo la cita…»). Si todas las tools del turno son de lectura, a
Alfred se le dice, después del mensaje y de los datos, que no ha cambiado nada."""
from unittest.mock import MagicMock, patch

import pytest

from core.tools import ALL_TOOLS

NOTA_CABECERA = "[En este turno solo has consultado ("
NOTA_COLA = ("): no has guardado, cambiado, borrado, apuntado ni creado nada. Si el usuario pedía un cambio, dile que no lo "
             "has hecho y ofrécete a hacerlo.]")


@pytest.fixture
def db():
    """`_synthesize` no toca la BD: basta una conexión de mentira (el constructor solo la guarda)."""
    return MagicMock()


def _orquestador(mock_anthropic_cls, db):
    cliente = MagicMock()
    mock_anthropic_cls.return_value = cliente
    respuesta = MagicMock()
    respuesta.content = [MagicMock(text="ok")]
    cliente.messages.create.return_value = respuesta
    from core.orchestrator import Orchestrator
    return Orchestrator(db, '99999'), cliente


def _ultimo(cliente):
    return cliente.messages.create.call_args.kwargs["messages"][-1]["content"]


def _resultado(tool, **entrada):
    return {"tool": tool, "input": entrada, "result": {"status": "ok"}}


def test_toda_tool_esta_clasificada_lectura_o_escritura():
    """Una tool nueva sin clasificar haría que un turno de escritura pareciera de lectura (o al revés): esta prueba obliga."""
    from core.orchestrator import _TOOLS_DE_ESCRITURA, _TOOLS_DE_LECTURA
    todas = {t["name"] for t in ALL_TOOLS}
    assert not (_TOOLS_DE_LECTURA & _TOOLS_DE_ESCRITURA), "una tool no puede ser de lectura y de escritura"
    sin_clasificar = todas - _TOOLS_DE_LECTURA - _TOOLS_DE_ESCRITURA
    assert not sin_clasificar, f"clasifica estas tools en core/orchestrator.py: {sorted(sin_clasificar)}"
    inexistentes = (_TOOLS_DE_LECTURA | _TOOLS_DE_ESCRITURA) - todas
    assert not inexistentes, f"clasificadas pero no existen: {sorted(inexistentes)}"


@pytest.mark.parametrize("tool", ["calendar_search_events", "calendar_list_events", "calendar_find_by_datetime",
                                  "search_memory", "compromisos_listar", "notes_search", "tasks_list"])
def test_las_de_lectura_de_verdad_son_de_lectura(tool):
    from core.orchestrator import _TOOLS_DE_LECTURA
    assert tool in _TOOLS_DE_LECTURA


@pytest.mark.parametrize("tool", ["calendar_add_event", "calendar_add_note", "calendar_update_event", "compromisos_crear",
                                  "compromisos_completar", "compromisos_borrar", "mark_as_memorable", "salud", "notes_create"])
def test_las_que_cambian_algo_son_de_escritura(tool):
    from core.orchestrator import _TOOLS_DE_ESCRITURA
    assert tool in _TOOLS_DE_ESCRITURA


@patch('core.orchestrator.Anthropic')
def test_con_solo_una_busqueda_la_nota_esta(mock_anthropic_cls, db):
    orch, cliente = _orquestador(mock_anthropic_cls, db)
    orch._synthesize("Me han cambiado la endoscopia al 29", [_resultado("calendar_search_events", query="endoscopia")], [])

    ultimo = _ultimo(cliente)
    assert NOTA_CABECERA + "calendar_search_events" + NOTA_COLA in ultimo
    # Después del mensaje y de los datos recogidos, no antes
    assert ultimo.index("Me han cambiado la endoscopia al 29") < ultimo.index("Datos recogidos") < ultimo.index(NOTA_CABECERA)


@patch('core.orchestrator.Anthropic')
def test_la_nota_nombra_cada_tool_una_sola_vez_y_en_orden(mock_anthropic_cls, db):
    orch, cliente = _orquestador(mock_anthropic_cls, db)
    orch._synthesize("¿Qué tengo?", [_resultado("calendar_list_events"), _resultado("compromisos_listar"),
                                     _resultado("calendar_list_events")], [])
    assert NOTA_CABECERA + "calendar_list_events, compromisos_listar" + NOTA_COLA in _ultimo(cliente)


@patch('core.orchestrator.Anthropic')
def test_con_una_busqueda_y_una_escritura_no_hay_nota(mock_anthropic_cls, db):
    orch, cliente = _orquestador(mock_anthropic_cls, db)
    orch._synthesize("Apunta que me acompaña Marta",
                     [_resultado("calendar_search_events"), _resultado("calendar_add_note", event_id=1)], [])
    ultimo = _ultimo(cliente)
    assert "solo has consultado" not in ultimo and "no se ha ejecutado ninguna herramienta" not in ultimo


@patch('core.orchestrator.Anthropic')
def test_sin_ninguna_tool_sigue_la_nota_de_d44(mock_anthropic_cls, db):
    from core.orchestrator import _TURNO_SIN_HERRAMIENTAS
    orch, cliente = _orquestador(mock_anthropic_cls, db)
    orch._synthesize("Olvida lo del marisco", [], [])
    ultimo = _ultimo(cliente)
    assert ultimo.rstrip().endswith(_TURNO_SIN_HERRAMIENTAS) and "solo has consultado" not in ultimo


@patch('core.orchestrator.Anthropic')
def test_la_consulta_normal_sigue_respondiendo_con_los_datos(mock_anthropic_cls, db):
    """La nota no cambia lo que Alfred recibe: los datos y la instrucción de responder siguen ahí."""
    orch, cliente = _orquestador(mock_anthropic_cls, db)
    orch._synthesize("¿Qué tengo hoy?", [_resultado("calendar_list_events", time_window="today")], [])
    ultimo = _ultimo(cliente)
    assert "calendar_list_events" in ultimo and "Responde al usuario en español" in ultimo
