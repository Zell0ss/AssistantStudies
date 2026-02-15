# tests/test_shopping_module.py
import pytest
from modules.shopping import ShoppingListModule
from db.connection import get_connection, close_connection

@pytest.fixture
def shopping_module():
    """Fixture to create ShoppingListModule instance"""
    conn = get_connection()
    user_id = "test_user_shopping"
    module = ShoppingListModule(conn, user_id)

    # Clean up any existing test data
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = %s)", (user_id,))
    conn.commit()

    # Create shopping list
    module._ensure_shopping_list()

    yield module

    # Cleanup
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    conn.commit()
    close_connection()

def test_add_to_shopping_list(shopping_module):
    """Test adding item to shopping list"""
    shopping_module.add("aguacates")

    items = shopping_module.list_all()
    assert len(items) == 1
    assert items[0]['name'] == "aguacates"

def test_remove_from_shopping_list(shopping_module):
    """Test removing item from shopping list"""
    shopping_module.add("aguacates")
    shopping_module.add("leche")
    shopping_module.remove("aguacates")

    items = shopping_module.list_all()
    assert len(items) == 1
    assert items[0]['name'] == "leche"

def test_mark_bought_removes_item(shopping_module):
    """Test that marking as bought removes item (disappears)"""
    shopping_module.add("aguacates")
    shopping_module.mark_bought("aguacates")

    items = shopping_module.list_all()
    assert len(items) == 0

def test_list_all_returns_unchecked_only(shopping_module):
    """Test that list_all only returns unchecked items"""
    shopping_module.add("aguacates")
    shopping_module.add("leche")
    shopping_module.mark_bought("aguacates")

    items = shopping_module.list_all()
    assert len(items) == 1
    assert items[0]['name'] == "leche"
