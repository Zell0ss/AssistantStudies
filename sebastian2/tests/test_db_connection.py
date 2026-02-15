# tests/test_db_connection.py
import pytest
from db.connection import get_connection, close_connection

def test_get_connection_returns_valid_connection():
    """Test that get_connection returns a working database connection"""
    conn = get_connection()
    assert conn is not None

    # Test connection is usable
    cursor = conn.cursor()
    cursor.execute("SELECT 1 as value")
    result = cursor.fetchone()
    assert result['value'] == 1

    close_connection()

def test_connection_is_reused():
    """Test that get_connection reuses the same connection"""
    conn1 = get_connection()
    conn2 = get_connection()
    assert conn1 is conn2
    close_connection()
