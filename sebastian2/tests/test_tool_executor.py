"""Tests for ToolExecutor — tool name → module method dispatch."""
import pytest
import sqlite3
from unittest.mock import patch
from tests.test_item_list_module import MySQLCompatibleConnection


@pytest.fixture
def db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            list_category TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            quantity REAL DEFAULT 1,
            unit TEXT,
            notes TEXT,
            checked INTEGER DEFAULT 0,
            low_threshold REAL,
            recurring INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
        );
        CREATE TABLE user_settings (
            user_id TEXT PRIMARY KEY,
            sprite_skin TEXT DEFAULT 'default',
            weather_location TEXT DEFAULT 'Madrid',
            weather_lat REAL DEFAULT 40.4168,
            weather_lon REAL DEFAULT -3.7038,
            weather_country TEXT DEFAULT 'ES'
        );
        INSERT INTO user_settings VALUES ('99999', 'default', 'Madrid', 40.4168, -3.7038, 'ES');
    ''')
    conn.commit()
    yield MySQLCompatibleConnection(conn)


def test_unknown_tool_raises(db):
    """Unknown tool name raises ValueError."""
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    with pytest.raises(ValueError, match="Unknown tool"):
        executor.execute("does_not_exist", {})


def test_inventory_list_returns_list(db):
    """inventory_list returns a list (possibly empty)."""
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("inventory_list", {})
    assert isinstance(result, list)


def test_shopping_list_returns_list(db):
    """shopping_list returns a list."""
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("shopping_list", {})
    assert isinstance(result, list)


def test_inventory_check_low_stock_returns_list(db):
    """inventory_check_low_stock returns a list."""
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("inventory_check_low_stock", {})
    assert isinstance(result, list)


@patch('modules.calendar.CalendarModule.search_events')
def test_calendar_search_events_dispatches(mock_search, db):
    """calendar_search_events calls CalendarModule.search_events."""
    mock_search.return_value = [{'event_id': 1, 'title': 'Teatro', 'date': '2026-03-05'}]
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("calendar_search_events", {"query": "teatro"})
    mock_search.assert_called_once_with("teatro")
    assert result[0]['title'] == 'Teatro'


@patch('modules.weather.WeatherModule.get_weather')
def test_weather_get_dispatches(mock_weather, db):
    """weather_get calls WeatherModule.get_weather and returns data field."""
    mock_weather.return_value = {
        'success': True, 'result': 'texto', 'data': {'temp': 15.0}
    }
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("weather_get", {})
    assert result['temp'] == 15.0


@patch('modules.weather.WeatherModule.get_forecast_for_date')
def test_weather_forecast_for_date_dispatches(mock_forecast, db):
    """weather_forecast_for_date calls correct method."""
    mock_forecast.return_value = {
        'success': True, 'result': '', 'data': {'dates': ['2026-03-05'], 'precip_prob': [70]}
    }
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("weather_forecast_for_date", {"date": "2026-03-05"})
    mock_forecast.assert_called_once_with("2026-03-05")
    assert result['precip_prob'] == [70]


@patch('modules.calendar.CalendarModule.add_event')
def test_calendar_add_event_dispatches(mock_add, db):
    """calendar_add_event calls CalendarModule.add_event with correct args."""
    mock_add.return_value = {'status': 'added', 'message': 'Evento añadido'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("calendar_add_event", {
        "title": "Dentista", "date": "2026-03-10", "time": "10:00"
    })
    mock_add.assert_called_once()
    assert result['status'] == 'added'


@patch('modules.calendar.CalendarModule.remove_event')
def test_calendar_remove_event_dispatches(mock_remove, db):
    """calendar_remove_event calls CalendarModule.remove_event."""
    mock_remove.return_value = {'status': 'removed', 'message': 'Eliminado'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("calendar_remove_event", {"title": "Dentista"})
    mock_remove.assert_called_once()
    assert result['status'] == 'removed'


@patch('modules.calendar.CalendarModule.update_event')
def test_calendar_update_event_dispatches(mock_update, db):
    """calendar_update_event calls CalendarModule.update_event."""
    mock_update.return_value = {'status': 'updated', 'message': 'Actualizado'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("calendar_update_event", {
        "title": "Dentista", "new_time": "11:00"
    })
    mock_update.assert_called_once()
    assert result['status'] == 'updated'
