"""Golden regression suite for the Orchestrator's agentic loop.

Validates TOOL-CALL SEQUENCE against real Anthropic API calls (Haiku planner +
ToolExecutor dispatch), not response text. Real cost, real DB (sebastian_test
only — see conftest.py guardrail). Excluded from the default `pytest` run by
pytest.ini (`addopts = -m "not golden"`); run explicitly with:

    pytest -m golden -v -s
"""
from collections import Counter
from pathlib import Path

import pytest
import yaml

from tests.golden.criterios import MODOS as MODOS_DE_COMPROMISO, evaluar_calendario, evaluar_compromiso

GOLDENS_PATH = Path(__file__).parent / "goldens.yaml"
GOLDENS = yaml.safe_load(GOLDENS_PATH.read_text())

# Populated as tests run; printed as a readable report by the
# pytest_terminal_summary hook in conftest.py.
GOLDEN_RESULTS = []


def _matches(actual: list, mode: str, expected) -> bool:
    if mode in MODOS_DE_COMPROMISO:                  # H7: se juzga en `evaluar_compromiso`, con lo que se creó
        raise ValueError(f"el modo {mode!r} se evalúa con criterios.evaluar_compromiso")
    if mode == "exact":
        return actual == expected
    if mode == "multiset":
        return Counter(actual) == Counter(expected)
    if mode == "any_of":
        return any(actual == alt for alt in expected)
    if mode == "none":
        return actual == []
    raise ValueError(f"unknown golden mode: {mode!r}")


def _fmt_sequence(seq: list) -> str:
    return " → ".join(seq) if seq else "(ninguna)"


def _fmt_expected(mode: str, expected) -> str:
    if mode == "any_of":
        return "  O  ".join(_fmt_sequence(alt) for alt in expected)
    return _fmt_sequence(expected)


@pytest.mark.golden
@pytest.mark.parametrize("golden", GOLDENS, ids=[f"golden_{g['id']:02d}" for g in GOLDENS])
def test_golden(golden, orchestrator_runner):
    actual, response = orchestrator_runner(golden["phrase"], golden.get("historia"), estado=golden.get("estado"),
                                           ahora=golden.get("ahora"))
    response_text = response.get("text", "") if isinstance(response, dict) else str(response)
    esperado = golden.get("expected", golden.get("expected_any"))   # #85 trae `expected_any` (varias lecturas valen)
    if golden["mode"] == "calendario":
        entradas = response.get("entradas_calendario", {}) if isinstance(response, dict) else {}
        passed = evaluar_calendario(golden, actual, entradas, response_text)
    elif golden["mode"] in MODOS_DE_COMPROMISO:
        creaciones = response.get("creaciones", []) if isinstance(response, dict) else []
        passed = evaluar_compromiso(golden, actual, creaciones, response_text)
    else:
        passed = _matches(actual, golden["mode"], golden["expected"])

    GOLDEN_RESULTS.append({
        "id": golden["id"],
        "phrase": golden["phrase"],
        "mode": golden["mode"],
        "expected": _fmt_expected(golden["mode"], esperado) if "expected" in golden else f"cualquiera de: {', '.join(esperado)}",
        "actual": _fmt_sequence(actual),
        "passed": passed,
        "validates": golden.get("validates", ""),
        "response_text": response_text,
        "planner_sin_tools": response.get("planner_sin_tools", []) if isinstance(response, dict) else [],
        "ventanas": response.get("ventanas", []) if isinstance(response, dict) else [],
        "creaciones": response.get("creaciones", []) if isinstance(response, dict) else [],
        "entradas_calendario": response.get("entradas_calendario", {}) if isinstance(response, dict) else {},
    })

    assert passed, (
        f"Golden #{golden['id']} ({golden['mode']}) — "
        f"esperado {esperado!r}, real {actual!r}. "
        f"Respuesta de Alfred: {response_text!r}"
    )
