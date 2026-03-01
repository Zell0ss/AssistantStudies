# Write Tools v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 15 write (mutating) tool definitions and their ToolExecutor dispatchers so the Orchestrator can create, update and delete data across Calendar, Inventory, Lists and Notes modules.

**Architecture:** Tool definitions are added to the existing `core/tools/*.py` files alongside the read tools. ToolExecutor gains 15 new private methods wired into the dispatch dict. The Orchestrator, handlers, and modules are not modified — the change is purely in the tool layer.

**Tech Stack:** Python 3.11, Anthropic Tool Use API (dict-based tool defs), existing module classes (CalendarModule, InventoryModule, ItemListModule, NotesModule).

---

## Context for the implementer

### Working directory
`/data/AssistantStudies/sebastian2/`

### Run tests with
```bash
source .venv/bin/activate && pytest tests/ -q
```

### Currently 242 tests pass. Keep them green after every commit.

### Key files
- `core/tools/calendar_tools.py` — add calendar write tool defs here
- `core/tools/inventory_tools.py` — add inventory write tool defs here
- `core/tools/shopping_tools.py` — **rename to `list_tools.py`** (generic list tools replace shopping-only)
- `core/tools/notes_tools.py` — add notes write tool defs here
- `core/tools/__init__.py` — update import after rename
- `core/tool_executor.py` — add 15 dispatcher methods + update dispatch dict
- `tests/test_tool_executor.py` — add tests for each new dispatcher

### Module signatures you'll call (already imported in tool_executor.py)

**CalendarModule** (`modules/calendar.py`):
```python
add_event(title, event_date=None, event_time=None, all_day=False,
          recurrence_rule=None, recurrence_end=None) -> dict
# Returns: {'status': 'added', 'message': '...'} or {'status': 'error', ...}

remove_event(title, event_date=None) -> dict
# Returns: {'status': 'removed'|'not_found'|'needs_clarification', 'message': '...'}

update_event(title, event_date=None, new_title=None, new_date=None,
             new_time=None, new_all_day=None) -> dict
# Returns: {'status': 'updated'|'not_found'|'needs_clarification', 'message': '...'}

add_note(event_id, note_text) -> dict
# Returns: {'status': 'updated'|'not_found', 'message': '...'}
```

**InventoryModule** (`modules/inventory.py`):
```python
add(item_name, quantity=1, unit='unidades', threshold=2, notes=None) -> dict
# Returns: {'status': 'added'|'updated', 'item': {...}, 'warning': ...}

remove(item_name) -> bool  # True if removed, False if not found

set_quantity(item_name, quantity) -> dict
# Returns: {'status': 'updated'|'removed'|'error', ...}

update_quantity(item_name, delta) -> dict
# Returns: {'status': 'updated'|'removed'|'not_found', ...}
```

**ItemListModule** (`modules/item_list.py`) — for generic list tools:
```python
# Instantiate with: ItemListModule(db, user_id, list_name, category)
# list_name comes from tool input; category='shopping' is the default for user lists.
add(item_name, quantity=1, unit='unidades') -> dict
# Returns: {'status': 'added'|'updated', 'item': {...}}

remove(item_name) -> bool

clear_all() -> int  # count of removed items
```

**NotesModule** (`modules/notes.py`):
```python
create(content, tags=None) -> dict
# Returns: {'note_id': int, 'status': 'created'}

delete(note_id) -> bool

append_text(note_id, text) -> dict
# Returns: {'status': 'updated'|'not_found'}

add_tag(note_id, tag) -> dict
# Returns: {'status': 'added'|'already_present'|'not_found'}
```

### ItemListModule import
`ItemListModule` is NOT imported in `tool_executor.py` yet. Add:
```python
from modules.item_list import ItemListModule
```

---

## Task 1: Calendar write tools — definitions

**Files:**
- Modify: `core/tools/calendar_tools.py`
- Test: `tests/test_tool_executor.py`

### Step 1: Write 3 failing tests

Add to `tests/test_tool_executor.py`:

```python
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
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/test_tool_executor.py::test_calendar_add_event_dispatches \
       tests/test_tool_executor.py::test_calendar_remove_event_dispatches \
       tests/test_tool_executor.py::test_calendar_update_event_dispatches -v
```
Expected: FAIL with `ValueError: Unknown tool: calendar_add_event`

