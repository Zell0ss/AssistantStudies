"""
Tests for HaikuParser list name extraction.

Task 9: Verify parser can extract list names from natural language.
"""

import pytest
from core.haiku_parser import HaikuParser


@pytest.fixture
def parser():
    """Create parser instance for testing."""
    return HaikuParser()


def test_extract_inventory_list_name(parser):
    """Parser should extract inventory list name from natural language."""
    result = parser.parse("añade aguacates a despensa de madrid")

    assert result["module"] == "inventory"
    assert result["action"] == "add"
    assert result["item"] == "aguacates"
    assert result["list_name"] is not None
    # Allow flexibility: should contain "despensa" or "madrid"
    list_name_lower = result["list_name"].lower()
    assert "despensa" in list_name_lower or "madrid" in list_name_lower


def test_extract_shopping_list_name(parser):
    """Parser should extract shopping list name from natural language."""
    result = parser.parse("añade pan a mercadona")

    assert result["module"] == "shopping"
    assert result["action"] == "add"
    assert result["item"] == "pan"
    assert result["list_name"] is not None
    assert "mercadona" in result["list_name"].lower()


def test_default_compra_for_shopping(parser):
    """Parser should use 'compra' as list name when user says 'la compra'."""
    result = parser.parse("añade leche a la compra")

    assert result["module"] == "shopping"
    assert result["action"] == "add"
    assert result["item"] == "leche"
    assert result["list_name"] is not None
    assert "compra" in result["list_name"].lower()


def test_no_list_name_returns_null(parser):
    """Parser should return null list_name when not specified."""
    result = parser.parse("qué tengo en mi inventario")

    assert result["module"] == "inventory"
    assert result["action"] == "list"
    assert result["list_name"] is None


def test_extract_quantity_with_list_name(parser):
    """Parser should extract both quantity and list name."""
    result = parser.parse("añade 3 kg de arroz a despensa madrid")

    assert result["module"] == "inventory"
    assert result["action"] == "add"
    assert result["item"] == "arroz"
    assert result["quantity"] == 3
    assert result["unit"] == "kg"
    assert result["list_name"] is not None
    # Should contain "despensa" or "madrid"
    list_name_lower = result["list_name"].lower()
    assert "despensa" in list_name_lower or "madrid" in list_name_lower
