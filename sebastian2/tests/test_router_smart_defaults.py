# tests/test_router_smart_defaults.py
"""
Tests for router smart defaults functionality.

Smart defaults allow users to omit list names when they only have one list
of a given category. The router auto-selects the list or prompts for clarification.
"""
import pytest
from core.router import ModuleRouter
from modules.item_list import ItemListModule
from db.connection import get_connection, close_connection


@pytest.fixture
def conn():
    """Database connection fixture."""
    connection = get_connection()
    yield connection
    close_connection()


@pytest.fixture
def user_id():
    """Test user ID fixture."""
    return 999999  # Test user


@pytest.fixture
def router(user_id):
    """Router fixture."""
    return ModuleRouter(user_id)


@pytest.fixture
def clean_lists(conn, user_id):
    """Clean up all lists for test user before each test."""
    # Delete all lists for test user
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = %s)", (user_id,))
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    yield
    # Cleanup after test
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = %s)", (user_id,))
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()


def test_smart_default_single_list_auto_selects(conn, user_id, router, clean_lists):
    """
    Test that when user has exactly 1 list of a category,
    it's auto-selected when list_name is not provided.
    """
    # Setup: Create 1 inventory list
    ItemListModule.create_list(conn, user_id, "despensa", "inventory")

    # Add item without specifying list_name
    parsed_intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'arroz',
        'quantity': 2,
        'unit': 'kg',
        'list_name': None  # Not specified
    }

    result = router.route(parsed_intent)

    # Should succeed - auto-selected "despensa"
    assert result['success'] is True
    assert 'arroz' in result['result']

    # Verify item was added to "despensa"
    items = ItemListModule.list_items(conn, user_id, "despensa")
    assert len(items) == 1
    assert items[0]['name'] == 'arroz'


def test_smart_default_multiple_lists_returns_error(conn, user_id, router, clean_lists):
    """
    Test that when user has 2+ lists of a category,
    an error is returned with list options when list_name is not provided.
    """
    # Setup: Create 2 inventory lists
    ItemListModule.create_list(conn, user_id, "despensa", "inventory")
    ItemListModule.create_list(conn, user_id, "nevera", "inventory")

    # Try to add item without specifying list_name
    parsed_intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'arroz',
        'quantity': 2,
        'unit': 'kg',
        'list_name': None  # Not specified
    }

    result = router.route(parsed_intent)

    # Should fail with helpful error
    assert result['success'] is False
    assert '¿A qué lista?' in result['result']
    assert 'despensa' in result['result']
    assert 'nevera' in result['result']


def test_explicit_list_name_bypasses_smart_default(conn, user_id, router, clean_lists):
    """
    Test that when list_name is explicitly provided,
    it's used directly even when user has multiple lists.
    """
    # Setup: Create 2 inventory lists
    ItemListModule.create_list(conn, user_id, "despensa", "inventory")
    ItemListModule.create_list(conn, user_id, "nevera", "inventory")

    # Add item with explicit list_name
    parsed_intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'arroz',
        'quantity': 2,
        'unit': 'kg',
        'list_name': 'nevera'  # Explicit
    }

    result = router.route(parsed_intent)

    # Should succeed - used explicit "nevera"
    assert result['success'] is True
    assert 'arroz' in result['result']

    # Verify item was added to "nevera" (not "despensa")
    items_nevera = ItemListModule.list_items(conn, user_id, "nevera")
    items_despensa = ItemListModule.list_items(conn, user_id, "despensa")

    assert len(items_nevera) == 1
    assert items_nevera[0]['name'] == 'arroz'
    assert len(items_despensa) == 0


def test_smart_default_no_lists_uses_default_name(conn, user_id, router, clean_lists):
    """
    Test that when user has 0 lists of a category,
    default list name is used (inventario, compra, equipaje).
    """
    # Setup: No lists exist

    # Add item without specifying list_name
    parsed_intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'arroz',
        'quantity': 2,
        'unit': 'kg',
        'list_name': None  # Not specified
    }

    result = router.route(parsed_intent)

    # Should succeed - created/used default "inventario"
    assert result['success'] is True
    assert 'arroz' in result['result']

    # Verify list "inventario" was created
    lists = ItemListModule.list_all_lists(conn, user_id, category='inventory')
    assert len(lists) == 1
    assert lists[0]['name'] == 'inventario'

    # Verify item was added
    items = ItemListModule.list_items(conn, user_id, "inventario")
    assert len(items) == 1
    assert items[0]['name'] == 'arroz'
