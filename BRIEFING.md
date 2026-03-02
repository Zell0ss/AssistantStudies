# Sebastian Bot - Briefing for Claude

> **Purpose**: Knowledge transfer between Claude Code and Claude Web.
> **Audience**: Claude AI and developer

---

## What is this project

Sebastian is a personal Telegram bot powered by Anthropic's Claude models (Haiku + Sonnet). It acts as an Alfred Pennyworth-style assistant: understands Spanish natural language, manages calendar events, inventory, shopping lists, notes, tickets, and weather. The bot uses an Orchestrator pattern where Claude Haiku reasons over a set of tools to gather data, and Claude Sonnet synthesizes a concise Spanish response in Alfred's voice.

This is **Sebastian 2.0** — a full rewrite of an older LangChain/OpenAI version. The code lives in `sebastian2/`.

---

## How it works (data flow)

```
1. INGESTION:    Telegram message → bot/handlers.py (authorization check)
2. PENDING CHECK: Is there an open pending plan for this user? → resume or discard
3. PLANNING:     Haiku receives user message + ALL_TOOLS → calls tools in a loop
4. EXECUTION:    ToolExecutor.execute(tool_name, input) → module method → DB/API
5. SYNTHESIS:    Sonnet (Alfred persona) receives collected data → Spanish response
6. OUTPUT:       Text sent via _send_markdown(); ticket images via send_photo()
7. SPRITE:       Neutral sprite sent as document (non-blocking)
```

Detailed explanation:

When a user sends a plain text message, `bot/handlers.py` routes it to `Orchestrator.handle()`. The orchestrator first checks if there's a pending clarification plan for the user (saved from a previous turn). If yes, it decides whether the new message answers the pending question — if so, it resumes the saved loop; if not, it discards the plan and starts fresh.

In the main loop, Haiku receives the user message and all tool definitions. It decides which tools to call (calendar search, weather, inventory, etc.), and the ToolExecutor dispatches each call to the appropriate module method. Results feed back to Haiku as `tool_result` blocks. This loop continues until Haiku stops requesting tools (max 8 iterations). Finally, Sonnet/Alfred receives all collected data and synthesizes a concise, elegant Spanish response. The return value is always `{"text": str, "images": list[bytes]}` — images are populated when ticket QR/barcodes are requested.

---

## Tech stack

- **Language**: Python 3.11
- **Main Frameworks/Libs**:
  - **pyTelegramBotAPI**: Telegram bot API wrapper with polling
  - **anthropic**: Anthropic Python SDK — Haiku planner + Sonnet synthesizer
  - **MariaDB / mysql-connector-python**: Persistent storage for all user data
  - **APScheduler**: Daily reminder job at 08:00
  - **loguru**: Structured logging
  - **requests / requests-cache**: Weather API calls with 1h cache
  - **zxing-cpp**: QR/barcode decoding and generation (primary)
  - **pyzbar**: Barcode decoding fallback (requires `libzbar0` system dep)
  - **qrcode**: QR code image generation
  - **python-barcode**: Linear barcode (Code128, EAN, etc.) generation
  - **Pillow / numpy**: Image processing for ticket scanning/generation
  - **telegram-markdown**: Converts `**bold**` to Telegram MessageEntity objects
- **External APIs**:
  - **Anthropic API**: `claude-haiku-4-5-20251001` (planner) + `claude-sonnet-4-6` (synthesizer)
  - **OpenMeteo**: Free weather forecast + geocoding API (no auth required)
- **Infrastructure**: Server deployment with systemd service (`sebastian.service`)
- **DB**: MariaDB (`sebastian_db`), accessed via `%s` placeholders

---

## Main Telegram commands

| Command | What it does |
|---------|-------------|
| `/start`, `/hola` | Welcome message |
| `/help`, `/ayuda` | Show available commands |
| `/id_me`, `/whoami` | Show user's Telegram ID |
| `/abort` | Cancel an open pending plan (clarification in progress) |
| `/skins` | List available sprite skins |
| `/skin <name>` | Change sprite skin (e.g. `/skin josem`) |
| No command (plain text) | Routed to Orchestrator |
| Photo / document (image) | Ticket scan: decode QR/barcode, associate to calendar event |

