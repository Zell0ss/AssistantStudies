"""Tests for ALL_TOOLS definitions."""
from core.tools import ALL_TOOLS


def test_request_clarification_in_all_tools():
    names = [t["name"] for t in ALL_TOOLS]
    assert "request_clarification" in names


def test_request_clarification_schema():
    tool = next(t for t in ALL_TOOLS if t["name"] == "request_clarification")
    props = tool["input_schema"]["properties"]
    assert "question" in props
    assert "missing_field" in props
    assert tool["input_schema"]["required"] == ["question", "missing_field"]