### Step 3: Add tool definitions to `core/tools/calendar_tools.py`

Append after the existing `CALENDAR_TOOLS` list (before the closing `]`... actually append as a new section):

Replace the entire file with:

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
    },
    # ── Write tools ────────────────────────────────────────────────────────────
    {
        "name": "calendar_add_event",
        "description": (
            "Crea un nuevo evento en el calendario. "
            "Usa esta herramienta cuando el usuario quiera añadir una cita, recordatorio o evento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título del evento. Ejemplo: 'Dentista', 'Teatro Jovellanos'."
                },
                "date": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD. Ejemplo: '2026-03-10'."
                },
                "time": {
                    "type": "string",
                    "description": "Hora en formato HH:MM (24h). Omite si es todo el día. Ejemplo: '10:00'."
                },
                "all_day": {
                    "type": "boolean",
                    "description": "True si el evento es todo el día (sin hora específica)."
                },
                "recurrence_rule": {
                    "type": "string",
                    "description": (
                        "Regla de recurrencia. Valores: 'daily', "
                        "'weekly:MON', 'weekly:MON,WED', 'monthly:15', 'monthly:first-TUE'. "
                        "Omite si es un evento único."
                    )
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "calendar_remove_event",
        "description": (
            "Elimina un evento del calendario por título. "
            "Si hay varios eventos con el mismo nombre, devuelve 'needs_clarification' "
            "con la lista de opciones para que el usuario especifique cuál."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título del evento a eliminar."
                },
                "date": {
                    "type": "string",
                    "description": "Fecha YYYY-MM-DD para desambiguar si hay varios eventos con el mismo nombre."
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "calendar_update_event",
        "description": (
            "Modifica un evento existente: cambia su título, fecha u hora. "
            "Identifica el evento por su título actual (y opcionalmente fecha). "
            "Proporciona solo los campos que cambien."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título actual del evento (para identificarlo)."
                },
                "date": {
                    "type": "string",
                    "description": "Fecha actual YYYY-MM-DD del evento (para desambiguar)."
                },
                "new_title": {
                    "type": "string",
                    "description": "Nuevo título (si se cambia)."
                },
                "new_date": {
                    "type": "string",
                    "description": "Nueva fecha YYYY-MM-DD (si se cambia)."
                },
                "new_time": {
                    "type": "string",
                    "description": "Nueva hora HH:MM (si se cambia)."
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "calendar_add_note",
        "description": (
            "Añade una nota de texto libre a un evento existente (identificado por event_id). "
            "Útil para apuntar 'llevar dinero', 'confirmar cita', etc. junto a un evento. "
            "Usa calendar_search_events o calendar_find_by_datetime primero para obtener el event_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "ID numérico del evento (obtenido con calendar_search_events)."
                },
                "note_text": {
                    "type": "string",
                    "description": "Texto de la nota a añadir al evento."
                }
            },
            "required": ["event_id", "note_text"]
        }
    },
]
```

### Step 4: Add dispatchers to `core/tool_executor.py`

In the dispatch dict, add after `"calendar_find_by_datetime"`:
```python
"calendar_add_event":    self._calendar_add_event,
"calendar_remove_event": self._calendar_remove_event,
"calendar_update_event": self._calendar_update_event,
"calendar_add_note":     self._calendar_add_note,
```

Add private methods after `_calendar_find_by_datetime`:
```python
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
    )

def _calendar_add_note(self, inputs: dict):
    module = CalendarModule(self._db, self._user_id)
    return module.add_note(event_id=inputs['event_id'], note_text=inputs['note_text'])
```

### Step 5: Run tests to verify they pass

```bash
pytest tests/test_tool_executor.py::test_calendar_add_event_dispatches \
       tests/test_tool_executor.py::test_calendar_remove_event_dispatches \
       tests/test_tool_executor.py::test_calendar_update_event_dispatches -v