All plain text messages go through the Orchestrator. There are no more `/tiempo`, `/inventario`, `/notas` slash commands — everything is natural language.

---

## Project structure

```
sebastian2/
├── sebastian_bot.py           # Entry point: starts bot, scheduler, clears pending plans
├── core/
│   ├── orchestrator.py        # Main pipeline: Haiku loop → ToolExecutor → Sonnet synthesis
│   ├── tool_executor.py       # Dispatch table: tool_name → module method (29 tools)
│   └── tools/                 # Anthropic tool definitions (schemas for Haiku)
│       ├── __init__.py        # Exports ALL_TOOLS (flat list)
│       ├── calendar_tools.py  # 9 tools: search, list, find, add, remove, update, add_note, get_tickets, clear_tickets
│       ├── weather_tools.py   # 3 tools: weather_get, weather_forecast, weather_forecast_for_date
│       ├── inventory_tools.py # 5 tools: list, check_low_stock, add, remove, set_quantity, update_quantity
│       ├── list_tools.py      # 4 tools: list_items, list_add_item, list_remove_item, list_clear
│       ├── notes_tools.py     # 7 tools: search, get, create, append, add_tag, remove_tag, delete
│       └── clarification_tools.py  # 1 tool: request_clarification
├── modules/
│   ├── base.py                # BaseModule: DB access helpers
│   ├── calendar.py            # CalendarModule: events CRUD + tickets + notes
│   ├── weather.py             # WeatherModule: OpenMeteo + geocoding + refranes
│   ├── inventory.py           # InventoryModule: quantity tracking + low stock
│   ├── item_list.py           # ItemListModule: shopping/packing lists
│   ├── notes.py               # NotesModule: free text notes with tags
│   ├── ticket_decoder.py      # QR/barcode decoding (zxing-cpp + pyzbar fallback)
│   ├── ticket_generator.py    # QR/barcode image generation
│   └── user_settings.py       # UserSettingsModule: sprite skin, weather location
├── bot/
│   ├── handlers.py            # Telegram handlers, /abort, photo/doc dispatch
│   ├── ticket_handler.py      # Photo → decode → associate to event (5min pending state)
│   ├── formatter.py           # Legacy response formatter (used for error sprites)
│   └── scheduler.py           # APScheduler: daily 08:00 reminder
├── db/
│   ├── connection.py          # MariaDB connection factory
│   ├── pending_plan_repo.py   # PendingPlanRepository: save/get/delete pending loop state
│   └── migrations/            # SQL migrations 001–008
│       └── 008_pending_plans.sql   # Latest migration (needed in production)
├── sprites/
│   ├── sprite_system.py       # Skin lookup, sprite path resolution
│   ├── mapping.yaml           # Skin → emotion → file mapping
│   └── images/
│       ├── default/           # Default sprite set
│       └── josem/             # josem skin (000_neutral.webp … 011_deadpan.webp)
├── utils/
│   ├── config.py              # Load config.yaml
│   └── logging_config.py      # Loguru setup
├── data/
│   └── refranes.txt           # Spanish wine proverbs (appended to weather responses)
├── tests/                     # 274 tests, all passing
├── docs/
│   ├── COMANDOS.md            # User-facing command reference
│   └── DEPLOYMENT_CHECKLIST.md # Step-by-step production deployment
└── config.yaml                # API keys, authorized users (gitignored)
```

---

## Critical design decisions

### Orchestrator: Haiku planner + Sonnet synthesizer

**Why**: A single model doing both reasoning and synthesis is slower and more expensive. Splitting lets Haiku (fast, cheap) handle multi-step tool orchestration while Sonnet (capable, eloquent) focuses only on crafting the final response.

**Haiku planner** (`claude-haiku-4-5-20251001`): Receives ALL_TOOLS + user message. Calls tools iteratively until it has enough data (max 8 iterations). System prompt injects today's date so date resolution works correctly.

