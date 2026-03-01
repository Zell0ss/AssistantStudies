# Orchestrator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a multi-step orchestrator that lets Haiku chain module calls via Anthropic Tool Use to answer compound queries like "¿necesito paraguas al teatro?".

**Architecture:** A new `Orchestrator` class runs a Haiku tool-use loop, executing read-only module methods as tools and feeding results back until Haiku has enough data. Sonnet/Alfred then synthesizes the final Spanish response. The existing router stays as legacy fallback during the transition.

**Tech Stack:** Python 3.11, `anthropic` SDK (already in requirements), MariaDB, existing module classes (CalendarModule, WeatherModule, InventoryModule, ShoppingModule, NotesModule).

---

## Task 1: `WeatherModule.get_forecast_for_date()` — new method

The orchestrator needs a tool that returns weather for a specific date. This method doesn't exist yet; `get_forecast()` returns date ranges.

**Files:**
- Modify: `modules/weather.py` (after `get_forecast()` at line ~276)
- Test: `tests/test_weather_module.py`

**Step 1: Write the failing test**

In `tests/test_weather_module.py`, add to `TestMultiDayForecast`:

```python
def test_get_forecast_for_date_returns_single_day(self, mock_forecast):
    """get_forecast_for_date filters to exactly the requested date."""
    mock_forecast.return_value = self._make_daily(14)
    target = (date.today() + timedelta(days=3)).isoformat()

    result = self.module.get_forecast_for_date(target)

    assert result['success'] is True
    assert result['data']['dates'] == [target]
    assert len(result['data']['temp_max']) == 1

def test_get_forecast_for_date_not_found(self, mock_forecast):
    """get_forecast_for_date returns failure if date not in 14-day window."""
    mock_forecast.return_value = self._make_daily(14)
    far_future = (date.today() + timedelta(days=30)).isoformat()

    result = self.module.get_forecast_for_date(far_future)

    assert result['success'] is False
```

**Step 2: Run to verify failure**

```bash
cd /data/AssistantStudies/sebastian2 && source .venv/bin/activate
pytest tests/test_weather_module.py::TestMultiDayForecast::test_get_forecast_for_date_returns_single_day -v
```
Expected: `FAILED — AttributeError: 'WeatherModule' object has no attribute 'get_forecast_for_date'`

**Step 3: Implement the method**

Add after `get_forecast()` (around line 340 in `modules/weather.py`):

```python
def get_forecast_for_date(self, date_str: str) -> dict:
    """
    Get weather forecast for a specific date (YYYY-MM-DD).

    Fetches a 14-day forecast and filters to the requested date.
    Returns single-day data dict identical in structure to get_forecast() data.
    """
    saved = self._settings.get_weather_location()
    display_name = saved['location']
    lat, lon, country = saved['lat'], saved['lon'], saved['country']

    try:
        data = self._fetch_forecast(lat, lon, days=14)
    except Exception as e:
        logger.error(f"Forecast fetch failed for date {date_str}: {e}")
        return {'success': False, 'result': "No pude obtener la previsión.", 'data': {}}

    if date_str not in data.get('dates', []):
        return {
            'success': False,
            'result': f"La fecha {date_str} está fuera del rango de previsión (14 días).",
            'data': {}
        }

    idx = data['dates'].index(date_str)
    day_data = {k: [v[idx]] if isinstance(v, list) else v for k, v in data.items()}
    return {'success': True, 'result': '', 'data': day_data}
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/test_weather_module.py::TestMultiDayForecast::test_get_forecast_for_date_returns_single_day tests/test_weather_module.py::TestMultiDayForecast::test_get_forecast_for_date_not_found -v
```
Expected: `2 passed`

**Step 5: Run full test suite to verify no regressions**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all previously passing tests still pass.

**Step 6: Commit**

```bash
git add modules/weather.py tests/test_weather_module.py
git commit -m "feat: add WeatherModule.get_forecast_for_date() for orchestrator"
```

---

## Task 2: Tool definitions — `core/tools/`

Define all 11 read-only tools as Anthropic tool dicts. No logic here — just schema declarations.

**Files:**
- Create: `core/tools/__init__.py`
- Create: `core/tools/calendar_tools.py`
- Create: `core/tools/weather_tools.py`
- Create: `core/tools/inventory_tools.py`
- Create: `core/tools/shopping_tools.py`
- Create: `core/tools/notes_tools.py`

