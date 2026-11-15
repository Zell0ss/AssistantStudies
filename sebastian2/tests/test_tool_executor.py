"""Tests for ToolExecutor — tool name → module method dispatch."""
import pytest
import sqlite3
from pathlib import Path
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


# ── Memory ────────────────────────────────────────────────────────────────────

@patch('core.memoria.servicio.ServicioMemoria.desde_config')
def test_mark_as_memorable_dispatches(mock_desde_config, db):
    """mark_as_memorable (contrato nuevo, fase 2) llama a ServicioMemoria.guardar con el texto y el usuario."""
    mock_desde_config.return_value.guardar.return_value = {'success': True, 'result': 'Apuntado.', 'data': {}}
    from core.tool_executor import ToolExecutor
    config = {'openai_apikey': 'sk-fake', 'memory_collection': 'sebastian_memory_test'}
    executor = ToolExecutor(db, '99999', config=config)
    result = executor.execute("mark_as_memorable", {"texto": "Paco es alérgico a los frutos secos"})
    mock_desde_config.return_value.guardar.assert_called_once_with(
        '99999', "Paco es alérgico a los frutos secos", mensaje=None)
    assert mock_desde_config.call_args.args[:2] == (db, config)
    assert result['success'] is True


@patch('core.memoria.servicio.ServicioMemoria.desde_config')
def test_mark_as_memorable_pasa_el_mensaje_del_usuario(mock_desde_config, db):
    """R7 (D41): además de la frase del planner, la fuente guarda el literal que escribió el usuario en el turno."""
    mock_desde_config.return_value.guardar.return_value = {'success': True, 'result': 'Apuntado.', 'data': {}}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config={'memory_collection': 'x'})
    executor.mensaje_del_turno = "apunta lo de Paco, que es alérgico a los frutos secos"
    executor.execute("mark_as_memorable", {"texto": "Paco es alérgico a los frutos secos"})
    mock_desde_config.return_value.guardar.assert_called_once_with(
        '99999', "Paco es alérgico a los frutos secos", mensaje="apunta lo de Paco, que es alérgico a los frutos secos")


@patch('core.memoria.servicio.ServicioMemoria.desde_config')
def test_mark_as_memorable_pasa_el_contador_de_uso(mock_desde_config, db):
    """El extractor (Haiku) informa de su uso al orquestador, que ya lo contabiliza por turno."""
    from core.tool_executor import ToolExecutor
    usos = []
    executor = ToolExecutor(db, '99999', config={'memory_collection': 'x'}, on_usage=lambda r, m: usos.append(m))
    executor.execute("mark_as_memorable", {"texto": "algo"})
    mock_desde_config.call_args.kwargs['on_usage']("resp", "claude-haiku-4-5-20251001")
    assert usos == ["claude-haiku-4-5-20251001"]


@patch('core.memoria.servicio.ServicioMemoria.desde_config')
def test_mark_as_memorable_no_loguea_el_texto(mock_desde_config, db):
    """D39-D42 (fase 2): ni el texto del usuario ni el resultado van al log, en ningun nivel."""
    mock_desde_config.return_value.guardar.return_value = {
        'success': True, 'result': 'Apuntado.', 'data': {'guardados': [{'valor': 'valor-secreto-123'}]}}
    from core.tool_executor import ToolExecutor
    with patch('core.tool_executor.logger') as mock_logger:
        ToolExecutor(db, '99999', config={'memory_collection': 'x'}).execute(
            "mark_as_memorable", {"texto": "texto-secreto-456"})
    volcado = " ".join(str(c) for c in mock_logger.mock_calls)
    assert "texto-secreto-456" not in volcado and "valor-secreto-123" not in volcado
    assert "mark_as_memorable" in volcado