**Sonnet synthesizer** (`claude-sonnet-4-6`): Receives collected `[tool(input)]: result` context + user's original question. Responds in Alfred Pennyworth style — British discretion, always Spanish, never more words than needed. System prompt includes today's date too.

---

### Pending plans: stateful clarification across turns

**Why**: Sometimes Haiku needs information the user didn't provide (e.g. "¿paraguas a pilates?" — but which city?). Rather than hallucinating, the orchestrator pauses, asks the user, and resumes on the next message.

**Mechanism**:
1. Haiku calls `request_clarification(question, missing_field)` when it needs input
2. Orchestrator saves the full Haiku messages array + the question to `pending_plans` table
3. Returns Alfred's phrasing of the question to the user
4. On next user message, Haiku (with max_tokens=10) decides if the message answers the question (SI/NO)
5. If YES → restore messages, inject user answer as `tool_result`, continue loop
6. If NO → discard plan, treat message as fresh query

**Cleanup**: Plans expire after 24h, are deleted on `/abort`, and all plans are cleared on bot restart.

---

### ToolExecutor dispatch table

**Why**: Clean separation between the orchestration layer (Orchestrator) and the execution layer (modules). Orchestrator never imports modules directly — all tool calls go through ToolExecutor's dispatch dict.

**Pattern**: Each tool maps to a private method `_tool_name(inputs: dict)` that instantiates the relevant module and calls one method. Returns raw data (str, list, dict) which Orchestrator serializes as JSON for Haiku's `tool_result` blocks.

---

### Weather tools return pre-formatted text

**Why**: If ToolExecutor returns raw data dicts (arrays of temps/dates), Sonnet/Alfred formats them as markdown tables — which Telegram doesn't render. By returning the pre-formatted plain text string from `WeatherModule`, Alfred receives clean text and can present it without re-formatting.

**Impact**: `_weather_get` and `_weather_forecast` return `response['result']` (pre-formatted string). `_weather_forecast_for_date` still returns `response['data']` (raw dict) because Haiku needs to reason over specific dates.

---

### Orchestrator returns {"text", "images"} dict

**Why**: Ticket retrieval requires sending both a text response AND ticket images (QR/barcode PNGs). Rather than a side-channel, `handle()` returns a structured dict so `bot/handlers.py` has a clean contract.

**Pattern**: `{"text": str, "images": list[bytes]}`. Most calls have `images = []`. When Haiku calls `calendar_get_tickets`, `_collect_images()` generates PNG bytes for each ticket via `ticket_generator.generate_image()`.

---

## Database schema

```sql
-- Events (calendar)
events (
    id, user_id, title,
    event_date DATE,          -- for all-day events
    start_datetime DATETIME,  -- for timed events
    end_datetime DATETIME,
    all_day BOOLEAN,
    recurrence_rule TEXT,     -- 'daily', 'weekly:MON', 'monthly:15', etc.
    recurrence_end DATE,
    notes JSON,               -- {"tickets": [{"type": "CODE_128", "value": "...", "value_b64": "..."}], "note": "..."}
    created_at, updated_at
)

-- Lists (shopping, packing, inventory all use same tables)
lists (id, user_id, list_category, name, created_at, updated_at)
list_items (id, list_id, name, quantity, unit, notes, checked, low_threshold, recurring, created_at, updated_at)

-- Notes
notes (id, user_id, content TEXT, tags JSON, created_at, updated_at)

-- User settings
user_settings (
    user_id TEXT PRIMARY KEY,
    sprite_skin TEXT DEFAULT 'default',
    weather_location TEXT, weather_lat REAL, weather_lon REAL, weather_country TEXT
)

-- Pending plans (orchestrator loop state)
pending_plans (
    id, user_id UNIQUE,
    original_message TEXT,
    messages_json LONGTEXT,   -- serialized Haiku messages array
    question TEXT,            -- what Alfred asked the user
    missing_field TEXT,       -- e.g. 'city'
    created_at, expires_at   -- TTL = 24h
)
```

**DB migrations**: 001–008. Production needs 006 (weather_settings), 007 (conversations), 008 (pending_plans) if not yet run.

---

## Tool domains (29 tools total)

