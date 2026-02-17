"""Tests for PackingModule with recurring items support."""
import pytest
import sqlite3
from modules.packing import PackingModule


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

    def cursor(self, dictionary=True):
        """Return a MySQL-compatible cursor (DictCursor by default to match MariaDB)."""
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
            list_category TEXT NOT NULL,
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
        CREATE INDEX idx_lists_user_category ON lists(user_id, list_category)
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


def test_add_recurring_item(db):
    """Test adding an item with recurring=True."""
    packing = PackingModule(db, 'test_user', 'test_packing', 'packing')

    packing.add('cepillo de dientes', quantity=1, unit='unidades', recurring=True)

    item = packing.get('cepillo de dientes')
    assert item is not None
    assert item['item_name'] == 'cepillo de dientes'
    assert item['recurring'] is True


def test_add_non_recurring_item(db):
    """Test adding an item with recurring=False (default)."""
    packing = PackingModule(db, 'test_user', 'test_packing', 'packing')

    packing.add('revista', quantity=1, unit='unidades', recurring=False)

    item = packing.get('revista')
    assert item is not None
    assert item['item_name'] == 'revista'
    assert item['recurring'] is False


def test_check_non_recurring_item_removes_it(db):
    """Test checking a non-recurring item removes it from list."""
    packing = PackingModule(db, 'test_user', 'test_packing', 'packing')

    packing.add('libro', quantity=1, unit='unidades', recurring=False)

    result = packing.check_item('libro')

    assert result['status'] == 'checked'
    assert 'empacado y eliminado de lista' in result['message']
    assert '✅' in result['message']

    # Verify item was removed
    item = packing.get('libro')
    assert item is None


def test_check_recurring_item_keeps_it(db):
    """Test checking a recurring item keeps it in list."""
    packing = PackingModule(db, 'test_user', 'test_packing', 'packing')

    packing.add('cargador', quantity=1, unit='unidades', recurring=True)

    result = packing.check_item('cargador')

    assert result['status'] == 'checked'
    assert 'marcado (se mantiene en lista)' in result['message']
    assert '✅' in result['message']

    # Verify item still exists
    item = packing.get('cargador')
    assert item is not None
    assert item['item_name'] == 'cargador'