@patch('core.memoria.servicio.ServicioMemoria.desde_config')
def test_search_memory_no_loguea_la_consulta(mock_desde_config, db):
    mock_desde_config.return_value.consultar.return_value = {
        'hechos': [{'valor': 'dato-secreto-789'}], 'historial': [], 'notas': [], 'vault': None, 'conflictos': []}
    from core.tool_executor import ToolExecutor
    with patch('core.tool_executor.logger') as mock_logger:
        ToolExecutor(db, '99999', config={'memory_collection': 'x'}).execute(
            "search_memory", {"query": "consulta-secreta-000", "entidad": "entidad-secreta-111"})
    volcado = " ".join(str(c) for c in mock_logger.mock_calls)
    for secreto in ("consulta-secreta-000", "entidad-secreta-111", "dato-secreto-789"):
        assert secreto not in volcado, secreto
    assert "search_memory" in volcado


@patch('core.memoria.servicio.ServicioMemoria.desde_config')
def test_search_memory_dispatches(mock_desde_config, db):
    """search_memory (contrato nuevo, fase 2) llama a ServicioMemoria.consultar con el usuario y los 4 campos."""
    esperado = {'hechos': [{'entidad': 'Paco', 'atributo': 'alergia', 'valor': 'frutos secos'}],
                'historial': [], 'notas': [], 'vault': None, 'conflictos': []}
    mock_desde_config.return_value.consultar.return_value = esperado
    from core.tool_executor import ToolExecutor
    config = {'openai_apikey': 'sk-fake', 'memory_collection': 'sebastian_memory_test'}
    result = ToolExecutor(db, '99999', config=config).execute(
        "search_memory", {"query": "alergias de Paco", "entidad": "Paco", "atributo": "alergia", "historial": True})
    mock_desde_config.return_value.consultar.assert_called_once_with(
        '99999', "alergias de Paco", entidad="Paco", atributo="alergia", historial=True)
    assert mock_desde_config.call_args.args[:2] == (db, config)   # la config del ejecutor llega al servicio
    assert result == esperado


@patch('core.memoria.servicio.ServicioMemoria.desde_config')
def test_search_memory_solo_con_query_el_resto_por_defecto(mock_desde_config, db):
    from core.tool_executor import ToolExecutor
    ToolExecutor(db, '99999', config={'memory_collection': 'x'}).execute("search_memory", {"query": "algo"})
    mock_desde_config.return_value.consultar.assert_called_once_with(
        '99999', "algo", entidad=None, atributo=None, historial=False)


@patch('core.memoria.servicio.ServicioMemoria.desde_config')
def test_search_memory_sin_query_usa_entidad_y_atributo(mock_desde_config, db):
    """Hallado en la pasada de H3: el planner a veces da `entidad` y `atributo` y se deja `query`, que el
    esquema pide. Un KeyError ahi dejaba al planner sin respuesta de la memoria."""
    from core.tool_executor import ToolExecutor
    ToolExecutor(db, '99999', config={'memory_collection': 'x'}).execute(
        "search_memory", {"entidad": "Paco", "atributo": "alergia"})
    mock_desde_config.return_value.consultar.assert_called_once_with(
        '99999', "Paco alergia", entidad="Paco", atributo="alergia", historial=False)


@patch('core.memoria.servicio.ServicioMemoria.desde_config')
def test_search_memory_sin_nada_no_revienta(mock_desde_config, db):
    from core.tool_executor import ToolExecutor
    ToolExecutor(db, '99999', config={'memory_collection': 'x'}).execute("search_memory", {})
    mock_desde_config.return_value.consultar.assert_called_once_with(
        '99999', "", entidad=None, atributo=None, historial=False)


# ── YouTube ───────────────────────────────────────────────────────────────────

@pytest.fixture
def youtube_config(tmp_path):
    vault = tmp_path / "vault" / "30-projects"
    vault.mkdir(parents=True)
    return {
        'vault_docs_path': str(vault),
        'youtube_workdir': str(tmp_path / "ytb"),
    }