```
Expected: 3 PASS

### Step 6: Run full suite

```bash
pytest tests/ -q
```
Expected: 245 passed

### Step 7: Commit

```bash
git add core/tools/calendar_tools.py core/tool_executor.py tests/test_tool_executor.py
git commit -m "feat: add calendar write tools (add/remove/update/add_note)"
```

---

## Task 2: Inventory write tools

**Files:**
- Modify: `core/tools/inventory_tools.py`
- Modify: `core/tool_executor.py`
- Test: `tests/test_tool_executor.py`

### Step 1: Write 3 failing tests

Add to `tests/test_tool_executor.py`:

```python
@patch('modules.inventory.InventoryModule.add')
def test_inventory_add_dispatches(mock_add, db):
    """inventory_add calls InventoryModule.add."""
    mock_add.return_value = {'status': 'added', 'item': {'name': 'aceite'}}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("inventory_add", {"item_name": "aceite", "quantity": 2})
    mock_add.assert_called_once()
    assert result['status'] == 'added'


@patch('modules.inventory.InventoryModule.remove')
def test_inventory_remove_dispatches(mock_remove, db):
    """inventory_remove calls InventoryModule.remove."""
    mock_remove.return_value = True
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("inventory_remove", {"item_name": "aceite"})
    mock_remove.assert_called_once_with("aceite")
    assert result is True


@patch('modules.inventory.InventoryModule.set_quantity')
def test_inventory_set_quantity_dispatches(mock_set, db):
    """inventory_set_quantity calls InventoryModule.set_quantity."""
    mock_set.return_value = {'status': 'updated'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("inventory_set_quantity", {"item_name": "aceite", "quantity": 5})
    mock_set.assert_called_once_with("aceite", 5)
    assert result['status'] == 'updated'
```

### Step 2: Run to verify they fail

```bash
pytest tests/test_tool_executor.py::test_inventory_add_dispatches \
       tests/test_tool_executor.py::test_inventory_remove_dispatches \
       tests/test_tool_executor.py::test_inventory_set_quantity_dispatches -v
```
Expected: FAIL with `ValueError: Unknown tool: inventory_add`

### Step 3: Add tool definitions to `core/tools/inventory_tools.py`

Append after `inventory_check_low_stock` (inside `INVENTORY_TOOLS` list):

```python
    # ── Write tools ────────────────────────────────────────────────────────────
    {
        "name": "inventory_add",
        "description": (
            "Añade un artículo al inventario o incrementa su cantidad si ya existe. "
            "Útil cuando el usuario dice 'he comprado aceite' o 'tengo 3 latas de tomate'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo. Ejemplo: 'aceite de oliva', 'pasta'."
                },
                "quantity": {
                    "type": "number",
                    "description": "Cantidad a añadir (default 1)."
                },
                "unit": {
                    "type": "string",
                    "description": "Unidad de medida. Ejemplo: 'litros', 'kg', 'unidades'."
                },
                "threshold": {
                    "type": "number",
                    "description": "Cantidad mínima antes de avisar que hay poco stock (default 2)."
                }
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "inventory_remove",
        "description": (
            "Elimina completamente un artículo del inventario. "
            "Usa cuando el usuario dice 'quita el aceite del inventario' o 'ya no tengo X'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Nombre exacto del artículo a eliminar."
                }
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "inventory_set_quantity",
        "description": (
            "Establece la cantidad exacta de un artículo del inventario. "
            "Usa cuando el usuario dice 'tengo 5 botellas de agua' (cantidad absoluta)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo."
                },
                "quantity": {
                    "type": "number",
                    "description": "Nueva cantidad absoluta."
                }
            },
            "required": ["item_name", "quantity"]
        }
    },
    {
        "name": "inventory_update_quantity",
        "description": (
            "Incrementa o decrementa la cantidad de un artículo del inventario. "
            "Usa cuando el usuario dice 'he usado 2 latas de tomate' (delta negativo) "
            "o 'he comprado 3 más' (delta positivo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo."
                },
                "delta": {
                    "type": "number",
                    "description": "Cambio en cantidad: positivo para añadir, negativo para restar."
                }
            },
            "required": ["item_name", "delta"]
        }
    },
