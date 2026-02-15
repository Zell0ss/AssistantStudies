# tests/test_formatter.py
"""Tests for ResponseFormatter class."""

import pytest
from pathlib import Path
from bot.formatter import ResponseFormatter


@pytest.fixture
def formatter():
    """Fixture to create ResponseFormatter instance."""
    return ResponseFormatter()


def test_format_success_returns_confident(formatter):
    """Test successful add/update returns confident sprite."""
    router_result = {
        "success": True,
        "result": "Vale, ahora tienes 8 aguacates 🥑",
        "data": {"item": "aguacates", "quantity": 8}
    }
    context = {"module": "inventory", "action": "add"}

    response = formatter.format_response(router_result, context)

    assert "sprite_path" in response
    assert "confident" in response["sprite_path"] or "triumphant" in response["sprite_path"]
    assert response["caption"] == "Vale, ahora tienes 8 aguacates 🥑"


def test_format_error_returns_confused(formatter):
    """Test error returns confused or apologetic sprite."""
    router_result = {
        "success": False,
        "error": "no_comprendo",
        "result": "No entendí tu mensaje. ¿Podrías reformularlo?"
    }
    context = {"module": "unknown", "action": "unknown"}

    response = formatter.format_response(router_result, context)

    assert "sprite_path" in response
    assert "confused" in response["sprite_path"] or "apologetic" in response["sprite_path"]
    assert response["caption"] == "No entendí tu mensaje. ¿Podrías reformularlo?"


def test_format_low_stock_returns_concerned(formatter):
    """Test low stock warning returns concerned sprite."""
    router_result = {
        "success": True,
        "result": "Tienes 2 huevos (quedan pocos)",
        "data": {"item": "huevos", "quantity": 2}
    }
    context = {"module": "inventory", "action": "query", "low_stock": True}

    response = formatter.format_response(router_result, context)

    assert "sprite_path" in response
    assert "concerned" in response["sprite_path"]
    assert response["caption"] == "Tienes 2 huevos (quedan pocos)"


def test_format_empty_list_returns_apologetic(formatter):
    """Test empty list query returns apologetic or deadpan sprite."""
    router_result = {
        "success": True,
        "result": "Tu lista de la compra está vacía",
        "data": {}
    }
    context = {"module": "shopping", "action": "list", "empty": True}

    response = formatter.format_response(router_result, context)

    assert "sprite_path" in response
    assert "apologetic" in response["sprite_path"] or "deadpan" in response["sprite_path"]
    assert response["caption"] == "Tu lista de la compra está vacía"


def test_format_query_returns_neutral(formatter):
    """Test query/list action returns neutral sprite."""
    router_result = {
        "success": True,
        "result": "Artículos en el inventario:\n• 5 aguacates",
        "data": {"items": [{"name": "aguacates", "quantity": 5}]}
    }
    context = {"module": "inventory", "action": "list"}

    response = formatter.format_response(router_result, context)

    assert "sprite_path" in response
    assert "neutral" in response["sprite_path"]
    assert response["caption"] == "Artículos en el inventario:\n• 5 aguacates"


def test_response_includes_sprite_path(formatter):
    """Test response includes absolute sprite path."""
    router_result = {
        "success": True,
        "result": "Test message",
        "data": {}
    }
    context = {"module": "inventory", "action": "add"}

    response = formatter.format_response(router_result, context)

    assert "sprite_path" in response
    assert isinstance(response["sprite_path"], str)
    # Should be an absolute path
    assert response["sprite_path"].startswith("/")
    # Should point to sprites directory
    assert "sprites" in response["sprite_path"]
    # Should be a WebP file
    assert response["sprite_path"].endswith(".webp")


def test_response_includes_caption(formatter):
    """Test response includes caption text from router."""
    router_result = {
        "success": True,
        "result": "Este es el mensaje de prueba",
        "data": {}
    }
    context = {"module": "notes", "action": "add"}

    response = formatter.format_response(router_result, context)

    assert "caption" in response
    assert response["caption"] == "Este es el mensaje de prueba"