@patch('core.tool_executor.extraer')
def test_youtube_transcript_dispatches_success(mock_extraer, db, youtube_config):
    """youtube_transcript llama a extraer() y devuelve texto preformateado con la ruta relativa."""
    mock_extraer.return_value = {
        'titulo': 'Un vídeo', 'idioma': 'es', 'subtitulos': 'manual',
        'ruta_md': '/data/library/mi-wiki/docs/Obsidian/Clippings/un-video.md',
        'palabras': 3200, 'id': 'abc123',
    }
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=youtube_config)
    result = executor.execute(
        "youtube_transcript", {"url": "https://www.youtube.com/watch?v=abc123", "idioma": "es"}
    )
    assert isinstance(result, str)
    assert "Un vídeo" in result
    assert "Clippings/un-video.md" in result
    assert "~3.200" in result
    call_args = mock_extraer.call_args
    assert call_args[0][0] == "https://www.youtube.com/watch?v=abc123"
    assert call_args[0][1] == "es"


@patch('core.tool_executor.extraer')
def test_youtube_transcript_deriva_clippings_de_vault_docs_path(mock_extraer, db, youtube_config):
    """clippings = <padre de vault_docs_path>/Clippings."""
    mock_extraer.return_value = {
        'titulo': 't', 'idioma': 'es', 'subtitulos': 'manual', 'ruta_md': 'x.md', 'palabras': 1, 'id': 'x',
    }
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=youtube_config)
    executor.execute("youtube_transcript", {"url": "u", "idioma": "es"})
    clippings_arg = mock_extraer.call_args[0][3]
    assert str(clippings_arg) == str(Path(youtube_config['vault_docs_path']).parent / "Clippings")


@patch('core.tool_executor.extraer')
def test_youtube_transcript_usa_workdir_configurado(mock_extraer, db, youtube_config):
    """El workdir viene de config['youtube_workdir'] cuando está presente."""
    mock_extraer.return_value = {
        'titulo': 't', 'idioma': 'es', 'subtitulos': 'manual', 'ruta_md': 'x.md', 'palabras': 1, 'id': 'x',
    }
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=youtube_config)
    executor.execute("youtube_transcript", {"url": "u", "idioma": "es"})
    workdir_arg = mock_extraer.call_args[0][2]
    assert str(workdir_arg) == youtube_config['youtube_workdir']


@patch('core.tool_executor.extraer')
def test_youtube_transcript_default_workdir_cuando_no_configurado(mock_extraer, db, tmp_path):
    """Sin youtube_workdir en config, usa /data/ytb-video-extracts por defecto."""
    vault = tmp_path / "30-projects"
    vault.mkdir()
    mock_extraer.return_value = {
        'titulo': 't', 'idioma': 'es', 'subtitulos': 'manual', 'ruta_md': 'x.md', 'palabras': 1, 'id': 'x',
    }
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config={'vault_docs_path': str(vault)})
    executor.execute("youtube_transcript", {"url": "u", "idioma": "es"})
    workdir_arg = mock_extraer.call_args[0][2]
    assert str(workdir_arg) == '/data/ytb-video-extracts'


@patch('core.tool_executor.extraer')
def test_youtube_transcript_sin_subtitulos_mensaje_legible(mock_extraer, db, youtube_config):
    """SinSubtitulos se traduce a texto con los idiomas disponibles."""
    from modules.youtube_transcript import SinSubtitulos
    mock_extraer.side_effect = SinSubtitulos(disponibles=['en', 'fr'])
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=youtube_config)
    result = executor.execute("youtube_transcript", {"url": "u", "idioma": "es"})
    assert isinstance(result, str)
    assert "en" in result and "fr" in result


@patch('core.tool_executor.extraer')
def test_youtube_transcript_429_mensaje_sudo(mock_extraer, db, youtube_config):
    """YtDlpDesactualizado se traduce al mensaje que Alfred puede transmitir a Josem."""
    from modules.youtube_transcript import YtDlpDesactualizado
    mock_extraer.side_effect = YtDlpDesactualizado()
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=youtube_config)
    result = executor.execute("youtube_transcript", {"url": "u", "idioma": "es"})
    assert "sudo -n yt-dlp -U" in result


@patch('core.tool_executor.extraer')
def test_youtube_transcript_otro_error_mensaje_legible(mock_extraer, db, youtube_config):
    """YtDlpError se traduce a texto legible, sin propagar la excepción."""
    from modules.youtube_transcript import YtDlpError
    mock_extraer.side_effect = YtDlpError("boom")
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=youtube_config)
    result = executor.execute("youtube_transcript", {"url": "u", "idioma": "es"})
    assert isinstance(result, str)
    assert "boom" in result


