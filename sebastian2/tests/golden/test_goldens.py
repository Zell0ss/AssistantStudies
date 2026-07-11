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

GOLDENS_PATH = Path(__file__).parent / "goldens.yaml"
GOLDENS = yaml.safe_load(GOLDENS_PATH.read_text())

# Populated as tests run; printed as a readable report by the
# pytest_terminal_summary hook in conftest.py.
GOLDEN_RESULTS = []


def _matches(actual: list, mode: str, expected) -> bool:
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
    actual, response = orchestrator_runner(golden["phrase"])
    passed = _matches(actual, golden["mode"], golden["expected"])
    response_text = response.get("text", "") if isinstance(response, dict) else str(response)

    GOLDEN_RESULTS.append({
        "id": golden["id"],
        "phrase": golden["phrase"],
        "mode": golden["mode"],
        "expected": _fmt_expected(golden["mode"], golden["expected"]),
        "actual": _fmt_sequence(actual),
        "passed": passed,
        "validates": golden.get("validates", ""),
        "response_text": response_text,
    })

    assert passed, (
        f"Golden #{golden['id']} ({golden['mode']}) — "
        f"esperado {golden['expected']!r}, real {actual!r}. "
        f"Respuesta de Alfred: {response_text!r}"
    )
