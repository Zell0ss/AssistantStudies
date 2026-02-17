"""Tests for InventoryModule with threshold warning support."""
import pytest
import sqlite3
from modules.inventory import InventoryModule


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

    def close(self):
        return self._cursor.close()

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

    def cursor(self, dictionary=False):
        """Return a MySQL-compatible cursor."""
        if dictionary:
            self._conn.row_factory = sqlite3.Row
            cursor = self._conn.cursor()
            return DictCursor(cursor)
        return MySQLCompatibleCursor(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()


class DictCursor(MySQLCompatibleCursor):
    """Cursor that returns results as dictionaries."""

    def fetchone(self):
        row = self._cursor.fetchone()
        if row:
            return dict(row)
        return None

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [dict(row) for row in rows]


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
            quantity REAL DEFAULT 1,
            unit TEXT,
            notes TEXT,
            checked BOOLEAN DEFAULT 0,
            low_threshold REAL,
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

    # Cleanup
    conn.close()


def test_add_with_threshold_no_warning(db):
    """Test adding item above threshold - should not warn."""
    inventory = InventoryModule(db, 'inventory', 'test_user')

    result = inventory.add('pasta', quantity=5, unit='paquetes', threshold=2)

    assert result['status'] == 'added'
    assert result['warning'] is False
    assert 'pasta' in result['message']
    assert '⚠️' not in result['message']


def test_add_with_quantity_below_threshold_warns(db):
    """Test adding item below threshold - should warn with ⚠️ emoji."""
    inventory = InventoryModule(db, 'inventory', 'test_user')

    result = inventory.add('leche', quantity=1, unit='litros', threshold=2)

    assert result['status'] == 'added'
    assert result['warning'] is True
    assert '⚠️' in result['message']
    assert 'Te queda poco' in result['message']
    assert 'leche' in result['message']


def test_update_quantity_below_threshold_warns(db):
    """Test updating quantity to below threshold - should warn."""
    inventory = InventoryModule(db, 'inventory', 'test_user')

    # Add item above threshold
    inventory.add('arroz', quantity=5, unit='kilos', threshold=2)

    # Update to below threshold
    result = inventory.update_quantity('arroz', -4)  # 5 - 4 = 1

    assert result['status'] == 'updated'
    assert result['warning'] is True
    assert '⚠️' in result['message']
    assert 'Te queda poco' in result['message']


def test_check_low_stock(db):
    """Test check_low_stock returns items below threshold."""
    inventory = InventoryModule(db, 'inventory', 'test_user')

    # Add items with different stock levels
    inventory.add('azúcar', quantity=1, unit='kilos', threshold=2)  # Below threshold
    inventory.add('sal', quantity=5, unit='kilos', threshold=2)      # Above threshold
    inventory.add('café', quantity=1, unit='paquetes', threshold=3)  # Below threshold

    low_stock = inventory.check_low_stock()

    assert len(low_stock) == 2
    low_stock_names = [item['name'] for item in low_stock]
    assert 'azúcar' in low_stock_names
    assert 'café' in low_stock_names
    assert 'sal' not in low_stock_names
