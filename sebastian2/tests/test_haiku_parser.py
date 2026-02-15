# tests/test_haiku_parser.py
import pytest
from core.haiku_parser import HaikuParser

@pytest.fixture
def parser():
    """Fixture to create HaikuParser instance"""
    return HaikuParser()

def test_haiku_parser_initializes(parser):
    """Test that HaikuParser initializes"""
    assert parser is not None
    assert parser.client is not None

def test_parse_inventory_add(parser):
    """Test parsing inventory add command"""
    result = parser.parse("compré 6 aguacates")

    assert result['module'] == 'inventory'
    assert result['action'] == 'add'
    assert result['item'] == 'aguacates'
    assert result['quantity'] == 6

def test_parse_shopping_list_query(parser):
    """Test parsing shopping list query"""
    result = parser.parse("lista de la compra")

    assert result['module'] == 'shopping'
    assert result['action'] == 'list'

# Note: These tests require actual Anthropic API calls and cost money
# Run with: pytest tests/test_haiku_parser.py -v -s