| Domain | Tools |
|--------|-------|
| **Calendar** | `calendar_search_events`, `calendar_list_events`, `calendar_find_by_datetime`, `calendar_add_event`, `calendar_remove_event`, `calendar_update_event`, `calendar_add_note`, `calendar_get_tickets`, `calendar_clear_tickets` |
| **Weather** | `weather_get`, `weather_forecast`, `weather_forecast_for_date` |
| **Inventory** | `inventory_list`, `inventory_check_low_stock`, `inventory_add`, `inventory_remove`, `inventory_set_quantity`, `inventory_update_quantity` |
| **Lists** | `list_items`, `list_add_item`, `list_remove_item`, `list_clear` (+ `shopping_list` alias) |
| **Notes** | `notes_search`, `notes_get`, `notes_create`, `notes_append`, `notes_add_tag`, `notes_remove_tag`, `notes_delete` |
| **Clarification** | `request_clarification` |

---

## Ticket flow

**Upload**: User sends photo → `handle_photo` → `handle_media()` → zxing-cpp decodes QR/barcode → if caption given: auto-associate to matching event; if no caption: ask user (5min pending state via threading.Timer) → stored in `events.notes` JSON.

**Retrieval**: "qué tickets tengo para el teatro" → Orchestrator: Haiku calls `calendar_search_events` then `calendar_get_tickets(event_id)` → `_collect_images()` generates PNG bytes → `handle()` returns `{"text": ..., "images": [bytes, ...]}` → bot sends text + each image as `send_photo()`.

**Ticket generator dispatch**:
- `QR_CODE` → `qrcode` library
- `CODE_128 / CODE_39 / EAN_* / UPC_*` → `python-barcode`
- `AZTEC / DATA_MATRIX / PDF417` → `zxingcpp.create_barcode()` + `write_barcode_to_image()`

---

## Configuration

**`config.yaml`** (gitignored, in `sebastian2/` root):
```yaml
authorized_ids: [telegram_user_id, ...]
authorized_users: [username, ...]
telegram_apikey: xxx
anthropic_apikey: xxx
logfolder: /path/to/logs
```

No OpenAI key. No LangChain. No provider classes.

---

## Current state

**Branch**: `orquestador` (ahead of `main`, ready for production testing)
**Tests**: 274/274 passing

### Features implemented

- ✅ **Orchestrator** — Haiku tool loop (max 8 iter) + Sonnet/Alfred synthesis
- ✅ **Pending plans** — stateful clarification across turns, /abort, 24h TTL, startup cleanup
- ✅ **Calendar** — full CRUD + recurring events + ticket storage + add_note
- ✅ **Weather** — current + multi-day forecast + per-user location (geocoding) + refranes
- ✅ **Inventory** — named inventories, quantity tracking, low stock warnings, upserts
- ✅ **Lists** — named shopping/packing lists, add/remove/clear
- ✅ **Notes** — free text with tags, search, append, tag management
- ✅ **Tickets** — scan (QR + barcodes), store in calendar events, retrieve + regenerate images
- ✅ **Sprites** — multi-skin system, josem skin added, `/skin` and `/skins` commands
- ✅ **Daily reminder** — APScheduler job at 08:00

### Pending before production

- Migrations 006–008 must run on production DB (`seb01`)
- PR from `orquestador` → `main` pending smoke test approval

---

## Typical use cases

### Case 1: Multi-step natural language query

```
User: "¿necesito llevar paraguas al teatro?"
Haiku: calls calendar_search_events(query="teatro")
       → finds Teatro Jovellanos on 2026-03-05 at 19:30
       calls weather_forecast_for_date(date="2026-03-05")
       → 75% precipitation probability
Alfred: "Sí, señor. El Teatro Jovellanos es el jueves a las 19:30.
         Hay un 75% de probabilidad de lluvia. ☂️ Lleve paraguas."
```

### Case 2: Clarification needed

```
User: "¿llevo paraguas a pilates?"
Haiku: calls request_clarification(question="¿En qué ciudad tiene pilates?", missing_field="city")
Alfred: "¿En qué ciudad tiene usted pilates, señor?"
[Plan saved]

User: "Madrid"
Haiku (is_plan_reply check): "SI"
[Resume saved loop]
Haiku: calls weather_get(city="Madrid")
Alfred: "No es necesario el paraguas, señor. 10% de probabilidad de lluvia en Madrid."
```