```

### Step 4: Add dispatchers to `core/tool_executor.py`

In the dispatch dict, add after `"inventory_check_low_stock"`:
```python
"inventory_add":             self._inventory_add,
"inventory_remove":          self._inventory_remove,
"inventory_set_quantity":    self._inventory_set_quantity,
"inventory_update_quantity": self._inventory_update_quantity,
```

Add private methods after `_inventory_check_low_stock`:
```python
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
    return module.remove(inputs['item_name'])

def _inventory_set_quantity(self, inputs: dict):
    module = InventoryModule(self._db, self._user_id, 'inventario', 'inventory')
    return module.set_quantity(inputs['item_name'], inputs['quantity'])

def _inventory_update_quantity(self, inputs: dict):
    module = InventoryModule(self._db, self._user_id, 'inventario', 'inventory')
    return module.update_quantity(inputs['item_name'], inputs['delta'])
```

### Step 5: Run new tests

```bash
pytest tests/test_tool_executor.py::test_inventory_add_dispatches \
       tests/test_tool_executor.py::test_inventory_remove_dispatches \
       tests/test_tool_executor.py::test_inventory_set_quantity_dispatches -v
```
Expected: 3 PASS

### Step 6: Run full suite

```bash
pytest tests/ -q
```
Expected: 248 passed

### Step 7: Commit

```bash
git add core/tools/inventory_tools.py core/tool_executor.py tests/test_tool_executor.py
git commit -m "feat: add inventory write tools (add/remove/set_quantity/update_quantity)"
```

---

## Task 3: Generic list tools (replaces shopping_tools.py)

The user wants `list_add_item(list_name, item)` etc. — generic across any list, not just `compra`.

**Files:**
- Create: `core/tools/list_tools.py`
- Delete content of: `core/tools/shopping_tools.py` → replace with re-export for compatibility
- Modify: `core/tools/__init__.py`
- Modify: `core/tool_executor.py`
- Test: `tests/test_tool_executor.py`

**Note:** `ItemListModule` is NOT imported in `tool_executor.py` yet — add the import.

### Step 1: Write 2 failing tests

Add to `tests/test_tool_executor.py`:

```python
@patch('modules.item_list.ItemListModule.add')
def test_list_add_item_dispatches(mock_add, db):
    """list_add_item calls ItemListModule.add for the named list."""
    mock_add.return_value = {'status': 'added', 'item': {'name': 'leche'}}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("list_add_item", {"list_name": "compra", "item_name": "leche"})
    mock_add.assert_called_once()
    assert result['status'] == 'added'


@patch('modules.item_list.ItemListModule.remove')
def test_list_remove_item_dispatches(mock_remove, db):
    """list_remove_item calls ItemListModule.remove."""
    mock_remove.return_value = True
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("list_remove_item", {"list_name": "compra", "item_name": "leche"})
    mock_remove.assert_called_once_with("leche")
```

### Step 2: Run to verify they fail

```bash
pytest tests/test_tool_executor.py::test_list_add_item_dispatches \
       tests/test_tool_executor.py::test_list_remove_item_dispatches -v
```
Expected: FAIL with `ValueError: Unknown tool: list_add_item`

### Step 3: Create `core/tools/list_tools.py`

```python
"""Generic list tool definitions for Orchestrator (shopping, packing, any list)."""

LIST_TOOLS = [
    {
        "name": "list_items",
        "description": (
            "Lista todos los artículos de una lista del usuario (compra, maleta, etc.). "
            "Devuelve los artículos con nombre, cantidad y unidad."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista. Ejemplo: 'compra', 'maleta', 'farmacia'."
                }
            },
            "required": ["list_name"]
        }
    },
    {
        "name": "list_add_item",
        "description": (
            "Añade un artículo a una lista del usuario o incrementa su cantidad si ya existe. "
            "Usa cuando el usuario dice 'apunta leche en la compra' o 'añade camisetas a la maleta'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista. Ejemplo: 'compra', 'maleta'."
                },
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo a añadir."
                },
                "quantity": {
                    "type": "number",
                    "description": "Cantidad (default 1)."
                }
            },
            "required": ["list_name", "item_name"]
        }
    },
    {
        "name": "list_remove_item",
        "description": (
            "Elimina un artículo de una lista del usuario. "
            "Usa cuando el usuario dice 'quita la leche de la compra'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista."
                },
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo a eliminar."
                }
            },
            "required": ["list_name", "item_name"]
        }
    },
    {
        "name": "list_clear",
        "description": (
            "Vacía completamente una lista. "
            "Usa cuando el usuario dice 'borra toda la lista de la compra' o 'vacía la maleta'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista a vaciar."
                }
            },
            "required": ["list_name"]
        }
    },
]
```

### Step 4: Update `core/tools/shopping_tools.py`

Replace its entire content with a re-export that keeps backward compatibility (existing tests may reference `SHOPPING_TOOLS`):

```python
"""Shopping tools — re-exported from list_tools for backward compatibility."""
from .list_tools import LIST_TOOLS