**Step 1: Create `core/tools/__init__.py`**

```python
"""Anthropic tool definitions for the Orchestrator."""
from .calendar_tools import CALENDAR_TOOLS
from .weather_tools import WEATHER_TOOLS
from .inventory_tools import INVENTORY_TOOLS
from .shopping_tools import SHOPPING_TOOLS
from .notes_tools import NOTES_TOOLS

ALL_TOOLS = (
    CALENDAR_TOOLS +
    WEATHER_TOOLS +
    INVENTORY_TOOLS +
    SHOPPING_TOOLS +
    NOTES_TOOLS
)
```

**Step 2: Create `core/tools/calendar_tools.py`**

```python
"""Calendar tool definitions for Orchestrator."""

CALENDAR_TOOLS = [
    {
        "name": "calendar_search_events",
        "description": (
            "Busca eventos en el calendario del usuario por texto en el título. "
            "Devuelve una lista de eventos con id, título, fecha (YYYY-MM-DD) y hora (HH:MM o null si todo el día). "
            "Útil para encontrar cuándo tiene algo el usuario (teatro, dentista, vuelo, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar en el título del evento. Ejemplo: 'teatro', 'dentista', 'vuelo'."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "calendar_list_events",
        "description": (
            "Lista los eventos del calendario en un rango de tiempo. "
            "Devuelve todos los eventos del período con id, título, fecha y hora."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_window": {
                    "type": "string",
                    "description": (
                        "Rango de tiempo. Valores válidos: "
                        "'today' (hoy), 'tomorrow' (mañana), 'week' (esta semana), "
                        "'month' (este mes), 'weekend' (próximo fin de semana)."
                    ),
                    "enum": ["today", "tomorrow", "week", "month", "weekend"]
                }
            },
            "required": ["time_window"]
        }
    },
    {
        "name": "calendar_find_by_datetime",
        "description": (
            "Busca un evento por fecha y hora exactas. "
            "Útil cuando el usuario menciona 'la cita de las 19:00 del miércoles'. "
            "Devuelve el evento si existe, o null."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD. Ejemplo: '2026-03-05'."
                },
                "time": {
                    "type": "string",
                    "description": "Hora en formato HH:MM (24h). Ejemplo: '19:00'."
                }
            },
            "required": ["date", "time"]
        }
    }
]
```

**Step 3: Create `core/tools/weather_tools.py`**

```python
"""Weather tool definitions for Orchestrator."""

WEATHER_TOOLS = [
    {
        "name": "weather_get",
        "description": (
            "Obtiene el tiempo actual para la ubicación guardada del usuario o una ciudad específica. "
            "Devuelve temperatura actual, máxima/mínima del día, probabilidad de lluvia, "
            "velocidad de viento y rachas. Usar para 'qué tiempo hace hoy'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": (
                        "Nombre de la ciudad. Si es null o no se especifica, "
                        "usa la ubicación guardada del usuario."
                    )
                }
            },
            "required": []
        }
    },
    {
        "name": "weather_forecast",
        "description": (
            "Obtiene la previsión meteorológica para varios días. "
            "Devuelve fechas, temperaturas, probabilidad de lluvia y viento para cada día. "
            "Usar para 'qué tiempo hace esta semana' o 'previsión del fin de semana'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_window": {
                    "type": "string",
                    "description": "Período: 'week' (7 días), 'weekend' (sábado y domingo próximos), 'tomorrow' (mañana).",
                    "enum": ["week", "weekend", "tomorrow"]
                },
                "city": {
                    "type": "string",
                    "description": "Ciudad. Si no se especifica, usa la ubicación guardada."
                }
            },
            "required": ["time_window"]
        }
    },
    {
        "name": "weather_forecast_for_date",
        "description": (
            "Obtiene la previsión meteorológica para una fecha concreta (hasta 14 días en el futuro). "
            "Devuelve temperatura máxima/mínima, probabilidad de lluvia y rachas de viento para ese día. "
            "Usar cuando ya se sabe la fecha exacta de un evento y se quiere saber el tiempo ese día."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD. Ejemplo: '2026-03-05'."
                }
            },
            "required": ["date"]
        }
    }
]
```

**Step 4: Create `core/tools/inventory_tools.py`**