@patch('core.tool_executor.extraer')
def test_youtube_transcript_ambos_combina_resultados(mock_extraer, db, youtube_config):
    """idioma='ambos' combina el texto de ambos idiomas en la respuesta."""
    mock_extraer.return_value = {
        'ambos': {
            'es': {'titulo': 't', 'idioma': 'es', 'subtitulos': 'manual',
                   'ruta_md': '/vault/Clippings/t-es.md', 'palabras': 100, 'id': 'x'},
            'en': {'titulo': 't', 'idioma': 'en', 'subtitulos': 'manual',
                   'ruta_md': '/vault/Clippings/t-en.md', 'palabras': 120, 'id': 'x'},
        },
        'errores': {},
    }
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=youtube_config)
    result = executor.execute("youtube_transcript", {"url": "u", "idioma": "ambos"})
    assert "t-es.md" in result
    assert "t-en.md" in result


SALUD_CONFIG = {'tristras_url': 'http://127.0.0.1:8003', 'tristras_token': 'tok'}


@patch('modules.salud.SaludModule.registrar_texto')
def test_salud_dispatches(mock_registrar, db):
    """salud calls SaludModule.registrar_texto with the raw mensaje."""
    mock_registrar.return_value = "Anoche: 6 h 45 min. Apuntado."
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=SALUD_CONFIG)
    result = executor.execute("salud", {"mensaje": "he dormido 6 horas 45, fatal"})
    mock_registrar.assert_called_once_with("he dormido 6 horas 45, fatal")
    assert result == "Anoche: 6 h 45 min. Apuntado."


def test_salud_module_uses_configured_tristras_url_and_token(db):
    """ToolExecutor passes config['tristras_url']/['tristras_token'] through to SaludModule."""
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=SALUD_CONFIG)
    with patch('modules.salud.SaludModule.__init__', return_value=None) as mock_init:
        with patch('modules.salud.SaludModule.registrar_texto', return_value="ok"):
            executor.execute("salud", {"mensaje": "algo"})
    mock_init.assert_called_once_with(base_url='http://127.0.0.1:8003', token='tok')


@patch('modules.salud.SaludModule.registrar_texto')
@patch('core.tool_executor.logger')
def test_salud_no_registra_el_mensaje_en_debug(mock_logger, mock_registrar, db):
    """D39-D42: nunca el texto del usuario ni el resumen en los logs, ni en debug."""
    mock_registrar.return_value = "Anoche: 6 h 45 min, me desperté con dolor de cabeza. Apuntado."
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999', config=SALUD_CONFIG)
    executor.execute("salud", {"mensaje": "dormí fatal, dolor de cabeza al despertar"})

    lineas_logueadas = [call.args[0] for call in mock_logger.debug.call_args_list]
    assert not any("dolor de cabeza" in linea for linea in lineas_logueadas)
    assert not any("dormí fatal" in linea for linea in lineas_logueadas)
    assert any("salud" in linea for linea in lineas_logueadas)  # el nombre de la tool sí se registra


@patch('core.tool_executor.extraer')
def test_youtube_transcript_usa_youtube_clippings_path_si_esta(mock_extraer, db, youtube_config, tmp_path):
    """D27: la clave opcional youtube_clippings_path manda sobre <vault>/../Clippings."""
    mock_extraer.return_value = {
        'titulo': 't', 'idioma': 'es', 'subtitulos': 'manual', 'ruta_md': 'x.md', 'palabras': 1, 'id': 'x',
    }
    from core.tool_executor import ToolExecutor
    config = {**youtube_config, 'youtube_clippings_path': str(tmp_path / "otros_clippings")}
    ToolExecutor(db, '99999', config=config).execute("youtube_transcript", {"url": "u", "idioma": "es"})
    assert str(mock_extraer.call_args[0][3]) == str(tmp_path / "otros_clippings")
