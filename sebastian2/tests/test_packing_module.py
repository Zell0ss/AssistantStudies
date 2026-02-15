# tests/test_packing_module.py
import pytest
from modules.packing import PackingListModule
from db.connection import get_connection, close_connection

@pytest.fixture
def packing_module():
    """Fixture to create PackingListModule instance"""
    conn = get_connection()
    user_id = "test_user_packing"
    module = PackingListModule(conn, user_id)

    # Clean up any existing test data
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    conn.commit()

    yield module

    # Cleanup
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    conn.commit()
    close_connection()

def test_add_recurring_item_to_packing_list(packing_module):
    """Test adding recurring item to packing list"""
    packing_module.add("gijón_llevar", "leche", recurring=True)

    items = packing_module.list_items("gijón_llevar")
    assert len(items) == 1
    assert items[0]['name'] == "leche"
    assert items[0]['recurring'] == 1  # True stored as 1 in DB

def test_add_one_time_item_to_packing_list(packing_module):
    """Test adding one-time item to packing list"""
    packing_module.add("gijón_llevar", "toalla", recurring=False)

    items = packing_module.list_items("gijón_llevar")
    assert len(items) == 1
    assert items[0]['name'] == "toalla"
    assert items[0]['recurring'] == 0  # False stored as 0 in DB

def test_check_recurring_item_stays_on_list(packing_module):
    """Test that recurring items stay when checked"""
    packing_module.add("gijón_llevar", "leche", recurring=True)
    packing_module.check("gijón_llevar", "leche")

    # Item should still be in list, just marked checked
    items = packing_module.list_items("gijón_llevar", include_checked=True)
    assert len(items) == 1
    assert items[0]['checked'] == 1
    assert items[0]['recurring'] == 1

def test_check_one_time_item_disappears(packing_module):
    """Test that one-time items disappear when checked"""
    packing_module.add("gijón_llevar", "toalla", recurring=False)
    packing_module.check("gijón_llevar", "toalla")

    # Item should be gone
    items = packing_module.list_items("gijón_llevar", include_checked=True)
    assert len(items) == 0

def test_uncheck_recurring_items_resets_for_next_trip(packing_module):
    """Test uncheck_recurring resets recurring items"""
    packing_module.add("gijón_llevar", "leche", recurring=True)
    packing_module.add("gijón_llevar", "pan", recurring=True)
    packing_module.check("gijón_llevar", "leche")
    packing_module.check("gijón_llevar", "pan")

    # Both checked
    items = packing_module.list_items("gijón_llevar", include_checked=True)
    assert all(item['checked'] == 1 for item in items)

    # Uncheck recurring items
    packing_module.uncheck_recurring("gijón_llevar")

    # Both should be unchecked now
    items = packing_module.list_items("gijón_llevar")
    assert len(items) == 2
    assert all(item['checked'] == 0 for item in items)

def test_list_items_excludes_checked_by_default(packing_module):
    """Test that list_items excludes checked items by default"""
    packing_module.add("gijón_llevar", "leche", recurring=True)
    packing_module.add("gijón_llevar", "toalla", recurring=False)
    packing_module.check("gijón_llevar", "leche")

    # Default should exclude checked
    items = packing_module.list_items("gijón_llevar")
    assert len(items) == 1
    assert items[0]['name'] == "toalla"
