"""
ToolExecutor — maps Orchestrator tool names to module method calls.

Each execute() call instantiates the relevant module, calls the method,
and returns raw data (the 'data' field from module responses, or the
direct return value for list modules).
"""
from datetime import date
from logcentral_client import get_logger

logger = get_logger("sebastian")
from modules.calendar import CalendarModule
from modules.weather import WeatherModule
from modules.inventory import InventoryModule
from modules.item_list import ItemListModule
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
            "calendar_add_event":        self._calendar_add_event,
            "calendar_remove_event":     self._calendar_remove_event,
            "calendar_update_event":     self._calendar_update_event,
            "calendar_add_note":         self._calendar_add_note,
            "calendar_get_tickets":      self._calendar_get_tickets,
            "calendar_clear_tickets":    self._calendar_clear_tickets,
            # Weather
            "weather_get":               self._weather_get,
            "weather_forecast":          self._weather_forecast,
            "weather_forecast_for_date": self._weather_forecast_for_date,
            # Inventory
            "inventory_list":            self._inventory_list,
            "inventory_check_low_stock": self._inventory_check_low_stock,
            "inventory_add":             self._inventory_add,
            "inventory_remove":          self._inventory_remove,
            "inventory_set_quantity":    self._inventory_set_quantity,
            "inventory_update_quantity": self._inventory_update_quantity,
            # Lists (generic)
            "shopping_list":    self._list_items,   # backward-compatible alias
            "list_items":       self._list_items,
            "list_add_item":    self._list_add_item,
            "list_remove_item": self._list_remove_item,
            "list_clear":       self._list_clear,
            # Notes
            "notes_search":              self._notes_search,
            "notes_get":                 self._notes_get,
            "notes_create":              self._notes_create,
            "notes_append":              self._notes_append,
            "notes_add_tag":             self._notes_add_tag,
            "notes_remove_tag":          self._notes_remove_tag,
            "notes_delete":              self._notes_delete,
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

    def _calendar_add_event(self, inputs: dict):
        module = CalendarModule(self._db, self._user_id)
        event_date = date.fromisoformat(inputs['date']) if inputs.get('date') else None
        return module.add_event(
            title=inputs['title'],
            event_date=event_date,
            event_time=inputs.get('time'),
            all_day=inputs.get('all_day', False),
            recurrence_rule=inputs.get('recurrence_rule'),
        )

    def _calendar_remove_event(self, inputs: dict):
        module = CalendarModule(self._db, self._user_id)
        event_date = date.fromisoformat(inputs['date']) if inputs.get('date') else None
        return module.remove_event(title=inputs['title'], event_date=event_date)

    def _calendar_update_event(self, inputs: dict):
        module = CalendarModule(self._db, self._user_id)
        event_date = date.fromisoformat(inputs['date']) if inputs.get('date') else None
        new_date = date.fromisoformat(inputs['new_date']) if inputs.get('new_date') else None
        return module.update_event(
            title=inputs['title'],
            event_date=event_date,
            new_title=inputs.get('new_title'),
            new_date=new_date,
            new_time=inputs.get('new_time'),
            # new_all_day not exposed to agent in v2
        )

    def _calendar_add_note(self, inputs: dict):
        module = CalendarModule(self._db, self._user_id)
        return module.add_note(event_id=inputs['event_id'], note_text=inputs['note_text'])

    def _calendar_get_tickets(self, inputs: dict):
        module = CalendarModule(self._db, self._user_id)
        notes = module.get_event_notes(inputs['event_id'])
        if not notes:
            return []
        return notes.get('tickets', [])

    def _calendar_clear_tickets(self, inputs: dict):
        module = CalendarModule(self._db, self._user_id)
        return module.clear_tickets(inputs['event_id'])

    # ── Weather ───────────────────────────────────────────────────────────────

    def _weather_get(self, inputs: dict):
        module = WeatherModule(self._db, self._user_id)
        response = module.get_weather(inputs.get('city'))
        return response.get('result', '')

    def _weather_forecast(self, inputs: dict):
        module = WeatherModule(self._db, self._user_id)
        response = module.get_forecast(
            city=inputs.get('city'),
            time_window=inputs.get('time_window', 'week'),
            days=inputs.get('days')
        )
        return response.get('result', '')

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

    def _inventory_add(self, inputs: dict):
        module = InventoryModule(self._db, self._user_id, 'inventario', 'inventory')
        return module.add(
            item_name=inputs['item_name'],
            quantity=inputs.get('quantity', 1),
            unit=inputs.get('unit', 'unidades'),
            threshold=inputs.get('threshold', 2),
        )

    def _inventory_remove(self, inputs: dict):
        module = InventoryModule(self._db, self._user_id, 'inventario', 'inventory')
        removed = module.remove(inputs['item_name'])
        return {'status': 'removed'} if removed else {'status': 'not_found'}

    def _inventory_set_quantity(self, inputs: dict):
        module = InventoryModule(self._db, self._user_id, 'inventario', 'inventory')
        return module.set_quantity(inputs['item_name'], inputs['quantity'])

    def _inventory_update_quantity(self, inputs: dict):
        module = InventoryModule(self._db, self._user_id, 'inventario', 'inventory')
        return module.update_quantity(inputs['item_name'], inputs['delta'])

    # ── Lists (generic) ───────────────────────────────────────────────────────

    def _list_items(self, inputs: dict):
        # Default only reached via the 'shopping_list' backward-compat alias (no list_name supplied)
        list_name = inputs.get('list_name', 'compra')
        module = ItemListModule(self._db, self._user_id, list_name, 'shopping')
        return module.list_all()

    def _list_add_item(self, inputs: dict):
        module = ItemListModule(self._db, self._user_id, inputs['list_name'], 'shopping')
        return module.add(
            item_name=inputs['item_name'],
            quantity=inputs.get('quantity', 1),
        )

    def _list_remove_item(self, inputs: dict):
        module = ItemListModule(self._db, self._user_id, inputs['list_name'], 'shopping')
        removed = module.remove(inputs['item_name'])
        return {'status': 'removed'} if removed else {'status': 'not_found'}

    def _list_clear(self, inputs: dict):
        module = ItemListModule(self._db, self._user_id, inputs['list_name'], 'shopping')
        count = module.clear_all()
        return {'status': 'cleared', 'count': count}

    # ── Notes ─────────────────────────────────────────────────────────────────

    def _notes_search(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.search(inputs['query'])

    def _notes_get(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.get(inputs['note_id'])

    def _notes_create(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.create(inputs['content'], inputs.get('tags'))

    def _notes_append(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.append_text(inputs['note_id'], inputs['text'])

    def _notes_add_tag(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.add_tag(inputs['note_id'], inputs['tag'])

    def _notes_remove_tag(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        return module.remove_tag(inputs['note_id'], inputs['tag'])

    def _notes_delete(self, inputs: dict):
        module = NotesModule(self._db, self._user_id)
        deleted = module.delete(inputs['note_id'])
        return {'status': 'deleted'} if deleted else {'status': 'not_found'}