```python
"""Inventory tool definitions for Orchestrator."""

INVENTORY_TOOLS = [
    {
        "name": "inventory_list",
        "description": (
            "Lista todos los artículos del inventario del usuario con sus cantidades y unidades. "
            "Útil para saber qué tiene en casa, cuánto queda de algo, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "inventory_check_low_stock",
        "description": (
            "Devuelve los artículos del inventario que están por debajo de su umbral mínimo. "
            "Útil para 'qué me falta' o 'qué tengo que comprar'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]
```

**Step 5: Create `core/tools/shopping_tools.py`**

```python
"""Shopping tool definitions for Orchestrator."""

SHOPPING_TOOLS = [
    {
        "name": "shopping_list",
        "description": (
            "Lista todos los artículos de la lista de compra del usuario. "
            "Útil para saber qué hay pendiente de comprar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]
```

**Step 6: Create `core/tools/notes_tools.py`**

```python
"""Notes tool definitions for Orchestrator."""

NOTES_TOOLS = [
    {
        "name": "notes_search",
        "description": (
            "Busca en las notas del usuario por contenido o texto libre. "
            "Devuelve lista de notas con id, contenido y tags. "
            "Útil para recordar información guardada previamente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar en el contenido de las notas."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "notes_get",
        "description": (
            "Obtiene una nota específica por su ID numérico. "
            "Devuelve el contenido completo y los tags."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "ID numérico de la nota."
                }
            },
            "required": ["note_id"]
        }
    }
]
```

**Step 7: Verify imports work**

```bash
cd /data/AssistantStudies/sebastian2 && source .venv/bin/activate
python -c "from core.tools import ALL_TOOLS; print(f'{len(ALL_TOOLS)} tools loaded')"
```
Expected: `11 tools loaded`

**Step 8: Commit**

```bash
git add core/tools/
git commit -m "feat: add orchestrator tool definitions (11 read-only tools)"
```

---

## Task 3: `ToolExecutor` — maps tool names to module calls

This class receives a tool name + input dict, instantiates the right module, calls the right method, and returns raw data.

**Files:**
- Create: `core/tool_executor.py`
- Test: `tests/test_tool_executor.py`

**Step 1: Write failing tests**

Create `tests/test_tool_executor.py`:

```python
"""Tests for ToolExecutor — tool name → module method dispatch."""
import pytest
import sqlite3
from unittest.mock import MagicMock, patch


class TestToolExecutor:
    """Tests using SQLite in-memory DB with same wrapper as test_item_list_module."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create minimal in-memory DB and mock user_id."""
        import sqlite3
        from tests.test_item_list_module import MySQLCompatibleConnection

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
        self.db = MySQLCompatibleConnection(conn)
        self.user_id = '99999'

    def _make_executor(self):
        from core.tool_executor import ToolExecutor
        return ToolExecutor(self.db, self.user_id)

    def test_unknown_tool_raises(self):
        """Unknown tool name raises ValueError."""
        executor = self._make_executor()
        with pytest.raises(ValueError, match="Unknown tool"):
            executor.execute("does_not_exist", {})

    def test_inventory_list_returns_list(self):
        """inventory_list returns a list (possibly empty)."""
        executor = self._make_executor()
        result = executor.execute("inventory_list", {})
        assert isinstance(result, list)

    def test_shopping_list_returns_list(self):
        """shopping_list returns a list."""
        executor = self._make_executor()
        result = executor.execute("shopping_list", {})
        assert isinstance(result, list)

    def test_inventory_check_low_stock_returns_list(self):
        """inventory_check_low_stock returns a list."""
        executor = self._make_executor()
        result = executor.execute("inventory_check_low_stock", {})
        assert isinstance(result, list)

    @patch('modules.calendar.CalendarModule.search_events')
    def test_calendar_search_events_dispatches(self, mock_search):
        """calendar_search_events calls CalendarModule.search_events."""
        mock_search.return_value = [{'event_id': 1, 'title': 'Teatro', 'date': '2026-03-05'}]
        executor = self._make_executor()
        result = executor.execute("calendar_search_events", {"query": "teatro"})
        mock_search.assert_called_once_with("teatro")
        assert result[0]['title'] == 'Teatro'

    @patch('modules.weather.WeatherModule.get_weather')
    def test_weather_get_dispatches(self, mock_weather):
        """weather_get calls WeatherModule.get_weather and returns data field."""
        mock_weather.return_value = {
            'success': True, 'result': 'texto', 'data': {'temp': 15.0}
        }
        executor = self._make_executor()
        result = executor.execute("weather_get", {})
        assert result['temp'] == 15.0

    @patch('modules.weather.WeatherModule.get_forecast_for_date')
    def test_weather_forecast_for_date_dispatches(self, mock_forecast):
        """weather_forecast_for_date calls correct method."""
        mock_forecast.return_value = {
            'success': True, 'result': '', 'data': {'dates': ['2026-03-05'], 'precip_prob': [70]}
        }
        executor = self._make_executor()
        result = executor.execute("weather_forecast_for_date", {"date": "2026-03-05"})
        mock_forecast.assert_called_once_with("2026-03-05")
        assert result['precip_prob'] == [70]
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_tool_executor.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.tool_executor'`