SHOPPING_TOOLS = LIST_TOOLS
```

### Step 5: Update `core/tools/__init__.py`

```python
"""Anthropic tool definitions for the Orchestrator."""
from .calendar_tools import CALENDAR_TOOLS
from .weather_tools import WEATHER_TOOLS
from .inventory_tools import INVENTORY_TOOLS
from .list_tools import LIST_TOOLS
from .notes_tools import NOTES_TOOLS

ALL_TOOLS = (
    CALENDAR_TOOLS +
    WEATHER_TOOLS +
    INVENTORY_TOOLS +
    LIST_TOOLS +
    NOTES_TOOLS
)
```

### Step 6: Add import and dispatchers to `core/tool_executor.py`

Add import at the top (after existing imports):
```python
from modules.item_list import ItemListModule
```

In the dispatch dict, replace `"shopping_list": self._shopping_list` with:
```python
"shopping_list":   self._list_items,  # legacy alias kept
"list_items":      self._list_items,
"list_add_item":   self._list_add_item,
"list_remove_item": self._list_remove_item,
"list_clear":      self._list_clear,
```

Remove the `_shopping_list` method and replace with:
```python
# ── Lists (generic) ───────────────────────────────────────────────────────

def _list_items(self, inputs: dict):
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
    return module.remove(inputs['item_name'])

def _list_clear(self, inputs: dict):
    module = ItemListModule(self._db, self._user_id, inputs['list_name'], 'shopping')
    return module.clear_all()
```

### Step 7: Run new tests

```bash
pytest tests/test_tool_executor.py::test_list_add_item_dispatches \
       tests/test_tool_executor.py::test_list_remove_item_dispatches -v
```
Expected: 2 PASS

### Step 8: Run full suite

```bash
pytest tests/ -q
```
Expected: 250 passed (the existing `test_shopping_list_returns_list` keeps working via the alias)

### Step 9: Commit

```bash
git add core/tools/list_tools.py core/tools/shopping_tools.py \
        core/tools/__init__.py core/tool_executor.py tests/test_tool_executor.py
