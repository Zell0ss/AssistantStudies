# tests/test_router.py
import pytest
from core.router import ModuleRouter
from db.connection import get_connection, close_connection

@pytest.fixture
def router():
    """Fixture to create ModuleRouter instance"""
    user_id = "test_user_router"
    r = ModuleRouter(user_id)

    # Clean up test data
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM notes WHERE user_id = %s", (user_id,))
    conn.commit()

    yield r

    # Cleanup
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM notes WHERE user_id = %s", (user_id,))
    conn.commit()
    r.cleanup()

def test_router_inventory_add(router):
    """Test routing inventory add action"""
    intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'test_item',
        'quantity': 5,
        'unit': 'unidades'
    }
    result = router.route(intent)
    assert result['success'] is True
    assert 'Añadido' in result['result']

def test_router_shopping_list(router):
    """Test routing shopping list query"""
    intent = {
        'module': 'shopping',
        'action': 'list'
    }
    result = router.route(intent)
    assert result['success'] is True

def test_router_unknown_module(router):
    """Test unknown module handling"""
    intent = {
        'module': 'unknown',
        'action': 'unknown'
    }
    result = router.route(intent)
    assert result['success'] is False
