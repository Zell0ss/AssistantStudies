"""Fase 4, H1k (D59, R26-R27): el log de fin de turno reparte el uso por papel (planner, extractor, alfred, otro). Clientes falsos: sin API."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.test_orchestrator import db, _make_text_response, _make_tool_use_response  # noqa: F401  (`db` es una fixture)

MARCA = "ZZUSO"


@pytest.fixture(autouse=True)
def _sin_indice_de_memoria():
    with patch("core.orchestrator.indice_memoria", return_value=""):
        yield


def _con_uso(respuesta, entrada, salida, cr=0, cc=0):
    respuesta.usage = SimpleNamespace(input_tokens=entrada, output_tokens=salida,
                                      cache_read_input_tokens=cr, cache_creation_input_tokens=cc)
    return respuesta


def _lineas(mock_logger):
    """Los textos de todas las líneas INFO que dejó el orquestador (sea `logger.info` o `logger.bind(...).info`)."""
    llamadas = list(mock_logger.info.call_args_list) + list(mock_logger.bind.return_value.info.call_args_list)
    return [c.args[0] for c in llamadas]


def _turno_completo(db, mensaje="Recuerda que mi color favorito es el verde"):
    """planner → mark_as_memorable → extractor (su uso llega por `on_usage`) → planner cierra → Alfred."""
    from core.orchestrator import Orchestrator
    with patch("core.orchestrator.Anthropic") as anthropic, patch("core.orchestrator.logger") as log:
        anthropic.return_value.messages.create.side_effect = [
            _con_uso(_make_tool_use_response("mark_as_memorable", "t1", {"texto": "Mi color favorito es el verde"}),
                     100, 20, cr=5000),
            _con_uso(_make_text_response("ya está"), 10, 5, cr=5100),
            _con_uso(_make_text_response("Anotado, señor."), 900, 60)]
        orch = Orchestrator(db, "99999", config={"anthropic_apikey": "sk-falsa"})

        def ejecutar(nombre, entrada):
            # lo que hace el extractor real dentro de la tool: informar de su uso por `on_usage`
            orch._executor._informar_uso(_con_uso(MagicMock(), 300, 40), "claude-haiku-4-5-20251001")
            return {"guardados": []}
        orch._executor.execute = ejecutar
        resultado = orch.handle(mensaje)
    return resultado, orch, log


def test_h1k_1_un_turno_completo_saca_turn_uso_con_los_tres_papeles_y_las_sumas_cuadran(db):
    resultado, orch, log = _turno_completo(db)
    assert resultado["text"] == "Anotado, señor."
    (uso,) = [l for l in _lineas(log) if l.startswith("Turn uso")]
    assert uso == "Turn uso | user=99999 | planner=110/25/10100/0 | extractor=300/40/0/0 | alfred=900/60/0/0"
    (fin,) = [l for l in _lineas(log) if l.startswith("Turn end")]
    assert "tokens_in=1310 | tokens_out=125 | cache_read=10100 | cache_creation=0" in fin
    por_papel = orch._turn_usage["por_papel"]
    assert sum(p["in"] for p in por_papel.values()) == 1310 and sum(p["out"] for p in por_papel.values()) == 125
    assert sum(p["cr"] for p in por_papel.values()) == 10100 and sum(p["cc"] for p in por_papel.values()) == 0
    # los mismos datos, en `bind`, como `uso_por_papel`
    campos = [c.kwargs for c in log.bind.call_args_list if "uso_por_papel" in c.kwargs]
    assert campos == [{"user_id": "99999", "uso_por_papel": {
        "planner": {"in": 110, "out": 25, "cr": 10100, "cc": 0},
        "extractor": {"in": 300, "out": 40, "cr": 0, "cc": 0},
        "alfred": {"in": 900, "out": 60, "cr": 0, "cc": 0}}}]


def test_h1k_2_un_turno_sin_tools_solo_tiene_planner_y_alfred(db):
    from core.orchestrator import Orchestrator
    with patch("core.orchestrator.Anthropic") as anthropic, patch("core.orchestrator.logger") as log:
        anthropic.return_value.messages.create.side_effect = [
            _con_uso(_make_text_response("sin herramientas"), 50, 7, cr=4000, cc=200),
            _con_uso(_make_text_response("Buenos días, señor."), 600, 30)]
        Orchestrator(db, "99999", config={"anthropic_apikey": "sk-falsa"}).handle("Hola")
    (uso,) = [l for l in _lineas(log) if l.startswith("Turn uso")]
    assert uso == "Turn uso | user=99999 | planner=50/7/4000/200 | alfred=600/30/0/0"
    assert "extractor" not in uso and "otro" not in uso


def test_h1k_3_turn_end_sale_exactamente_igual_y_su_bind_no_gana_campos(db):
    _, _, log = _turno_completo(db)
    (fin,) = [l for l in _lineas(log) if l.startswith("Turn end")]
    assert fin.startswith("Turn end | user=99999 | outcome=completed | iterations=2 | models=") and "uso" not in fin
    assert fin.endswith(f"| latency_ms={fin.rsplit('latency_ms=', 1)[1]}")
    bind_fin = next(c.kwargs for c in log.bind.call_args_list if "outcome" in c.kwargs)
    assert set(bind_fin) == {"user_id", "iterations", "models", "tokens_in", "tokens_out", "cache_read", "cache_creation",
                             "latency_ms", "outcome"}
    assert log.bind.call_args_list[-1].kwargs == bind_fin                        # el último `bind` sigue siendo el de `Turn end`
    textos = _lineas(log)
    assert textos.index(next(l for l in textos if l.startswith("Turn end"))) < textos.index(
        next(l for l in textos if l.startswith("Turn uso")))                     # `Turn uso` va detrás


def test_h1k_4_ningun_contenido_en_el_log_con_una_marca(db):
    resultado, _, log = _turno_completo(db, mensaje=f"Recuerda que mi clave es {MARCA}")
    assert resultado["text"] == "Anotado, señor."
    llamadas = [str(c) for c in log.mock_calls]
    assert any("Turn uso" in l for l in llamadas) and not any(MARCA in l for l in llamadas)


def test_h1k_papel_por_defecto_otro_orden_fijo_y_papeles_desconocidos_cuentan_como_otro(db):
    from core.orchestrator import Orchestrator
    with patch("core.orchestrator.Anthropic"):
        orch = Orchestrator(db, "99999", config={"anthropic_apikey": "sk-falsa"})
    orch._track_usage(_con_uso(MagicMock(), 1, 2), "claude-haiku-4-5-20251001")                  # sin papel: «otro»
    orch._track_usage(_con_uso(MagicMock(), 3, 4), "claude-haiku-4-5-20251001", "rarisimo")       # desconocido: «otro»
    orch._track_usage(_con_uso(MagicMock(), 5, 6, cr=7, cc=8), "claude-sonnet-4-6", "alfred")
    orch._track_usage(MagicMock(usage=None), "claude-haiku-4-5-20251001", "planner")             # una llamada sin `usage` también cuenta
    assert orch._turn_usage["por_papel"] == {"otro": {"in": 4, "out": 6, "cr": 0, "cc": 0},
                                             "alfred": {"in": 5, "out": 6, "cr": 7, "cc": 8},
                                             "planner": {"in": 0, "out": 0, "cr": 0, "cc": 0}}
    assert orch._turn_usage["tokens_in"] == 9 and orch._turn_usage["cache_read"] == 7           # los totales de siempre


def test_h1k_la_llamada_si_no_de_un_plan_pendiente_es_otro(db):
    from core.orchestrator import Orchestrator
    with patch("core.orchestrator.Anthropic") as anthropic:
        anthropic.return_value.messages.create.return_value = _con_uso(_make_text_response("SI"), 30, 1)
        orch = Orchestrator(db, "99999", config={"anthropic_apikey": "sk-falsa"})
        orch._is_plan_reply("sí, el jueves", "¿Qué día?")
    assert orch._turn_usage["por_papel"] == {"otro": {"in": 30, "out": 1, "cr": 0, "cc": 0}}


def test_h1k_cada_turno_empieza_con_el_reparto_vacio(db):
    _, orch, _ = _turno_completo(db)
    assert set(orch._turn_usage["por_papel"]) == {"planner", "extractor", "alfred"}
    from core.orchestrator import _uso_vacio
    assert _uso_vacio()["por_papel"] == {}