git commit -m "feat: add generic list write tools (list_add_item/remove/clear)"
```

---

## Task 4: Notes write tools

**Files:**
- Modify: `core/tools/notes_tools.py`
- Modify: `core/tool_executor.py`
- Test: `tests/test_tool_executor.py`

### Step 1: Write 3 failing tests

Add to `tests/test_tool_executor.py`:

```python
@patch('modules.notes.NotesModule.create')
def test_notes_create_dispatches(mock_create, db):
    """notes_create calls NotesModule.create."""
    mock_create.return_value = {'note_id': 7, 'status': 'created'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("notes_create", {"content": "Comprar flores", "tags": ["pendiente"]})
    mock_create.assert_called_once_with("Comprar flores", ["pendiente"])
    assert result['note_id'] == 7


@patch('modules.notes.NotesModule.append_text')
def test_notes_append_dispatches(mock_append, db):
    """notes_append calls NotesModule.append_text."""
    mock_append.return_value = {'status': 'updated'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("notes_append", {"note_id": 7, "text": "también rosas"})
    mock_append.assert_called_once_with(7, "también rosas")
    assert result['status'] == 'updated'


@patch('modules.notes.NotesModule.add_tag')
def test_notes_add_tag_dispatches(mock_tag, db):
    """notes_add_tag calls NotesModule.add_tag."""
    mock_tag.return_value = {'status': 'added'}
    from core.tool_executor import ToolExecutor
    executor = ToolExecutor(db, '99999')
    result = executor.execute("notes_add_tag", {"note_id": 7, "tag": "urgente"})
    mock_tag.assert_called_once_with(7, "urgente")
    assert result['status'] == 'added'
```

### Step 2: Run to verify they fail

```bash
pytest tests/test_tool_executor.py::test_notes_create_dispatches \
       tests/test_tool_executor.py::test_notes_append_dispatches \
       tests/test_tool_executor.py::test_notes_add_tag_dispatches -v
```
Expected: FAIL with `ValueError: Unknown tool: notes_create`

### Step 3: Add write tools to `core/tools/notes_tools.py`

Append inside `NOTES_TOOLS` list before the closing `]`:

```python
    # ── Write tools ────────────────────────────────────────────────────────────
    {
        "name": "notes_create",
        "description": (
            "Crea una nota nueva con contenido de texto libre y opcionalmente tags. "
            "Devuelve el note_id de la nota creada."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Contenido de la nota."
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de etiquetas opcionales. Ejemplo: ['receta', 'pendiente']."
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "notes_append",
        "description": (
            "Añade texto al final de una nota existente. "
            "Útil cuando el usuario quiere ampliar una nota que ya tiene. "
            "Usa notes_search primero para obtener el note_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "ID numérico de la nota."
                },
                "text": {
                    "type": "string",
                    "description": "Texto a añadir al final de la nota."
                }
            },
            "required": ["note_id", "text"]
        }
    },
    {
        "name": "notes_add_tag",
        "description": (
            "Añade un tag a una nota existente. "
            "Usa notes_search primero para obtener el note_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "ID numérico de la nota."
                },
                "tag": {
                    "type": "string",
                    "description": "Tag a añadir. Ejemplo: 'urgente', 'receta'."
                }
            },
            "required": ["note_id", "tag"]
        }
    },
    {
        "name": "notes_delete",
        "description": (
            "Elimina permanentemente una nota. "
            "Usa notes_search primero para confirmar el note_id correcto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "ID numérico de la nota a eliminar."
                }
            },
            "required": ["note_id"]
        }
    },
```

### Step 4: Add dispatchers to `core/tool_executor.py`

In the dispatch dict, add after `"notes_get"`:
```python
"notes_create":  self._notes_create,
"notes_append":  self._notes_append,
"notes_add_tag": self._notes_add_tag,
"notes_delete":  self._notes_delete,
```

Add private methods after `_notes_get`:
```python
def _notes_create(self, inputs: dict):
    module = NotesModule(self._db, self._user_id)
    return module.create(inputs['content'], inputs.get('tags'))

def _notes_append(self, inputs: dict):
    module = NotesModule(self._db, self._user_id)
    return module.append_text(inputs['note_id'], inputs['text'])

def _notes_add_tag(self, inputs: dict):
    module = NotesModule(self._db, self._user_id)
    return module.add_tag(inputs['note_id'], inputs['tag'])

def _notes_delete(self, inputs: dict):
    module = NotesModule(self._db, self._user_id)
    return module.delete(inputs['note_id'])
```

### Step 5: Run new tests

```bash
pytest tests/test_tool_executor.py::test_notes_create_dispatches \
       tests/test_tool_executor.py::test_notes_append_dispatches \
       tests/test_tool_executor.py::test_notes_add_tag_dispatches -v
```
Expected: 3 PASS

### Step 6: Run full suite

```bash
pytest tests/ -q
```
Expected: 253 passed

### Step 7: Commit

```bash
git add core/tools/notes_tools.py core/tool_executor.py tests/test_tool_executor.py
git commit -m "feat: add notes write tools (create/append/add_tag/delete)"
```

---

## Final check

After all 4 tasks, verify the total tool count:

```bash
python3 -c "
from core.tools import ALL_TOOLS
print(f'Total tools: {len(ALL_TOOLS)}')
for t in ALL_TOOLS:
    print(f'  {t[\"name\"]}')
"
```
Expected: 26 tools total (11 read + 15 write).

Run one last full suite:
```bash
pytest tests/ -q
```
Expected: 253 passed.
