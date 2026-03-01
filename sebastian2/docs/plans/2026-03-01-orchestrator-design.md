# Orchestrator — Design Doc

**Date:** 2026-03-01
**Status:** Approved
**Branch:** `orquestador`

## Problem

The current system handles one intent per message (Haiku → router → module → response).
Compound queries like *"¿necesito llevar paraguas al teatro?"* require chaining multiple
modules (calendar search → extract date → weather forecast → synthesize answer).
Today there is no mechanism for this.

---

## Solution: Anthropic Tool Use Orchestrator

A new `Orchestrator` layer replaces the router as the primary message handler.
It runs a tool use loop: Haiku selects and calls tools (module methods), the
orchestrator executes them, feeds results back, and Haiku iterates until it has
enough information. Sonnet/Alfred then synthesizes the final Spanish response.

---

## Architecture

```
Telegram → handlers.py → Orchestrator (core/orchestrator.py)
                              │
                    ┌─────────▼──────────┐
                    │  Haiku tool loop   │
                    │  tools = all defs  │
                    └─────────┬──────────┘
                              │ tool_use block
                    ┌─────────▼──────────┐
                    │  Tool executor     │  ← calls existing modules
                    │  returns raw data  │
                    └─────────┬──────────┘
                              │ tool_result
                    ┌─────────▼──────────┐
                    │  Haiku iterates…   │
                    │  stop_reason=      │
                    │  end_turn          │
                    └─────────┬──────────┘
                              │ all data collected
                    ┌─────────▼──────────┐
                    │  Sonnet / Alfred   │  ← synthesizes final answer
                    └─────────┬──────────┘
                              │
                         Spanish response
```

**Single path:** All messages go through the Orchestrator.
If Haiku needs no tools (simple conversation), it returns text directly → Alfred
responds as now via ChatModule. If Haiku uses tools, results are collected and
Alfred synthesizes.

The existing router and Haiku parser are **not deleted** — they remain as legacy
fallback until the Orchestrator is validated in production.

---

## New Components

### `core/orchestrator.py`
- Receives raw user message + user_id
- Loads tool definitions
- Runs Haiku tool use loop (max iterations: 8)
- Executes each tool_use via ToolExecutor
- Passes collected data to Sonnet/Alfred for synthesis
- Returns final response string

### `core/tools/` — Tool definitions per module

Each file exports a list of Anthropic tool dicts:

```python
# core/tools/calendar_tools.py
CALENDAR_TOOLS = [
    {
        "name": "calendar_search_events",
        "description": "Busca eventos en el calendario por título. "
                       "Devuelve lista con id, título, fecha, hora.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar en el título del evento"
                }
            },
            "required": ["query"]
        }
    },
    ...
]
```

Files: `calendar_tools.py`, `weather_tools.py`, `inventory_tools.py`,
`shopping_tools.py`, `notes_tools.py`

### `core/tool_executor.py`
- Maps tool names → module method calls
- Instantiates modules with (db, user_id)
- Returns raw `data` dict from each module response

---

## Tool Definitions — v1 (read-only)

Write tools are excluded from v1. The LLM cannot modify data unless the user
explicitly issues a write command (handled by legacy router or v2 write tools).

| Tool | Module | Method | Key params |
|------|--------|--------|------------|
| `calendar_search_events` | CalendarModule | `search_events()` | `query: str` |
| `calendar_list_events` | CalendarModule | `list_events()` | `time_window: str` |
| `calendar_find_by_datetime` | CalendarModule | `find_by_datetime()` | `date: str, time: str` |
| `weather_get` | WeatherModule | `get_weather()` | `city: str\|null` |
| `weather_forecast` | WeatherModule | `get_forecast()` | `time_window: str, days: int\|null` |
| `weather_forecast_for_date` | WeatherModule | `get_forecast_for_date()` *(new)* | `date: str (YYYY-MM-DD)` |
| `inventory_list` | InventoryModule | `list_all()` | — |
| `inventory_check_low_stock` | InventoryModule | `check_low_stock()` | — |
| `shopping_list` | ShoppingModule | `list_all()` | — |
| `notes_search` | NotesModule | `search()` | `query: str` |
| `notes_get` | NotesModule | `get()` | `note_id: int` |

### New method required
`WeatherModule.get_forecast_for_date(date: str)` — fetches a 14-day forecast
and filters to return the single day matching `date`. Returns the same structure
as `get_forecast()` but for one day.

---

## Example Flow: "¿necesito llevar paraguas al teatro?"

```
1. Haiku receives message + 11 tool defs
2. → tool_use: calendar_search_events(query="teatro")
3. Executor: CalendarModule.search_events("teatro")
   → [{event_id:42, title:"Teatro Jovellanos", date:"2026-03-05", time:"19:30"}]
4. → tool_use: weather_forecast_for_date(date="2026-03-05")
5. Executor: WeatherModule.get_forecast_for_date("2026-03-05")
   → {precip_prob:75, windgusts:40, temp_max:14, temp_min:9}
6. Haiku: stop_reason=end_turn
7. Alfred/Sonnet synthesizes:
   "Sí señor. El miércoles tiene el Teatro Jovellanos a las 19:30.
    Hay un 75% de probabilidad de lluvia. ☂️ Lleve paraguas."
```

---

## Raw Data Strategy

Modules are **not modified in v1**. The ToolExecutor reads the `data` field from
each module response (already present in all modules). The transition to
"modules return only raw data" happens module by module when convenient.

---

## Existing System Compatibility

| Component | v1 status |
|-----------|-----------|
| `core/haiku_parser.py` | Kept, used by legacy router |
| `core/router.py` | Kept as legacy fallback |
| `bot/handlers.py` | Updated: routes to Orchestrator instead of router |
| All modules | Unchanged |

During the transition period, `handlers.py` will route to the Orchestrator for
all messages. If the Orchestrator fails (exception or empty response), it falls
back to the existing router. Once stable, the legacy router is removed.

---

## Files Touched

| File | Change |
|------|--------|
| `core/orchestrator.py` | New — main tool use loop |
| `core/tool_executor.py` | New — maps tool names to module calls |
| `core/tools/__init__.py` | New — aggregates all tool definitions |
| `core/tools/calendar_tools.py` | New — 3 calendar tool defs |
| `core/tools/weather_tools.py` | New — 3 weather tool defs |
| `core/tools/inventory_tools.py` | New — 2 inventory tool defs |
| `core/tools/shopping_tools.py` | New — 1 shopping tool def |
| `core/tools/notes_tools.py` | New — 2 notes tool defs |
| `modules/weather.py` | Add `get_forecast_for_date()` method |
| `bot/handlers.py` | Route to Orchestrator; legacy router as fallback |
| `tests/test_orchestrator.py` | New — unit + integration tests |

---

## Testing Strategy

- Unit tests: mock Haiku responses, verify ToolExecutor dispatches correctly
- Integration tests: SQLite in-memory DB, real module calls, mock Haiku
- End-to-end test: full "paraguas al teatro" flow with mocked API calls
