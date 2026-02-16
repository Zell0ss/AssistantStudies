"""
Tests for ItemListModule base class.

This module tests the core functionality of the ItemListModule class,
which provides the foundation for inventory, shopping, and packing list features.
"""
import pytest
import sqlite3
from modules.item_list import ItemListModule


class MySQLCompatibleCursor:
    """Cursor wrapper that converts MySQL %s placeholders to SQLite ? placeholders."""

    def __init__(self, sqlite_cursor):
        self._cursor = sqlite_cursor

    def execute(self, query, params=None):
        """Execute query after converting %s to ?."""
        if params:
            # Convert MySQL %s placeholders to SQLite ? placeholders
            query = query.replace('%s', '?')
        return self._cursor.execute(query, params or ())

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid


class MySQLCompatibleConnection:
    """Connection wrapper that returns MySQL-compatible cursors."""

    def __init__(self, sqlite_conn):
        self._conn = sqlite_conn

    def cursor(self):
        """Return a MySQL-compatible cursor."""
        return MySQLCompatibleCursor(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()


@pytest.fixture
def db():
    """Create a test database with schema (MySQL-compatible wrapper)."""
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # Create tables matching migration 003
    cursor.execute('''
        CREATE TABLE lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            list_type TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            unit TEXT,
            notes TEXT,
            checked BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE INDEX idx_lists_user_type ON lists(user_id, list_type)
    ''')

    cursor.execute('''
        CREATE INDEX idx_list_items_list_id ON list_items(list_id)
    ''')

    conn.commit()

    # Wrap connection to provide MySQL-compatible interface
    wrapped_conn = MySQLCompatibleConnection(conn)
    yield wrapped_conn
    conn.close()


def test_add_item_creates_list_and_item(db):
    """Test that adding an item creates both list and item records."""
    module = ItemListModule(db, list_type="inventory", user_id=12345)

    # Add an item
    module.add("Tomates", quantity=5, unit="kg")

    # Verify list was created
    cursor = db.cursor()
    cursor.execute("SELECT * FROM lists WHERE user_id = ? AND list_type = ?",
                   (12345, "inventory"))
    list_row = cursor.fetchone()
    assert list_row is not None
    assert list_row[1] == 12345  # user_id
    assert list_row[2] == "inventory"  # list_type

    # Verify item was added
    cursor.execute("SELECT * FROM list_items WHERE list_id = ?", (list_row[0],))
    item_row = cursor.fetchone()
    assert item_row is not None
    assert item_row[2] == "Tomates"  # name
    assert item_row[3] == 5  # quantity
    assert item_row[4] == "kg"  # unit


def test_add_duplicate_item_updates_quantity(db):
    """Test that adding a duplicate item updates the quantity."""
    module = ItemListModule(db, list_type="shopping", user_id=12345)

    # Add item first time
    module.add("Pan", quantity=2)

    # Add same item again
    module.add("Pan", quantity=3)

    # Verify only one item exists with updated quantity
    cursor = db.cursor()
    cursor.execute("""
        SELECT li.name, li.quantity
        FROM list_items li
        JOIN lists l ON li.list_id = l.id
        WHERE l.user_id = ? AND l.list_type = ?
    """, (12345, "shopping"))

    items = cursor.fetchall()
    assert len(items) == 1
    assert items[0][0] == "Pan"
    assert items[0][1] == 5  # 2 + 3


def test_remove_item(db):
    """Test removing an item from the list."""
    module = ItemListModule(db, list_type="inventory", user_id=12345)

    # Add items
    module.add("Tomates", quantity=5)
    module.add("Cebollas", quantity=3)

    # Remove one item
    removed = module.remove("Tomates")

    # Verify item was removed
    assert removed is True
    items = module.list_all()
    assert len(items) == 1
    assert items[0]['item_name'] == "Cebollas"


def test_remove_nonexistent_item(db):
    """Test that removing a nonexistent item returns False."""
    module = ItemListModule(db, list_type="shopping", user_id=12345)

    # Try to remove item from empty list
    removed = module.remove("nonexistent")

    assert removed is False

    # Add an item and try to remove a different one
    module.add("Pan", quantity=1)
    removed = module.remove("Leche")

    assert removed is False


def test_get_item(db):
    """Test retrieving a specific item."""
    module = ItemListModule(db, list_type="shopping", user_id=12345)

    # Add item
    module.add("Leche", quantity=2, unit="litros", notes="Desnatada")

    # Get item
    item = module.get("Leche")

    assert item is not None
    assert item['item_name'] == "Leche"
    assert item['quantity'] == 2
    assert item['unit'] == "litros"
    assert item['notes'] == "Desnatada"
    assert item['checked'] == 0


def test_list_all_items(db):
    """Test listing all items in a list."""
    module = ItemListModule(db, list_type="packing", user_id=12345)

    # Add multiple items
    module.add("Camisetas", quantity=3)
    module.add("Pantalones", quantity=2)
    module.add("Zapatos", quantity=1, unit="par")

    # List all
    items = module.list_all()

    assert len(items) == 3
    item_names = [item['item_name'] for item in items]
    assert "Camisetas" in item_names
    assert "Pantalones" in item_names
    assert "Zapatos" in item_names


def test_update_quantity(db):
    """Test updating item quantity by delta."""
    module = ItemListModule(db, list_type="inventory", user_id=12345)

    # Add item
    module.add("Manzanas", quantity=10)

    # Update quantity (add 5)
    module.update_quantity("Manzanas", 5)
    item = module.get("Manzanas")
    assert item['quantity'] == 15

    # Update quantity (subtract 7)
    module.update_quantity("Manzanas", -7)
    item = module.get("Manzanas")
    assert item['quantity'] == 8


def test_set_quantity(db):
    """Test setting item quantity to absolute value."""
    module = ItemListModule(db, list_type="shopping", user_id=12345)

    # Add item
    module.add("Huevos", quantity=6)

    # Set quantity to new value
    module.set_quantity("Huevos", 12)
    item = module.get("Huevos")
    assert item['quantity'] == 12


def test_list_all_lists(db):
    """Test listing all lists for a user."""
    # Create multiple lists
    module1 = ItemListModule(db, list_type="inventory", user_id=12345)
    module1.add("Item1")

    module2 = ItemListModule(db, list_type="shopping", user_id=12345)
    module2.add("Item2")

    module3 = ItemListModule(db, list_type="packing", user_id=12345)
    module3.add("Item3")

    # List all lists for user
    lists = ItemListModule.list_all_lists(db, user_id=12345)

    assert len(lists) == 3
    list_types = [lst['list_type'] for lst in lists]
    assert "inventory" in list_types
    assert "shopping" in list_types
    assert "packing" in list_types


def test_create_list(db):
    """Test explicitly creating a named list."""
    # Create a named list
    list_id = ItemListModule.create_list(
        db,
        user_id=12345,
        list_type="shopping",
        name="Compra semanal"
    )

    # Verify list was created
    cursor = db.cursor()
    cursor.execute("SELECT * FROM lists WHERE id = ?", (list_id,))
    row = cursor.fetchone()

    assert row is not None
    assert row[1] == 12345  # user_id
    assert row[2] == "shopping"  # list_type
    assert row[3] == "Compra semanal"  # name


def test_multiple_users_separate_lists(db):
    """Test that different users have separate lists."""
    module1 = ItemListModule(db, list_type="inventory", user_id=111)
    module1.add("User1 Item")

    module2 = ItemListModule(db, list_type="inventory", user_id=222)
    module2.add("User2 Item")

    # Verify each user sees only their items
    items1 = module1.list_all()
    items2 = module2.list_all()

    assert len(items1) == 1
    assert len(items2) == 1
    assert items1[0]['item_name'] == "User1 Item"
    assert items2[0]['item_name'] == "User2 Item"


def test_case_insensitive_item_lookup(db):
    """Test that item names are matched case-insensitively."""
    module = ItemListModule(db, list_type="shopping", user_id=12345)

    # Add item
    module.add("Tomates", quantity=5)

    # Add with different case - should update existing
    module.add("tomates", quantity=3)

    # Verify only one item exists
    items = module.list_all()
    assert len(items) == 1
    assert items[0]['quantity'] == 8  # 5 + 3
