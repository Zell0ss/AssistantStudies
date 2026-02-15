# tests/test_inventory_module.py
import pytest
from modules.inventory import InventoryModule
from db.connection import get_connection, close_connection

@pytest.fixture
def inventory_module():
    """Fixture to create InventoryModule instance"""
    conn = get_connection()
    user_id = "test_user_inventory"
    module = InventoryModule(conn, user_id)

    # Clean up any existing test data
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE user_id = %s", (user_id,))
    conn.commit()

    yield module

    # Cleanup after test
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE user_id = %s", (user_id,))
    conn.commit()
    close_connection()

def test_add_to_inventory_creates_new_item(inventory_module):
    """Test adding a new item to inventory"""
    inventory_module.add("aguacates", 6, "unidades")

    # Verify item was added
    item = inventory_module.get("aguacates")
    assert item is not None
    assert item['quantity'] == 6
    assert item['unit'] == "unidades"

def test_add_to_inventory_increments_existing(inventory_module):
    """Test adding to existing inventory item"""
    inventory_module.add("aguacates", 6, "unidades")
    inventory_module.add("aguacates", 3, "unidades")

    item = inventory_module.get("aguacates")
    assert item['quantity'] == 9

def test_set_inventory_updates_quantity(inventory_module):
    """Test setting absolute quantity"""
    inventory_module.add("aguacates", 10, "unidades")
    inventory_module.set("aguacates", 2, "unidades")

    item = inventory_module.get("aguacates")
    assert item['quantity'] == 2

def test_get_nonexistent_item_returns_none(inventory_module):
    """Test getting item that doesn't exist"""
    item = inventory_module.get("nonexistent")
    assert item is None

def test_list_all_returns_all_items(inventory_module):
    """Test listing all inventory items"""
    inventory_module.add("aguacates", 6, "unidades")
    inventory_module.add("leche", 1, "litros")

    items = inventory_module.list_all()
    assert len(items) == 2
    assert any(i['item_name'] == 'aguacates' for i in items)
    assert any(i['item_name'] == 'leche' for i in items)

def test_check_threshold_returns_true_when_low(inventory_module):
    """Test threshold check when quantity is low"""
    inventory_module.add("aguacates", 2, "unidades")  # Default threshold is 2
    is_low = inventory_module.check_threshold("aguacates")
    assert is_low is True

def test_check_threshold_returns_false_when_sufficient(inventory_module):
    """Test threshold check when quantity is sufficient"""
    inventory_module.add("aguacates", 5, "unidades")
    is_low = inventory_module.check_threshold("aguacates")
    assert is_low is False

def test_set_threshold_updates_threshold(inventory_module):
    """Test setting custom threshold"""
    inventory_module.add("aguacates", 5, "unidades")
    inventory_module.set_threshold("aguacates", 10)

    # Now 5 should be below threshold of 10
    is_low = inventory_module.check_threshold("aguacates")
    assert is_low is True
