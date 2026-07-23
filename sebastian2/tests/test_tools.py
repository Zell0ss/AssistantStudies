"""Tests for ALL_TOOLS definitions."""
import importlib

import pytest

from core.tools import ALL_TOOLS

TOOL_FAMILY_MODULES = [
    "calendar_tools", "weather_tools", "inventory_tools", "list_tools",
    "notes_tools", "clarification_tools", "tasks_tools", "docs_tools", "memory_tools",
]


@pytest.mark.parametrize("module_name", TOOL_FAMILY_MODULES)
def test_tool_family_module_exports_family_summary(module_name):
    module = importlib.import_module(f"core.tools.{module_name}")
    assert isinstance(module.FAMILY_SUMMARY, str)
    assert module.FAMILY_SUMMARY.strip()


def test_build_capabilities_digest_includes_all_family_summaries():
    from core.tools import build_capabilities_digest, _TOOL_FAMILIES
    digest = build_capabilities_digest()
    for _, summary in _TOOL_FAMILIES:
        assert summary in digest


def test_every_tool_in_all_tools_belongs_to_a_summarized_family():
    from core.tools import _TOOL_FAMILIES
    covered = sum(len(tools) for tools, _ in _TOOL_FAMILIES)
    assert covered == len(ALL_TOOLS)


def test_request_clarification_in_all_tools():
    names = [t["name"] for t in ALL_TOOLS]
    assert "request_clarification" in names


def test_request_clarification_schema():
    tool = next(t for t in ALL_TOOLS if t["name"] == "request_clarification")
    props = tool["input_schema"]["properties"]
    assert "question" in props
    assert "missing_field" in props
    assert tool["input_schema"]["required"] == ["question", "missing_field"]