**Step 3: Implement `core/tool_executor.py`**

```python
"""
ToolExecutor — maps Orchestrator tool names to module method calls.

Each execute() call instantiates the relevant module, calls the method,
and returns raw data (the 'data' field from module responses, or the
direct return value for list modules).
"""
import json
from loguru import logger
from modules.calendar import CalendarModule
from modules.weather import WeatherModule
from modules.inventory import InventoryModule
from modules.shopping import ShoppingModule
from modules.notes import NotesModule


class ToolExecutor:
    """Executes tool calls by dispatching to the appropriate module method."""

    def __init__(self, db, user_id: str):
        self._db = db
        self._user_id = user_id

    def execute(self, tool_name: str, tool_input: dict):
        """
        Execute a named tool with the given inputs.

        Returns raw data suitable for inclusion in a tool_result block.
        Raises ValueError for unknown tool names.
        """
        logger.debug(f"Executing tool: {tool_name} inputs={tool_input}")

        dispatch = {
            # Calendar
            "calendar_search_events":   self._calendar_search_events,
            "calendar_list_events":     self._calendar_list_events,
            "calendar_find_by_datetime": self._calendar_find_by_datetime,
            # Weather
            "weather_get":               self._weather_get,
            "weather_forecast":          self._weather_forecast,
            "weather_forecast_for_date": self._weather_forecast_for_date,
            # Inventory
            "inventory_list":            self._inventory_list,
            "inventory_check_low_stock": self._inventory_check_low_stock,
            # Shopping
            "shopping_list":             self._shopping_list,
            # Notes
            "notes_search":              self._notes_search,
            "notes_get":                 self._notes_get,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        result = handler(tool_input)
        logger.debug(f"Tool {tool_name} result: {str(result)[:200]}")
        return result

    # ── Calendar ──────────────────────────────────────────────────────────────

    def _calendar_search_events(self, inputs: dict):
        module = CalendarModule(self._db, self._user_id)
        return module.search_events(inputs['query'])

    def _calendar_list_events(self, inputs: dict):
        module = CalendarModule(self._db, self._user_id)
        return module.list_events(inputs['time_window'])

    def _calendar_find_by_datetime(self, inputs: dict):
        from datetime import date
        module = CalendarModule(self._db, self._user_id)
        event_date = date.fromisoformat(inputs['date'])
        return module.find_by_datetime(event_date, inputs['time'])

    # ── Weather ───────────────────────────────────────────────────────────────

    def _weather_get(self, inputs: dict):
        module = WeatherModule(self._db, self._user_id)
        response = module.get_weather(inputs.get('city'))
        return response.get('data', {})

    def _weather_forecast(self, inputs: dict):
        module = WeatherModule(self._db, self._user_id)
        response = module.get_forecast(
            city=inputs.get('city'),
            time_window=inputs.get('time_window', 'week'),
            days=inputs.get('days')
        )
        return response.get('data', {})

    def _weather_forecast_for_date(self, inputs: dict):
        module = WeatherModule(self._db, self._user_id)
        response = module.get_forecast_for_date(inputs['date'])
        return response.get('data', {})

    # ── Inventory ─────────────────────────────────────────────────────────────

    def _inventory_list(self, inputs: dict):
        module = InventoryModule(self._db, self._user_id, 'inventario')
        return module.list_all()

    def _inventory_check_low_stock(self, inputs: dict):
        module = InventoryModule(self._db, self._user_id, 'inventario')
        return module.check_low_stock()

    # ── Shopping ──────────────────────────────────────────────────────────────

    def _shopping_list(self, inputs: dict):
        module = ShoppingModule(self._db, self._user_id, 'compra')
        return module.list_all()

    # ── Notes ─────────────────────────────────────────────────────────────────

    def _notes_search(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.search(inputs['query'])

    def _notes_get(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.get(inputs['note_id'])
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/test_tool_executor.py -v
```
Expected: all tests pass.

