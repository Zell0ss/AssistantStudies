# tests/test_base_module.py
import pytest
from modules.base import BaseModule
from db.connection import get_connection, close_connection

@pytest.fixture
def base_module():
    """Fixture to create BaseModule instance"""
    conn = get_connection()
    user_id = "test_user_123"
    module = BaseModule(conn, user_id)
    yield module
    close_connection()

def test_base_module_has_connection(base_module):
    """Test that BaseModule stores connection"""
    assert base_module.db is not None

def test_base_module_has_user_id(base_module):
    """Test that BaseModule stores user_id"""
    assert base_module.user_id == "test_user_123"

def test_execute_query_returns_cursor(base_module):
    """Test that execute_query works"""
    cursor = base_module.execute_query("SELECT 1 as num", ())
    result = cursor.fetchone()
    assert result['num'] == 1
