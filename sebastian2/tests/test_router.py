# tests/test_router.py
import pytest
from core.router import ModuleRouter
from db.connection import get_connection, close_connection

@pytest.fixture
def router():
    """Fixture to create ModuleRouter instance"""
    user_id = "test_user_router"
    r = ModuleRouter(user_id)

    # Clean up test data - use new unified schema
    conn = get_connection()
    cursor = conn.cursor()
    # Delete list items first (foreign key constraint)
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = %s)", (user_id,))
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM notes WHERE user_id = %s", (user_id,))
    conn.commit()

    yield r

    # Cleanup
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = %s)", (user_id,))
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
        'unit': 'kg',
        'threshold': 2
    }
    result = router.route(intent)
    assert result['success'] is True
    assert 'test_item' in result['result']

def test_router_inventory_list(router):
    """Test inventory list action"""
    # Add an item first
    router.route({
        'module': 'inventory',
        'action': 'add',
        'item': 'manzanas',
        'quantity': 10,
        'unit': 'kg'
    })

    # List items
    intent = {'module': 'inventory', 'action': 'list'}
    result = router.route(intent)
    assert result['success'] is True
    assert 'manzanas' in result['result']
    assert '10' in result['result']

def test_router_inventory_get(router):
    """Test inventory get action"""
    # Add an item first
    router.route({
        'module': 'inventory',
        'action': 'add',
        'item': 'tomates',
        'quantity': 5,
        'unit': 'kg'
    })

    # Get item
    intent = {'module': 'inventory', 'action': 'get', 'item': 'tomates'}
    result = router.route(intent)
    assert result['success'] is True
    assert 'tomates' in result['result']
    assert '5' in result['result']

def test_router_inventory_check_low_stock(router):
    """Test inventory check_low_stock action"""
    # Add item with low quantity
    router.route({
        'module': 'inventory',
        'action': 'add',
        'item': 'sal',
        'quantity': 1,
        'unit': 'kg',
        'threshold': 5
    })

    # Check low stock
    intent = {'module': 'inventory', 'action': 'check_low_stock'}
    result = router.route(intent)
    assert result['success'] is True
    # Should show low stock warning
    assert 'sal' in result['result'] or 'Todo bien' in result['result']

def test_router_shopping_add(router):
    """Test shopping add action"""
    intent = {
        'module': 'shopping',
        'action': 'add',
        'item': 'leche',
        'quantity': 2,
        'unit': 'litros'
    }
    result = router.route(intent)
    assert result['success'] is True
    assert 'leche' in result['result']

def test_router_shopping_list(router):
    """Test routing shopping list query"""
    # Add item first
    router.route({
        'module': 'shopping',
        'action': 'add',
        'item': 'pan',
        'quantity': 1,
        'unit': 'unidades'
    })

    intent = {'module': 'shopping', 'action': 'list'}
    result = router.route(intent)
    assert result['success'] is True
    assert 'pan' in result['result']

def test_router_shopping_remove(router):
    """Test shopping remove action"""
    # Add item first
    router.route({
        'module': 'shopping',
        'action': 'add',
        'item': 'huevos',
        'quantity': 12,
        'unit': 'unidades'
    })

    # Remove item
    intent = {'module': 'shopping', 'action': 'remove', 'item': 'huevos'}
    result = router.route(intent)
    assert result['success'] is True

def test_router_packing_add(router):
    """Test packing add action"""
    intent = {
        'module': 'packing',
        'action': 'add',
        'item': 'cepillo',
        'quantity': 1,
        'unit': 'unidades',
        'recurring': True
    }
    result = router.route(intent)
    assert result['success'] is True
    assert 'cepillo' in result['result']

def test_router_packing_list(router):
    """Test packing list action with recurring items"""
    # Add recurring item
    router.route({
        'module': 'packing',
        'action': 'add',
        'item': 'cargador',
        'quantity': 1,
        'unit': 'unidades',
        'recurring': True
    })

    # List items
    intent = {'module': 'packing', 'action': 'list'}
    result = router.route(intent)
    assert result['success'] is True
    assert 'cargador' in result['result']
    assert '🔄' in result['result']  # Should show recurring emoji

def test_router_packing_check(router):
    """Test packing check action"""
    # Add item
    router.route({
        'module': 'packing',
        'action': 'add',
        'item': 'libro',
        'quantity': 1,
        'unit': 'unidades',
        'recurring': False
    })

    # Check item (should remove it)
    intent = {'module': 'packing', 'action': 'check', 'item': 'libro'}
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
