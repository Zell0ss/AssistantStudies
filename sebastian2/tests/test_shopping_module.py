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

def test_multiple_shopping_lists(shopping_module):
    """Test creating and managing multiple shopping lists"""
    # Add to default list (compra)
    shopping_module.add("aguacates")
    shopping_module.add("leche")

    # Add to custom list (mercadona)
    shopping_module.add("vino", "mercadona")
    shopping_module.add("queso", "mercadona")

    # Add to another custom list (carrefour)
    shopping_module.add("pan", "carrefour")

    # Verify each list has correct items
    compra_items = shopping_module.list_all("compra")
    assert len(compra_items) == 2
    assert any(i['name'] == 'aguacates' for i in compra_items)
    assert any(i['name'] == 'leche' for i in compra_items)

    mercadona_items = shopping_module.list_all("mercadona")
    assert len(mercadona_items) == 2
    assert any(i['name'] == 'vino' for i in mercadona_items)
    assert any(i['name'] == 'queso' for i in mercadona_items)

    carrefour_items = shopping_module.list_all("carrefour")
    assert len(carrefour_items) == 1
    assert carrefour_items[0]['name'] == "pan"

def test_list_all_lists(shopping_module):
    """Test listing all shopping lists"""
    # Create multiple lists by adding items
    shopping_module.add("aguacates", "compra")
    shopping_module.add("vino", "mercadona")
    shopping_module.add("pan", "carrefour")

    # Get all lists
    lists = shopping_module.list_all_lists()
    assert len(lists) == 3

    # Verify list names and item counts
    list_names = [l['name'] for l in lists]
    assert "compra" in list_names
    assert "mercadona" in list_names
    assert "carrefour" in list_names

    # Each should have 1 item
    for lst in lists:
        assert lst['item_count'] == 1

def test_remove_from_specific_list(shopping_module):
    """Test removing items from specific lists"""
    # Add same item to different lists
    shopping_module.add("leche", "compra")
    shopping_module.add("leche", "mercadona")

    # Remove from one list
    shopping_module.remove("leche", "compra")

    # Verify removed from compra but still in mercadona
    compra_items = shopping_module.list_all("compra")
    assert len(compra_items) == 0

    mercadona_items = shopping_module.list_all("mercadona")
    assert len(mercadona_items) == 1
    assert mercadona_items[0]['name'] == "leche"
