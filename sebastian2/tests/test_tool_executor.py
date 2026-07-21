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
        CREATE TABLE project_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            project TEXT NOT NULL,
            priority TEXT DEFAULT 'normal',
            done INTEGER DEFAULT 0,
            notes TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
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
    """weather_get calls WeatherModule.get_weather and returns pre-formatted text."""
    mock_weather.return_value = {
        'success': True, 'result': '📍 Madrid, ES\n🌡️ 15°C', 'data': {'temp': 15.0}
    }
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("weather_get", {})
    assert isinstance(result, str)
    assert 'Madrid' in result


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
    from datetime import date
    mock_add.assert_called_once_with(
        title="Dentista",
        event_date=date(2026, 3, 10),
        event_time="10:00",
        all_day=False,
        recurrence_rule=None,
    )
    assert result['status'] == 'added'


@patch('modules.calendar.CalendarModule.remove_event')
def test_calendar_remove_event_dispatches(mock_remove, db):
    """calendar_remove_event calls CalendarModule.remove_event."""
    mock_remove.return_value = {'status': 'removed', 'message': 'Eliminado'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("calendar_remove_event", {"title": "Dentista"})
    from datetime import date
    mock_remove.assert_called_once_with(title="Dentista", event_date=None)
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
    mock_update.assert_called_once_with(
        title="Dentista",
        event_date=None,
        new_title=None,
        new_date=None,
        new_time="11:00",
    )
    assert result['status'] == 'updated'


@patch('modules.calendar.CalendarModule.add_note')
def test_calendar_add_note_dispatches(mock_add_note, db):
    """calendar_add_note calls CalendarModule.add_note with event_id and note_text."""
    mock_add_note.return_value = {'status': 'updated', 'message': 'Nota añadida'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("calendar_add_note", {"event_id": 42, "note_text": "llevar dinero"})
    mock_add_note.assert_called_once_with(event_id=42, note_text="llevar dinero")
    assert result['status'] == 'updated'


@patch('modules.inventory.InventoryModule.add')
def test_inventory_add_dispatches(mock_add, db):
    """inventory_add calls InventoryModule.add with correct args."""
    mock_add.return_value = {'status': 'added', 'item': {'name': 'aceite'}}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("inventory_add", {"item_name": "aceite", "quantity": 2})
    mock_add.assert_called_once_with(
        item_name="aceite",
        quantity=2,
        unit="unidades",
        threshold=2,
    )
    assert result['status'] == 'added'


@patch('modules.inventory.InventoryModule.remove')
def test_inventory_remove_dispatches(mock_remove, db):
    """inventory_remove calls InventoryModule.remove with item_name."""
    mock_remove.return_value = True
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("inventory_remove", {"item_name": "aceite"})
    mock_remove.assert_called_once_with("aceite")
    assert result == {'status': 'removed'}


@patch('modules.inventory.InventoryModule.set_quantity')
def test_inventory_set_quantity_dispatches(mock_set, db):
    """inventory_set_quantity calls InventoryModule.set_quantity with item_name and quantity."""
    mock_set.return_value = {'status': 'updated'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("inventory_set_quantity", {"item_name": "aceite", "quantity": 5})
    mock_set.assert_called_once_with("aceite", 5)
    assert result['status'] == 'updated'


@patch('modules.inventory.InventoryModule.update_quantity')
def test_inventory_update_quantity_dispatches(mock_update, db):
    """inventory_update_quantity calls InventoryModule.update_quantity with item_name and delta."""
    mock_update.return_value = {'status': 'updated', 'message': 'Actualizado aceite: 3 unidades', 'warning': False}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("inventory_update_quantity", {"item_name": "aceite", "delta": -2})
    mock_update.assert_called_once_with("aceite", -2)
    assert result['status'] == 'updated'


@patch('modules.item_list.ItemListModule.add')
def test_list_add_item_dispatches(mock_add, db):
    """list_add_item calls ItemListModule.add for the named list."""
    mock_add.return_value = {'status': 'added', 'item': {'name': 'leche'}}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("list_add_item", {"list_name": "compra", "item_name": "leche"})
    mock_add.assert_called_once_with(item_name="leche", quantity=1)
    assert result['status'] == 'added'


@patch('modules.item_list.ItemListModule.remove')
def test_list_remove_item_dispatches(mock_remove, db):
    """list_remove_item calls ItemListModule.remove."""
    mock_remove.return_value = True
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("list_remove_item", {"list_name": "compra", "item_name": "leche"})
    mock_remove.assert_called_once_with("leche")
    assert result == {'status': 'removed'}


@patch('modules.item_list.ItemListModule.list_all')
def test_list_items_dispatches(mock_list_all, db):
    """list_items calls ItemListModule.list_all for the named list."""
    mock_list_all.return_value = [{'item_name': 'leche', 'quantity': 2}]
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("list_items", {"list_name": "maleta"})
    mock_list_all.assert_called_once_with()
    assert result[0]['item_name'] == 'leche'


@patch('modules.item_list.ItemListModule.clear_all')
def test_list_clear_dispatches(mock_clear, db):
    """list_clear calls ItemListModule.clear_all and returns count."""
    mock_clear.return_value = 3
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("list_clear", {"list_name": "compra"})
    mock_clear.assert_called_once_with()
    assert result == {'status': 'cleared', 'count': 3}


@patch('modules.notes.NotesModule.create')
def test_notes_create_dispatches(mock_create, db):
    """notes_create calls NotesModule.create with content and tags."""
    mock_create.return_value = 7
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("notes_create", {"content": "Comprar flores", "tags": ["pendiente"]})
    mock_create.assert_called_once_with("Comprar flores", ["pendiente"])
    assert result == 7


@patch('modules.notes.NotesModule.append_text')
def test_notes_append_dispatches(mock_append, db):
    """notes_append calls NotesModule.append_text with note_id and text."""
    mock_append.return_value = {'status': 'updated'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("notes_append", {"note_id": 7, "text": "también rosas"})
    mock_append.assert_called_once_with(7, "también rosas")
    assert result['status'] == 'updated'


@patch('modules.notes.NotesModule.add_tag')
def test_notes_add_tag_dispatches(mock_tag, db):
    """notes_add_tag calls NotesModule.add_tag with note_id and tag."""
    mock_tag.return_value = {'status': 'added'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("notes_add_tag", {"note_id": 7, "tag": "urgente"})
    mock_tag.assert_called_once_with(7, "urgente")
    assert result['status'] == 'added'


@patch('modules.notes.NotesModule.remove_tag')
def test_notes_remove_tag_dispatches(mock_remove_tag, db):
    """notes_remove_tag calls NotesModule.remove_tag with note_id and tag."""
    mock_remove_tag.return_value = {'status': 'removed'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("notes_remove_tag", {"note_id": 7, "tag": "urgente"})
    mock_remove_tag.assert_called_once_with(7, "urgente")
    assert result['status'] == 'removed'


@patch('modules.notes.NotesModule.delete')
def test_notes_delete_dispatches(mock_delete, db):
    """notes_delete calls NotesModule.delete and returns status dict."""
    mock_delete.return_value = True
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("notes_delete", {"note_id": 7})
    mock_delete.assert_called_once_with(7)
    assert result == {'status': 'deleted'}


# ── Tasks ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def vault_dir(tmp_path):
    """Minimal fake vault (PROJECTS.md) for known-project validation + consult_docs."""
    (tmp_path / "PROJECTS.md").write_text(
        "## sebastian — Personal Assistant\nEstado: en desarrollo.\n"
        "Puerto: n/a.\n\n"
        "## glasspannel — Server Control Panel\nPuerto: 8420.\n",
        encoding="utf-8",
    )
    return tmp_path


@patch('modules.tasks.TasksModule.list')
def test_tasks_list_dispatches(mock_list, db):
    """tasks_list calls TasksModule.list with project/state passthrough."""
    mock_list.return_value = [{'id': 1, 'title': 'revisar fuzzy match'}]
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("tasks_list", {"project": "sebastian", "state": "open"})
    mock_list.assert_called_once_with(project="sebastian", state="open")
    assert result[0]['title'] == 'revisar fuzzy match'


@patch('modules.tasks.TasksModule.list')
def test_tasks_list_defaults_state_to_open(mock_list, db):
    """tasks_list defaults state to 'open' when not given."""
    mock_list.return_value = []
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    executor.execute("tasks_list", {})
    mock_list.assert_called_once_with(project=None, state="open")


def test_tasks_create_dispatches_with_known_projects(db, vault_dir):
    """tasks_create validates project against PROJECTS.md-derived known_projects and creates."""
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config={'vault_docs_path': str(vault_dir)})
    result = executor.execute("tasks_create", {"project": "sebastian", "title": "revisar fuzzy match"})
    assert result['status'] == 'created'


def test_tasks_create_rejects_unknown_project(db, vault_dir):
    """tasks_create rejects a project not present in PROJECTS.md."""
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config={'vault_docs_path': str(vault_dir)})
    result = executor.execute("tasks_create", {"project": "proyecto-inventado-xyz", "title": "tarea"})
    assert result['status'] == 'unknown_project'


@patch('modules.tasks.TasksModule.complete')
def test_tasks_complete_dispatches(mock_complete, db):
    """tasks_complete calls TasksModule.complete with task_id."""
    mock_complete.return_value = {'status': 'completed', 'task_id': 5}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("tasks_complete", {"task_id": 5})
    mock_complete.assert_called_once_with(5)
    assert result['status'] == 'completed'


# ── Consult docs ──────────────────────────────────────────────────────────────

def test_consult_docs_dispatches(db, vault_dir):
    """consult_docs resolves via ConsultDocsModule using config's vault_docs_path."""
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config={'vault_docs_path': str(vault_dir)})
    result = executor.execute("consult_docs", {"project": "glasspannel", "query": "puerto"})
    assert result['status'] == 'found'
    assert any('8420' in r['content'] for r in result['results'])
