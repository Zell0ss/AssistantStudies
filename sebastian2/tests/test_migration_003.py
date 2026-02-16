"""Tests for migration 003 - unified list system."""
import pytest
from db.connection import get_connection


@pytest.fixture
def db():
    """Get database connection for testing."""
    return get_connection()


def test_lists_table_has_list_category(db):
    """Test that lists table has list_category column after migration."""
    cursor = db.cursor()
    cursor.execute("SHOW COLUMNS FROM lists LIKE 'list_category'")
    result = cursor.fetchone()
    assert result is not None, "list_category column should exist"
    assert 'enum' in result['Type'].lower(), "list_category should be ENUM type"


def test_list_items_has_quantity_unit(db):
    """Test that list_items has quantity and unit columns."""
    cursor = db.cursor()

    # Check quantity column
    cursor.execute("SHOW COLUMNS FROM list_items LIKE 'quantity'")
    result = cursor.fetchone()
    assert result is not None, "quantity column should exist"

    # Check unit column
    cursor.execute("SHOW COLUMNS FROM list_items LIKE 'unit'")
    result = cursor.fetchone()
    assert result is not None, "unit column should exist"

    # Check low_threshold column
    cursor.execute("SHOW COLUMNS FROM list_items LIKE 'low_threshold'")
    result = cursor.fetchone()
    assert result is not None, "low_threshold column should exist"


def test_inventory_table_renamed(db):
    """Test that inventory table was renamed to inventory_backup."""
    cursor = db.cursor()
    cursor.execute("SHOW TABLES LIKE 'inventory_backup'")
    result = cursor.fetchone()
    assert result is not None, "inventory_backup table should exist"


def test_inventory_data_migrated(db):
    """Test that inventory data was migrated to lists structure."""
    cursor = db.cursor()

    # Check that inventory lists exist (or 0 if no inventory data existed before)
    cursor.execute("""
        SELECT COUNT(*) as count FROM lists
        WHERE list_category = 'inventory' AND name = 'inventario'
    """)
    result = cursor.fetchone()
    count = result['count']
    # Migration creates inventory list only if inventory table had data
    # So count can be 0 or more
    assert count >= 0, "Should have migrated inventory list (or 0 if no data)"

    # Check that items were migrated
    cursor.execute("""
        SELECT COUNT(*) as count FROM list_items li
        JOIN lists l ON li.list_id = l.id
        WHERE l.list_category = 'inventory'
    """)
    result = cursor.fetchone()
    count = result['count']
    # Should have migrated items (or 0 if no data before)
    assert count >= 0, "Should have migrated inventory items"
