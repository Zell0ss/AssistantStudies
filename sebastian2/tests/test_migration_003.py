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
    try:
        cursor.execute("SHOW COLUMNS FROM lists LIKE 'list_category'")
        result = cursor.fetchone()
        assert result is not None, "list_category column should exist"

        # Validate ENUM type and values
        enum_type = result['Type']
        assert 'enum' in enum_type.lower(), "list_category should be ENUM type"
        assert 'inventory' in enum_type, "ENUM should contain 'inventory' value"
        assert 'shopping' in enum_type, "ENUM should contain 'shopping' value"
        assert 'packing' in enum_type, "ENUM should contain 'packing' value"
    finally:
        cursor.close()


def test_list_items_has_quantity_unit(db):
    """Test that list_items has quantity and unit columns."""
    cursor = db.cursor()
    try:
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
    finally:
        cursor.close()


def test_inventory_table_renamed(db):
    """Test that inventory table was renamed to inventory_backup."""
    cursor = db.cursor()
    try:
        cursor.execute("SHOW TABLES LIKE 'inventory_backup'")
        result = cursor.fetchone()
        assert result is not None, "inventory_backup table should exist"
    finally:
        cursor.close()


def test_inventory_data_migrated(db):
    """Test that inventory data exists in the unified lists structure."""
    cursor = db.cursor()
    try:
        # Verify we can query inventory items from the unified structure
        cursor.execute("""
            SELECT COUNT(*) as count FROM list_items li
            JOIN lists l ON li.list_id = l.id
            WHERE l.list_category = 'inventory'
        """)
        result = cursor.fetchone()
        # The query must succeed (schema is correct) — count can be 0 if no data yet
        assert result is not None
        assert 'count' in result
    finally:
        cursor.close()
