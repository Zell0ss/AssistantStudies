"""
ToolExecutor — maps Orchestrator tool names to module method calls.

Each execute() call instantiates the relevant module, calls the method,
and returns raw data (the 'data' field from module responses, or the
direct return value for list modules).
"""
from datetime import date
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
            "calendar_search_events":    self._calendar_search_events,
            "calendar_list_events":      self._calendar_list_events,
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
        module = InventoryModule(self._db, self._user_id, 'inventario', 'inventory')
        return module.list_all()

    def _inventory_check_low_stock(self, inputs: dict):
        module = InventoryModule(self._db, self._user_id, 'inventario', 'inventory')
        return module.check_low_stock()

    # ── Shopping ──────────────────────────────────────────────────────────────

    def _shopping_list(self, inputs: dict):
        module = ShoppingModule(self._db, self._user_id, 'compra', 'shopping')
        return module.list_all()

    # ── Notes ─────────────────────────────────────────────────────────────────

    def _notes_search(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.search(inputs['query'])

    def _notes_get(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.get(inputs['note_id'])