**Step 5: Run full suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: no regressions.

**Step 6: Commit**

```bash
git add core/tool_executor.py tests/test_tool_executor.py
git commit -m "feat: add ToolExecutor — tool name to module dispatch"
```

---

## Task 4: `Orchestrator` — the tool use loop

The main class: calls Haiku with tools, runs the loop, collects results, delegates synthesis to Sonnet/Alfred.

**Files:**
- Create: `core/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write failing tests**

Create `tests/test_orchestrator.py`:

```python
"""Tests for Orchestrator — tool use loop."""
import json
import pytest
from unittest.mock import MagicMock, patch, call
import sqlite3
from tests.test_item_list_module import MySQLCompatibleConnection


@pytest.fixture
def db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE user_settings (
            user_id TEXT PRIMARY KEY,
            sprite_skin TEXT DEFAULT 'default',
            weather_location TEXT DEFAULT 'Madrid',
            weather_lat REAL DEFAULT 40.4168,
            weather_lon REAL DEFAULT -3.7038,
            weather_country TEXT DEFAULT 'ES'
        );
        INSERT INTO user_settings VALUES ('99999','default','Madrid',40.4168,-3.7038,'ES');
    ''')
    conn.commit()
    yield MySQLCompatibleConnection(conn)


def _make_text_response(text):
    """Minimal mock Anthropic response with just text."""
    msg = MagicMock()
    msg.stop_reason = 'end_turn'
    content_block = MagicMock()
    content_block.type = 'text'
    content_block.text = text
    msg.content = [content_block]
    return msg


def _make_tool_use_response(tool_name, tool_id, tool_input):
    """Mock Anthropic response requesting a tool call."""
    msg = MagicMock()
    msg.stop_reason = 'tool_use'
    content_block = MagicMock()
    content_block.type = 'tool_use'
    content_block.name = tool_name
    content_block.id = tool_id
    content_block.input = tool_input
    msg.content = [content_block]
    return msg


class TestOrchestrator:

    @patch('core.orchestrator.Anthropic')
    def test_simple_conversation_no_tools(self, mock_anthropic_cls, db):
        """When Haiku returns text without tools, Alfred responds directly."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call: planner (Haiku) returns text with no tool use
        # Second call: synthesizer (Sonnet) called with context
        mock_client.messages.create.side_effect = [
            _make_text_response("El usuario saluda"),
            _make_text_response("Buenos días, señor."),
        ]

        from core.orchestrator import Orchestrator
        orch = Orchestrator(db, '99999')
        result = orch.handle("Hola")

        assert "Buenos días" in result

    @patch('core.orchestrator.Anthropic')
    @patch('core.tool_executor.ToolExecutor.execute')
    def test_single_tool_call_then_synthesis(self, mock_execute, mock_anthropic_cls, db):
        """Tool use block triggers executor, result feeds back, Sonnet synthesizes."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_execute.return_value = [
            {'event_id': 42, 'title': 'Teatro', 'date': '2026-03-05', 'time': '19:30'}
        ]

        mock_client.messages.create.side_effect = [
            _make_tool_use_response('calendar_search_events', 'tool_1', {'query': 'teatro'}),
            _make_text_response("end_turn after tool"),
            _make_text_response("El teatro es el miércoles a las 19:30, señor."),
        ]

        from core.orchestrator import Orchestrator
        orch = Orchestrator(db, '99999')
        result = orch.handle("¿cuándo es el teatro?")

        mock_execute.assert_called_once_with('calendar_search_events', {'query': 'teatro'})
        assert "teatro" in result.lower()

    @patch('core.orchestrator.Anthropic')
    def test_max_iterations_respected(self, mock_anthropic_cls, db):
        """Loop stops after MAX_ITERATIONS even if model keeps requesting tools."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Always returns a tool_use (infinite loop scenario)
        tool_response = _make_tool_use_response(
            'inventory_list', 'tool_1', {}
        )
        final_text = _make_text_response("Suficiente, señor.")
        # After MAX_ITERATIONS tool calls, the synthesizer is called
        mock_client.messages.create.side_effect = (
            [tool_response] * 8 + [final_text]
        )

        with patch('core.tool_executor.ToolExecutor.execute', return_value=[]):
            from core.orchestrator import Orchestrator
            orch = Orchestrator(db, '99999')
            result = orch.handle("test infinite loop")

        # Should not raise; synthesizer called eventually
        assert isinstance(result, str)

    @patch('core.orchestrator.Anthropic')
    def test_tool_executor_error_returns_error_message(self, mock_anthropic_cls, db):
        """If tool execution fails, error is surfaced gracefully."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_client.messages.create.side_effect = [
            _make_tool_use_response('calendar_search_events', 'tool_1', {'query': 'x'}),
            _make_text_response("Lo siento señor."),
        ]

        with patch('core.tool_executor.ToolExecutor.execute', side_effect=Exception("DB down")):
            from core.orchestrator import Orchestrator
            orch = Orchestrator(db, '99999')
            result = orch.handle("busca algo")

        assert isinstance(result, str)
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_orchestrator.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.orchestrator'`

**Step 3: Implement `core/orchestrator.py`**

```python
"""
Orchestrator — multi-step query handler using Anthropic Tool Use.

Flow:
1. Haiku receives the user message + all tool definitions.
2. If Haiku selects tools, ToolExecutor calls the relevant module methods.
3. Tool results are fed back to Haiku (tool_result blocks).
4. Loop continues until stop_reason=end_turn or MAX_ITERATIONS reached.
5. Sonnet/Alfred synthesizes a Spanish response from collected data.
"""
import json
from loguru import logger
from anthropic import Anthropic
from core.tools import ALL_TOOLS
from core.tool_executor import ToolExecutor
from utils.config import get_config

_MAX_ITERATIONS = 8

_PLANNER_SYSTEM = """Eres el núcleo de razonamiento de Sebastian, asistente personal.
Tu único trabajo es decidir qué herramientas usar para responder la pregunta del usuario.
Usa las herramientas necesarias para reunir la información. No respondas al usuario directamente.
Cuando tengas toda la información, devuelve exactamente el texto: DONE"""

_ALFRED_SYSTEM = """Eres Sebastian, el asistente personal de tu señor.
Tu estilo es el de Alfred Pennyworth: servicial, eficiente, con flema británica.
Eres discreto — no te extiendes innecesariamente, mides cada palabra.
Nundes preguntas más de lo estrictamente necesario.
Respondes siempre en español.
Si el contexto incluye datos de herramientas, úsalos para dar una respuesta precisa y útil."""


class Orchestrator:
    """Handles any user message by orchestrating module tools via Haiku + Alfred synthesis."""

    def __init__(self, db, user_id: str):
        self._db = db
        self._user_id = user_id
        config = get_config()
        self._client = Anthropic(api_key=config['anthropic_apikey'])
        self._executor = ToolExecutor(db, user_id)

    def handle(self, user_message: str) -> str:
        """
        Process a user message and return the final Spanish response.

        Args:
            user_message: Raw text from the user

        Returns:
            Alfred-style Spanish response string
        """
        messages = [{"role": "user", "content": user_message}]
        tool_results_summary = []

        for iteration in range(_MAX_ITERATIONS):
            response = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=_PLANNER_SYSTEM,
                tools=ALL_TOOLS,
                messages=messages
            )

            # Collect any text blocks from this response
            text_blocks = [b for b in response.content if b.type == 'text']
            tool_blocks = [b for b in response.content if b.type == 'tool_use']

            if response.stop_reason == 'end_turn' or not tool_blocks:
                # Planner is done — move to synthesis
                break

            # Execute each tool call
            tool_results = []
            for block in tool_blocks:
                try:
                    raw = self._executor.execute(block.name, block.input)
                    result_content = json.dumps(raw, default=str, ensure_ascii=False)
                    tool_results_summary.append({
                        "tool": block.name,
                        "input": block.input,
                        "result": raw
                    })
                    logger.info(f"Tool {block.name} → {result_content[:150]}")
                except Exception as e:
                    logger.error(f"Tool {block.name} failed: {e}")
                    result_content = json.dumps({"error": str(e)})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_content
                })

            # Add assistant turn + tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        # Synthesize final response with Alfred/Sonnet
        return self._synthesize(user_message, tool_results_summary)

    def _synthesize(self, user_message: str, tool_results: list) -> str:
        """Call Sonnet to synthesize a Spanish Alfred-style response."""
        if tool_results:
            context_lines = []
            for item in tool_results:
                context_lines.append(
                    f"[{item['tool']}({json.dumps(item['input'], ensure_ascii=False)})]:\n"
                    f"{json.dumps(item['result'], default=str, ensure_ascii=False)}"
                )
            context = "\n\n".join(context_lines)
            synthesis_prompt = (
                f"El usuario preguntó: {user_message}\n\n"
                f"Datos recogidos:\n{context}\n\n"
                f"Responde al usuario en español, de forma concisa y útil."
            )
        else:
            synthesis_prompt = user_message

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=_ALFRED_SYSTEM,
            messages=[{"role": "user", "content": synthesis_prompt}]
        )
        return response.content[0].text.strip()
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/test_orchestrator.py -v
```
Expected: all tests pass.

**Step 5: Run full suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: no regressions.

**Step 6: Commit**

```bash
git add core/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add Orchestrator — Haiku tool use loop + Sonnet synthesis"
```

---

## Task 5: Wire Orchestrator into `handlers.py`

Replace the `parser → router` path in `handle_text` with `Orchestrator`. Keep the old router as fallback.

**Files:**
- Modify: `bot/handlers.py`

**Step 1: Read the current `handle_text` function**

The relevant section is `bot/handlers.py:204-299`. The key block to replace is lines 224-231:

```python
# Parse intent
parsed = parser.parse(message.text)
parsed['_raw_message'] = message.text
logger.debug(f"Parsed intent: {parsed}")

# Route to module
router = ModuleRouter(str(message.chat.id))
result = router.route(parsed)
logger.debug(f"Router result: {result}")
```

**Step 2: Add Orchestrator import**

At the top of `bot/handlers.py`, after existing imports, add:

```python
from core.orchestrator import Orchestrator
```

**Step 3: Replace the parse → route block**

Replace lines 224-232 (the parse+route block) with:

```python
# Orchestrate via tool use loop
conn = get_connection()
orchestrator = Orchestrator(conn, str(message.chat.id))
response_text = orchestrator.handle(message.text)

# Send response directly (Orchestrator produces final text)
_send_markdown(bot, message.chat.id, response_text)

# Send sprite
conn2 = get_connection()
settings2 = UserSettingsModule(conn2, str(message.chat.id))
user_skin = settings2.get_sprite_skin()
sprite_path = formatter.get_sprite_path(context={'module': 'unknown', 'action': None}, user_skin=user_skin)
try:
    with open(sprite_path, 'rb') as sprite:
        bot.send_document(chat_id=message.chat.id, document=sprite, disable_notification=True)
except FileNotFoundError:
    pass
return
```

> **Note:** The Orchestrator returns the final text directly — no need for the formatter's caption formatting. The sprite is still sent as before for consistency. The ticket image sending block (lines 260-279) is preserved below this in the old code but will be dead code for now — ticket display will be handled in a later task when write tools are added.

**Step 4: Manual smoke test**

Start the bot locally or send a test message via a test script. Verify a simple query works end-to-end. Check logs for `Executing tool:` entries on compound queries.

```bash
cd /data/AssistantStudies/sebastian2 && source .venv/bin/activate
python -c "
from db.connection import get_connection
from core.orchestrator import Orchestrator
db = get_connection()
orch = Orchestrator(db, '12345')
print(orch.handle('hola'))
"
```
Expected: Alfred-style greeting in Spanish, no exceptions.

**Step 5: Commit**

```bash
git add bot/handlers.py
git commit -m "feat: wire Orchestrator into handlers.py as primary message path"
```

---

## Task 6: End-to-end test — "¿paraguas al teatro?"

Verify the full compound-query flow works with mocked external APIs.

**Files:**
- Test: `tests/test_orchestrator.py` (add to existing file)

**Step 1: Add the end-to-end test**

Add to `tests/test_orchestrator.py`:

```python
class TestOrchestratorEndToEnd:
    """Full flow tests with mocked Anthropic + mocked module calls."""

    @pytest.fixture
    def db(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.executescript('''
            CREATE TABLE user_settings (
                user_id TEXT PRIMARY KEY,
                sprite_skin TEXT DEFAULT 'default',
                weather_location TEXT DEFAULT 'Madrid',
                weather_lat REAL DEFAULT 40.4168,
                weather_lon REAL DEFAULT -3.7038,
                weather_country TEXT DEFAULT 'ES'
            );
            INSERT INTO user_settings VALUES
                ('99999','default','Madrid',40.4168,-3.7038,'ES');
        ''')
        conn.commit()
        yield MySQLCompatibleConnection(conn)

    @patch('core.orchestrator.Anthropic')
    @patch('core.tool_executor.ToolExecutor.execute')
    def test_paraguas_al_teatro_flow(self, mock_execute, mock_anthropic_cls, db):
        """
        Full compound query: search calendar for 'teatro', get weather for that date.
        Verifies Orchestrator calls both tools and includes weather data in synthesis.
        """
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Tool execution side effects
        def execute_side_effect(tool_name, tool_input):
            if tool_name == 'calendar_search_events':
                return [{'event_id': 42, 'title': 'Teatro Jovellanos',
                         'date': '2026-03-05', 'time': '19:30', 'all_day': False}]
            if tool_name == 'weather_forecast_for_date':
                return {'dates': ['2026-03-05'], 'precip_prob': [75],
                        'temp_max': [14.0], 'temp_min': [9.0], 'windgusts': [40.0]}
            return []

        mock_execute.side_effect = execute_side_effect

        # Planner: first requests calendar search, then weather, then done
        mock_client.messages.create.side_effect = [
            _make_tool_use_response('calendar_search_events', 't1', {'query': 'teatro'}),
            _make_tool_use_response('weather_forecast_for_date', 't2', {'date': '2026-03-05'}),
            _make_text_response('DONE'),
            # Synthesizer
            _make_text_response(
                'Sí señor. El Teatro Jovellanos es el miércoles a las 19:30. '
                'Hay un 75% de probabilidad de lluvia. ☂️ Lleve paraguas.'
            ),
        ]

        from core.orchestrator import Orchestrator
        orch = Orchestrator(db, '99999')
        result = orch.handle("¿necesito llevar paraguas al teatro?")

        # Both tools were called
        calls = [c[0][0] for c in mock_execute.call_args_list]
        assert 'calendar_search_events' in calls
        assert 'weather_forecast_for_date' in calls

        # Response mentions rain
        assert 'paraguas' in result.lower() or '75%' in result or 'lluvia' in result
```

**Step 2: Run the test**

```bash
pytest tests/test_orchestrator.py::TestOrchestratorEndToEnd -v
```
Expected: `1 passed`

**Step 3: Run full suite one final time**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all tests pass, no regressions.

**Step 4: Final commit**

```bash
git add tests/test_orchestrator.py
git commit -m "test: add end-to-end orchestrator test (paraguas al teatro flow)"
```

---

## Summary of changes

| File | Type | Purpose |
|------|------|---------|
| `modules/weather.py` | Modified | Add `get_forecast_for_date()` |
| `core/tools/__init__.py` | New | Aggregate all tool defs |
| `core/tools/calendar_tools.py` | New | 3 calendar tool defs |
| `core/tools/weather_tools.py` | New | 3 weather tool defs |
| `core/tools/inventory_tools.py` | New | 2 inventory tool defs |
| `core/tools/shopping_tools.py` | New | 1 shopping tool def |
| `core/tools/notes_tools.py` | New | 2 notes tool defs |
| `core/tool_executor.py` | New | Tool name → module dispatch |
| `core/orchestrator.py` | New | Haiku loop + Sonnet synthesis |
| `bot/handlers.py` | Modified | Route to Orchestrator |
| `tests/test_weather_module.py` | Modified | 2 new tests |
| `tests/test_tool_executor.py` | New | 7 executor tests |
| `tests/test_orchestrator.py` | New | 5 orchestrator tests |

Legacy: `core/haiku_parser.py` and `core/router.py` unchanged — remain as reference until Orchestrator is validated in production.