### Case 3: Ticket retrieval

```
User: "qué tickets tengo para el teatro"
Haiku: calls calendar_search_events(query="teatro")
       → event_id=42, Teatro Jovellanos
       calls calendar_get_tickets(event_id=42)
       → [{"type": "CODE_128", "value": "ABC123", ...}]
Alfred: "Aquí tiene su entrada para el Teatro Jovellanos, señor."
Bot: sends text + barcode image
```

### Case 4: Inventory update

```
User: "me quedan 3 huevos"
Haiku: calls inventory_set_quantity(item_name="huevos", quantity=3)
Alfred: "Anotado, señor. Huevos: 3 unidades."
(If 3 < threshold → Alfred includes low stock note)
```

---

## Limitations and caveats

- **No conversation history**: Each user message starts fresh. Alfred can't refer to previous turns.
- **Single user context**: The system is designed for one primary user. Multi-user works technically but Alfred responds generically.
- **MariaDB required**: Tests use SQLite in-memory (via `MySQLCompatibleConnection` wrapper that translates `%s→?`), but production needs MariaDB.
- **System dependency**: `libzbar0` must be installed on the server (`sudo apt-get install libzbar0`) — NOT in requirements.txt.
- **Haiku date reasoning**: The planner system prompt injects today's date. Without it, Haiku resolves "mañana" incorrectly.

---

## Key code patterns

### Adding a new tool

1. Add tool definition dict to the appropriate `core/tools/<domain>_tools.py`
2. Add `"tool_name": self._method` to `ToolExecutor.dispatch` in `core/tool_executor.py`
3. Add `def _method(self, inputs: dict)` handler in ToolExecutor
4. Handler instantiates the module and calls one method, returning raw data

### Accessing the orchestrator result

```python
# bot/handlers.py pattern
result = orchestrator.handle(message.text)
response_text = result["text"]   # always present
images = result["images"]        # list[bytes], usually []
_send_markdown(bot, chat_id, response_text)
for img_bytes in images:
    bot.send_photo(chat_id=chat_id, photo=io.BytesIO(img_bytes))
```

### Adding a new module

Inherit from `BaseModule` (provides `execute_query()`, `commit()`, `self.user_id`). All queries use `%s` placeholders (MariaDB). Tests use SQLite via `MySQLCompatibleConnection`.

---

## Notes for Claude Web

**Architecture summary for discussions**:
- No LangChain, no OpenAI. Everything is Anthropic (Claude Haiku + Sonnet).
- The orchestrator is the central intelligence. Modules are dumb data layers.
- Tool descriptions for Haiku are critical — they determine which tools get called and when.
- Alfred's character is defined in `_ALFRED_SYSTEM` prompt in `orchestrator.py`.

**Active design questions**:
- Should conversation history be stored and fed back to Haiku? Currently stateless per message.
- Should the synthesizer (Alfred) ever call tools directly, or only reason over data Haiku collected?
- Is 8 iterations enough for complex multi-step queries?

---

## Notes for Claude Code

**Project conventions**:
- All DB queries use `%s` placeholders (MariaDB). Tests use `MySQLCompatibleConnection` to translate to SQLite.
- `Orchestrator.handle()` always returns `{"text": str, "images": list[bytes]}`.
- Tool results returned by ToolExecutor are serialized as JSON in the Haiku tool_result block — keep them JSON-serializable (use `default=str` in dumps).
- Weather tools return pre-formatted text strings, not raw dicts — keeps Alfred from generating markdown tables.
- Run tests: `cd sebastian2 && source .venv/bin/activate && pytest tests/ -v`
- DB access: `sudo mysql sebastian_db`
- Commits use `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`

---

*Last updated: 2026-03-02*
*Architecture: Sebastian 2.0 — Orchestrator (Haiku + Sonnet) + MariaDB*
*Branch: `orquestador` — 274/274 tests passing*
