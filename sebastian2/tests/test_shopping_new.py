"""Tests for ShoppingModule - simple pass-through from ItemListModule."""
import pytest
import sqlite3
from modules.shopping_new import ShoppingModule


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
            recurring BOOLEAN DEFAULT 0,
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


def test_shopping_inherits_from_item_list(db):
    """Test that ShoppingModule inherits all ItemListModule functionality."""
    shopping = ShoppingModule(db, 'shopping', 'test_user')

    # Test add and get work correctly
    shopping.add('manzanas', quantity=5, unit='unidades')

    item = shopping.get('manzanas')
    assert item is not None
    assert item['item_name'] == 'manzanas'
    assert item['quantity'] == 5
    assert item['unit'] == 'unidades'
