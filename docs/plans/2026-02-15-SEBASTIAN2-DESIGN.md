# Sebastian 2.0 - Design Document

**Date:** 2026-02-15
**Status:** Approved
**Author:** Claude (Sonnet 4.5) + Josem
**Purpose:** Evolution from Q&A bot to personal assistant with persistent memory

---

## 1. Vision & Motivation

### The Problem

Sebastian 1.0 is a well-architected Telegram bot (LangChain agent + provider system) built as a learning project. However, it's **rarely used** in practice - more of a tech demo than a daily tool.

Meanwhile, there's a real-world problem:
- **Scattered notes** - forget where things are written, lose track of tasks
- **Memory/organization issues** - impacts relationship with Rebe ("did you buy X?", "where is Y?")
- **No single source of truth** - information fragmented across apps, notes, messages
- **Friction to capture** - opening notes apps, typing, organizing - all too slow

### The Solution

Sebastian 2.0 is a **personal assistant with persistent memory**, accessible via Telegram (Phase 1) with optional web frontend (Phase 2+). It solves organization problems through:

1. **Inventory tracking** - know what you have, auto-alert when low
2. **Smart shopping lists** - items disappear when bought, auto-populate when stock low
3. **Packing lists** - recurring items (milk for Gijón) vs one-time (towels)
4. **Free-form notes** - searchable, tagged, never lost
5. **Voice-first input** - Telegram voice-to-text → natural language processing
6. **Personality** - sprite expressions make it engaging (not just a database)

### Success Metrics

Phase 1 succeeds if:
- **Daily use** for 2+ weeks (behavior change, not just "cool project")
- **Lower friction** than scattered notes/texts
- **Rebe notices** improved organization (fewer "did you forget X?" moments)

---

## 2. System Overview

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      User (Telegram)                         │
│           Text messages OR voice (Telegram STT)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                   sebastian_bot.py                           │
│                 (Telegram handler)                           │
│  - Authorization check (user_id)                             │
│  - Route to Haiku intent parser                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────────┐
│            Claude Haiku Intent Parser                        │
│  - Receives text (typed or Telegram-transcribed voice)       │
│  - Returns structured JSON:                                  │
│    {module, action, item, qty, unit, list_name, ...}         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                  Module Router                               │
│  Dispatches to appropriate module based on parsed intent     │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│ Inventory   │ Shopping     │ Packing      │ Notes           │
│ Module      │ List Module  │ List Module  │ Module          │
└──────┬──────┴──────┬───────┴──────┬───────┴─────┬───────────┘
       │             │              │             │
       └─────────────┴──────────────┴─────────────┘
                      │
                      ↓
            ┌─────────────────────┐
            │   MariaDB (seb01)   │
            │  - inventory        │
            │  - lists            │
            │  - list_items       │
            │  - notes            │
            └──────────┬──────────┘
                       │
                       ↓
            ┌─────────────────────┐
            │  Response Formatter │
            │  - Text + Sprite    │
            └──────────┬──────────┘
                       │
                       ↓
            ┌─────────────────────┐
            │  Telegram Response  │
            │  (photo + caption)  │
            └─────────────────────┘
```

### Key Flow

1. User sends message (text or voice) via Telegram
2. Telegram handles voice-to-text transcription (built-in)
3. `sebastian_bot.py` receives text message
4. Authorization check (user_id against config)
5. Text sent to Claude Haiku for intent parsing
6. Haiku returns structured JSON: `{module, action, item, qty, ...}`
7. Module router calls appropriate module method
8. Module updates MariaDB, returns result
9. Response formatter selects sprite expression + formats text
10. Telegram receives photo (sprite) with caption (text response)

### What Changes from v1.0

| Aspect | Sebastian 1.0 | Sebastian 2.0 |
|--------|--------------|---------------|
| **Core function** | Q&A + external API queries | CRUD personal data + conversational AI |
| **State** | Stateless (no persistence) | MariaDB as source of truth |
| **LLM role** | LangChain agent selects tools | Haiku parses intent → module router |
| **Intelligence** | GPT-4 via LangChain | Claude Haiku (fast, cheap, structured output) |
| **Voice input** | Whisper API transcription | Telegram built-in voice-to-text |
| **Personality** | None | Sprite expressions mapped to response context |
| **Usage** | Rarely used (tech demo) | Daily driver (solving real problem) |

### What's Preserved from v1.0

- ✅ Telegram interface (pyTelegramBotAPI)
- ✅ Authorization system (config.yaml)
- ✅ Logging (loguru)
- ✅ Deployment (systemd service, .venv)
- ✅ Configuration pattern (YAML-based)

---

## 3. Data Model (MariaDB)

Database: `sebastian_db` on seb01's existing MariaDB instance.

All data is **per-user** (multi-user support via `user_id` = Telegram user ID).

### Table: inventory

Tracks what you have at home (pantry, fridge).

```sql
CREATE TABLE inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,           -- Telegram user ID
    item_name VARCHAR(255) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL DEFAULT 0,
    unit VARCHAR(50),                        -- 'unidades', 'kg', 'litros', etc.
    low_threshold DECIMAL(10,2) DEFAULT 2,   -- Auto-add to shopping when qty <= this
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_item (user_id, item_name)
);
```

**Key behaviors:**
- `quantity` can be **added** ("compré 3 aguacates" → qty += 3)
- `quantity` can be **set** ("me quedan 2 aguacates" → qty = 2)
- When `quantity <= low_threshold`, auto-add to shopping list
- Per-item thresholds (aguacates < 3, leche < 1, etc.)

### Table: lists

Named collections (shopping, packing, custom).

```sql
CREATE TABLE lists (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,              -- 'compra', 'gijón_llevar'
    description TEXT,
    list_type ENUM('shopping', 'packing', 'freeform') DEFAULT 'freeform',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_list (user_id, name)
);
```

### Table: list_items

Items within lists.

```sql
CREATE TABLE list_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    list_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    quantity DECIMAL(10,2),                  -- Optional: "6 aguacates" vs just "aguacates"
    unit VARCHAR(50),
    checked BOOLEAN DEFAULT FALSE,
    recurring BOOLEAN DEFAULT FALSE,         -- For packing lists: stays when checked
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
);
```

**Key behaviors:**
- **Shopping list** (`list_type='shopping'`):
  - All items have `recurring=false`
  - When `checked=true` (bought), item **disappears** (deleted from list)

- **Packing list** (`list_type='packing'`):
  - Items can be `recurring=true` (milk for Gijón) or `recurring=false` (towels)
  - `recurring=true`: When checked, stays in list (just marked done for this trip)
  - `recurring=false`: When checked, **disappears** (brought to destination)

### Table: notes

Free-form text with tags.

```sql
CREATE TABLE notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    tags JSON,                               -- ["personal", "rebe", "idea"]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    archived BOOLEAN DEFAULT FALSE
);
```

**Key behaviors:**
- Tags are JSON array (MariaDB 10.x supports `JSON_CONTAINS()`)
- Search via simple LIKE query in Phase 1
- Can migrate to full-text search or vector search (ChromaDB) in Phase 3

### Design Decisions

**Why separate `inventory` and shopping `list`?**
- Inventory tracks **current state** (what you have)
- Shopping list tracks **intent** (what to buy)
- When inventory low → auto-add to shopping list
- When you buy → update inventory AND remove from shopping list

**Why `recurring` flag on `list_items`?**
- Packing lists have different patterns:
  - **Recurring** (milk for Gijón) - always need to bring, stays on list
  - **One-time** (towels) - bring once, disappears when checked
- Shopping lists always have `recurring=false`

**Why JSON for tags?**
- Simple for Phase 1 (no junction table)
- MariaDB 10.x supports `JSON_CONTAINS()` for searching
- Can add full-text index later if needed

**Why `user_id` in every table?**
- Multi-user support (currently just Josem, but architecture supports Rebe/family)
- Each user has isolated inventory, lists, notes

---

## 4. Core Components

### Directory Structure

```
sebastian2/
├── bot/
│   ├── __init__.py
│   ├── handlers.py          # Telegram message handlers
│   └── formatter.py         # Response formatting + sprite selection
│
├── core/
│   ├── __init__.py
│   ├── haiku_parser.py      # Claude Haiku intent parsing
│   └── router.py            # Routes parsed intent → modules
│
├── modules/
│   ├── __init__.py
│   ├── base.py              # BaseModule (DB connection)
│   ├── inventory.py         # InventoryModule
│   ├── shopping.py          # ShoppingListModule
│   ├── packing.py           # PackingListModule
│   └── notes.py             # NotesModule
│
├── db/
│   ├── __init__.py
│   ├── connection.py        # MariaDB connection pool (PyMySQL + dbutils)
│   └── migrations/
│       └── 001_initial.sql  # Creates tables
│
├── sprites/
│   ├── mapping.yaml         # expression → image file
│   └── images/
│       ├── neutral.png
│       ├── thinking.png
│       ├── confident.png
│       ├── surprised.png
│       ├── concerned.png
│       ├── triumphant.png
│       ├── confused.png
│       ├── serious.png
│       ├── skeptical.png
│       ├── apologetic.png
│       ├── excited.png
│       └── deadpan.png
│
├── utils/
│   ├── __init__.py
│   ├── config.py            # Load config.yaml
│   └── logging.py           # Loguru setup
│
├── config.yaml              # Telegram token, Anthropic key, MariaDB creds
├── config.example.yaml
├── requirements.txt
├── sebastian_bot.py         # Main entry point
└── sebastian2.service       # systemd service file
```

### BaseModule

All modules inherit from `BaseModule`:

```python
class BaseModule:
    def __init__(self, db_connection, user_id):
        self.db = db_connection
        self.user_id = user_id

    def execute_query(self, query, params):
        """Execute SQL with automatic user_id filtering"""
        cursor = self.db.cursor()
        cursor.execute(query, params)
        return cursor

    def commit(self):
        self.db.commit()
```

### Module Methods

**InventoryModule** (`modules/inventory.py`):
- `add(item, quantity, unit)` - Add to existing quantity (compré X)
- `set(item, quantity, unit)` - Set absolute quantity (me quedan X)
- `get(item)` - Query current quantity
- `list_all()` - Get full inventory
- `check_threshold(item)` - If qty <= threshold, add to shopping list
- `set_threshold(item, threshold)` - Configure per-item low stock alert

**ShoppingListModule** (`modules/shopping.py`):
- `add(item, quantity)` - Add to shopping list
- `remove(item)` - Remove from list (when bought)
- `list_all()` - Get current shopping list
- `mark_bought(item)` - Remove item (disappears from list)

**PackingListModule** (`modules/packing.py`):
- `add(list_name, item, recurring)` - Add to packing list
- `check(list_name, item)` - Check off item
- `uncheck_recurring(list_name)` - Reset recurring items for next trip
- `list_items(list_name)` - Get items in packing list

**NotesModule** (`modules/notes.py`):
- `create(content, tags)` - Save a note
- `search(query)` - Search notes (LIKE query in Phase 1)
- `add_tag(note_id, tag)` - Add tag to existing note
- `list_by_tag(tag)` - Get all notes with specific tag

### Haiku Intent Parser

**Input:** Raw text from user (typed or Telegram-transcribed voice)

**Output:** Structured JSON with intent + parameters

**Example Haiku system prompt:**
```
You are an intent parser for a personal assistant. Parse the user's message into structured JSON.

Output schema:
{
  "module": "inventory | shopping | packing | notes | query",
  "action": "add | set | remove | list | check | search | get",
  "item": "string (item name, e.g., 'aguacates')",
  "quantity": "number (optional)",
  "unit": "string (optional, e.g., 'unidades', 'kg')",
  "list_name": "string (for lists/packing, e.g., 'gijón_llevar')",
  "tags": "array of strings (for notes)",
  "recurring": "boolean (for packing lists)",
  "threshold": "number (for setting low stock alert)"
}

Examples:
- "compré 6 aguacates" → {"module": "inventory", "action": "add", "item": "aguacates", "quantity": 6}
- "me quedan 2 aguacates" → {"module": "inventory", "action": "set", "item": "aguacates", "quantity": 2}
- "lista de la compra" → {"module": "shopping", "action": "list"}
- "añade leche a Gijón, siempre" → {"module": "packing", "action": "add", "item": "leche", "list_name": "gijón_llevar", "recurring": true}
```

**Implementation notes:**
- Use Anthropic SDK with Claude Haiku (`claude-haiku-4.5-20250129`)
- Structured output via JSON mode
- ~$0.25/MTok input, $1.25/MTok output (very cheap for personal use)
- Estimated cost: $3-5/month for 50-100 daily interactions

### Response Formatter + Sprite Selection

**Phase 1:** Text response + sprite image sent as photo with caption

**Sprite mapping logic (deterministic):**
- Successful add/update → `confident` or `triumphant`
- Query result (list/inventory) → `neutral`
- Low stock warning → `concerned`
- Item added to shopping → `thinking` → `confident`
- Empty list query → `apologetic` or `deadpan`
- Error/can't parse intent → `confused` or `apologetic`
- Correction acknowledged → `neutral`

**Telegram output:**
```python
bot.send_photo(
    chat_id=message.chat.id,
    photo=open('sprites/images/confident.png', 'rb'),
    caption="Vale, ahora tienes 8 aguacates 🥑"
)
```

**Future (Phase 1.5):** Haiku can optionally suggest expression in JSON output

---

## 5. Key Workflows

### Workflow 1: Coming from Market (Voice Input)

**User sends voice message:** "compré 6 aguacates, leche y pan"

```
1. Telegram transcribes → "compré 6 aguacates, leche y pan"
2. sebastian_bot.py receives text
3. Authorization check
4. Send to Haiku:
   → Returns: [
       {"module": "inventory", "action": "add", "item": "aguacates", "quantity": 6},
       {"module": "inventory", "action": "add", "item": "leche", "quantity": 1},
       {"module": "inventory", "action": "add", "item": "pan", "quantity": 1}
     ]
5. For each item:
   - InventoryModule.add(item, qty)
   - Check if item in shopping list → remove it
   - Update inventory count
6. Response formatter:
   - Expression: "confident"
   - Text: "Vale, actualizado:\n• Aguacates: 8 🥑\n• Leche: 1 🥛\n• Pan: 1 🍞"
7. Send photo (confident sprite) + caption
```

### Workflow 2: Low Stock → Auto-Add to Shopping

**User:** "me quedan 2 aguacates"

```
1. Haiku: {"module": "inventory", "action": "set", "item": "aguacates", "quantity": 2}
2. InventoryModule.set(item="aguacates", qty=2)
3. Update inventory: 8→2
4. InventoryModule.check_threshold("aguacates"):
   - Query threshold: 3
   - Current: 2
   - 2 <= 3 → TRIGGER
5. ShoppingListModule.add(item="aguacates")
6. Response:
   - Expression: "concerned"
   - Text: "Vale, te quedan 2 aguacates.\n⚠️ Stock bajo, he añadido aguacates a la lista de la compra."
```

### Workflow 3: Query Shopping List

**User:** "lista de la compra"

```
1. Haiku: {"module": "shopping", "action": "list"}
2. ShoppingListModule.list_all()
3. Response:
   - Expression: "neutral"
   - Text: "🛒 Lista de la compra:\n• Aguacates\n• Leche\n• Pan\n\n(3 items)"
```

### Workflow 4: Packing List (Recurring Items)

**User:** "añade leche a Gijón, siempre"

```
1. Haiku: {"module": "packing", "action": "add", "item": "leche",
           "list_name": "gijón_llevar", "recurring": true}
2. PackingListModule.add(list_name="gijón_llevar", item="leche", recurring=true)
3. Response:
   - Expression: "confident"
   - Text: "Añadido a la lista de Gijón: leche (se mantendrá en la lista)"
```

**Later:** "marca leche en Gijón"

```
1. Haiku: {"module": "packing", "action": "check", "item": "leche",
           "list_name": "gijón_llevar"}
2. PackingListModule.check(list_name="gijón_llevar", item="leche")
3. UPDATE list_items SET checked=true WHERE name='leche' AND recurring=true
   (item stays, just marked done)
4. Response:
   - Expression: "triumphant"
   - Text: "✓ Leche marcado en lista Gijón"
```

### Workflow 5: Correction

**User:** "cuántos aguacates tenemos"

```
1. Haiku: {"module": "inventory", "action": "get", "item": "aguacates"}
2. InventoryModule.get(item="aguacates")
3. Response: "Tienes 8 aguacates" (neutral sprite)
```

**User:** "corrígelo a 5, me comí varios"

```
1. Haiku: {"module": "inventory", "action": "set", "item": "aguacates", "quantity": 5}
2. InventoryModule.set(item="aguacates", qty=5)
3. Update: 8→5
4. Check threshold: 5 > 3, no shopping list add
5. Response: "Vale, corregido a 5 aguacates" (confident sprite)
```

---

## 6. Migration from v1.0

### Strategy: New Directory (Clean Slate)

**Why new directory:**
- v1.0 rarely used → no critical workflows to preserve
- Clean separation (v1.0 as reference, v2.0 fresh start)
- Can run both bots during testing (different tokens or stop v1.0)
- Easy rollback if Phase 1 fails

**Directory structure:**
```
/data/AssistantStudies/
├── sebastian/              # v1.0 (archived, keep for reference)
│   ├── sebastian_bot.py
│   ├── providers/
│   ├── tools.py
│   └── sebastian_agent.py
│
└── sebastian2/             # v2.0 (fresh start)
    ├── bot/
    ├── core/
    ├── modules/
    ├── db/
    └── config.yaml
```

### What to Keep from v1.0

**Infrastructure:**
- ✅ Telegram interface pattern (pyTelegramBotAPI)
- ✅ Authorization system (`authorized_ids`, `authorized_users`)
- ✅ Logging pattern (loguru)
- ✅ Deployment (systemd service, .venv)
- ✅ Config structure (config.yaml)

**Optional (Phase 1.5+):**
- 🔄 Weather provider (if still want weather queries)
- 🔄 Google Calendar (read-only events)
- 🔄 DALL-E image generation (`/imagen` command)

### What to Retire

- ❌ LangChain agent system
- ❌ tools.py (specialized chains)
- ❌ sebastian_agent.py
- ❌ Provider pattern (not needed for Phase 1)
- ❌ Whisper transcription (Telegram handles it)
- ❌ Dropbox storage provider (not needed)

### Config Migration

**v1.0 config.yaml:**
```yaml
authorized_ids: [123456789]
authorized_users: [username]
telegram_apikey: xxx
openai_apikey: xxx
logfolder: /path/to/logs
```

**v2.0 config.yaml:**
```yaml
# Preserved from v1.0:
authorized_ids: [123456789]
authorized_users: [username]
telegram_apikey: xxx
logfolder: /path/to/logs

# NEW for v2.0:
anthropic_apikey: xxx           # Claude Haiku
mariadb:
  host: localhost
  port: 3306
  database: sebastian_db
  user: sebastian_user
  password: xxx

# Optional (Phase 1.5+):
openai_apikey: xxx              # If keeping DALL-E
google_calendar: {...}          # If keeping calendar
```

### systemd Services

**v1.0:** `sebastian.service` (keep running during Phase 1 testing)

**v2.0:** `sebastian2.service` (new file)

Can run both during testing, then disable v1.0 when v2.0 stable.

---

## 7. Deployment

### Server: seb01

**Specs:** Ubuntu 22.04, 4 vCores, 16GB RAM, 75GB SSD

**Already running:** Docker, n8n, MariaDB, glasspanel, mangataro, Claude Gazette, Sebastian v1.0

**Resource overhead for v2.0:**
- ~200-300MB RAM (Python + connection pool)
- Minimal CPU (idle unless processing)
- ~100MB disk (code + .venv)
- MariaDB: ~10-50MB (personal data is tiny)

No concerns about capacity.

### Dependencies (requirements.txt)

```txt
# Telegram
pyTelegramBotAPI==4.14.0

# Database
PyMySQL==1.1.0
dbutils==3.0.3          # Connection pooling

# LLM
anthropic==0.18.0       # Claude Haiku API

# Config & Utils
pyyaml==6.0.1
python-dotenv==1.0.0
loguru==0.7.2
```

**Much lighter than v1.0** (no LangChain, no heavy dependencies).

### Database Setup

**1. Create database & user:**
```sql
CREATE DATABASE sebastian_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sebastian_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON sebastian_db.* TO 'sebastian_user'@'localhost';
FLUSH PRIVILEGES;
```

**2. Run migration:**
```bash
cd /data/AssistantStudies/sebastian2
mysql -u sebastian_user -p sebastian_db < db/migrations/001_initial.sql
```

**3. Verify:**
```bash
mysql -u sebastian_user -p sebastian_db -e "SHOW TABLES;"
# Expected: inventory, lists, list_items, notes
```

### systemd Service

**File:** `/etc/systemd/system/sebastian2.service`
```ini
[Unit]
Description=Sebastian 2.0 Personal Assistant Bot
After=network.target mariadb.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/data/AssistantStudies/sebastian2
Environment="PYTHONUNBUFFERED=1"
ExecStart=/data/AssistantStudies/sebastian2/.venv/bin/python sebastian_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Commands:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable sebastian2
sudo systemctl start sebastian2
sudo systemctl status sebastian2
sudo journalctl -u sebastian2 -f
```

### Development Workflow

```bash
# Create project structure
mkdir -p /data/AssistantStudies/sebastian2
cd /data/AssistantStudies/sebastian2

# Create venv
python3.11 -m venv .venv
source .venv/bin/activate

# Install deps
pip install -r requirements.txt

# Setup config
cp config.example.yaml config.yaml
# Edit: telegram_apikey, anthropic_apikey, mariadb credentials

# Run migrations
mysql -u sebastian_user -p sebastian_db < db/migrations/001_initial.sql

# Test bot (foreground)
python sebastian_bot.py

# If working, enable service
sudo systemctl start sebastian2
```

---

## 8. Phase 1 Scope & Success Criteria

### What's IN Phase 1

**Core Features:**
- ✅ **Inventory system** - quantities, thresholds, auto-shopping list
- ✅ **Shopping list** - items disappear when bought
- ✅ **Packing lists** - recurring + one-time items (Gijón scenario)
- ✅ **Notes** - free-form with tags, basic search
- ✅ **Voice input** - Telegram voice-to-text → Haiku parsing
- ✅ **Sprite expressions** - 12 expressions, photo + caption responses

**Architecture:**
- ✅ MariaDB schema (inventory, lists, list_items, notes)
- ✅ Module system (Inventory, Shopping, Packing, Notes)
- ✅ Haiku intent parser (structured JSON output)
- ✅ Module router (dispatch to correct module)
- ✅ Response formatter (sprite selection + text)
- ✅ Telegram bot (handlers, authorization)
- ✅ systemd service (seb01 deployment)

**Operations Haiku Must Parse:**
- Inventory: "compré 6 aguacates", "me quedan 2", "cuántos tenemos", "corrígelo a 5"
- Thresholds: "pon el mínimo de aguacates a 3"
- Shopping: "añade leche a la compra", "lista de la compra"
- Packing: "añade toalla a Gijón", "añade leche a Gijón, siempre", "marca leche"
- Notes: "apunta que Rebe prefiere manzanas verdes", "busca notas sobre Rebe"

### What's NOT in Phase 1

**Phase 1.5 (after 2 weeks of daily use):**
- ❌ Tier 2 Sonnet agent (if Haiku struggles with complex queries)
- ❌ Reminders/notifications (n8n workflow)
- ❌ Conversation context (multi-turn memory)
- ❌ Weather provider migration from v1.0

**Phase 2:**
- ❌ Events/calendar (use Google Calendar from v1.0 if needed)
- ❌ Media tracking (movies, series, TMDB)
- ❌ Travel docs (tickets, QR codes)
- ❌ Project tracking
- ❌ Web frontend (Astro calendar/list browser)

**Phase 3:**
- ❌ Vector search (ChromaDB for semantic notes)
- ❌ MCP server (claude.ai access to sebastian_db)
- ❌ Shared lists with Rebe
- ❌ Voice output (TTS)

### Success Criteria

**Functional (Features Work):**
1. ✅ Voice/text input → Haiku → correct module → DB update → response
2. ✅ Inventory updates (add/set) work correctly
3. ✅ Low stock items auto-add to shopping list
4. ✅ Shopping list items disappear when bought
5. ✅ Packing lists: recurring items stay, one-time disappear
6. ✅ Notes can be saved, tagged, searched
7. ✅ Sprite expressions match response context

**Behavioral (Actually Useful):**
8. ✅ **Daily use for 2+ weeks** (not just "cool project")
9. ✅ **Lower friction** than scattered notes/texts to Rebe
10. ✅ Haiku understands natural language (stream-of-consciousness is okay)
11. ✅ **Rebe notices** improved organization (fewer "did you buy X?" moments)

**Technical (Reliable):**
12. ✅ Runs stable on seb01 (no crashes, auto-restart)
13. ✅ DB queries fast (<100ms)
14. ✅ Haiku parsing <5% error rate
15. ✅ Clean logs (debuggable via loguru)

### Estimated Effort

**Implementation:** ~3-5 dev sessions (2-4 hours each)
- Session 1: Scaffolding, DB migrations, config
- Session 2: Core modules (Inventory, Shopping, Packing)
- Session 3: Haiku integration, module router
- Session 4: Telegram handlers, response formatting, sprites
- Session 5: Testing, debugging, deployment

**Real-world testing:** 1-2 weeks daily use

**Total:** 2-3 weeks from start to "daily driver"

### What Comes Next

**If Phase 1 succeeds** (daily use for 2+ weeks):
- Phase 1.5: Reminders, migrate weather, conversation context
- Phase 2: Media tracking, travel docs, web frontend

**If Haiku struggles** (>10% parsing errors):
- Add Tier 2 Sonnet agent for ambiguous queries
- OR add Tier 0 regex patterns for common commands

**If Phase 1 fails** (not using it):
- Identify friction (too slow? too many errors? not helpful?)
- Iterate on UX before adding features

---

## 9. Key Design Decisions

### Why Haiku All The Way? (vs. Hybrid 3-Tier)

**Context:** Your draft proposed 3-tier routing (Regex → Haiku → Sonnet).

**Decision:** Single-tier Haiku for Phase 1.

**Reasons:**
- Phase 1 operations are all single-step (no multi-step reasoning needed)
- Voice-first usage means regex patterns save less (voice always needs NLU)
- Haiku is fast enough (1-2s) and cheap enough ($3-5/month)
- Simpler = ships faster, easier to debug
- YAGNI: don't build Tier 0 or Tier 2 until proven necessary

**Trade-off accepted:** Every interaction costs API call (~$0.01). This is acceptable for personal use. Can add Tier 0 patterns later if speed matters, or Tier 2 Sonnet if complexity increases.

### Why Telegram Voice-to-Text? (vs. Whisper API)

**Decision:** Use Telegram's built-in voice transcription, not Whisper API.

**Reasons:**
- Free (included in Telegram)
- One less API call per voice message
- Simpler architecture (no file handling)
- Good enough quality for Spanish
- User willing to "think before speak" (accepts stream-of-consciousness)

**Trade-off accepted:** Transcription quality depends on Telegram. If quality poor, can add Whisper API in Phase 1.5.

### Why Sprites in Phase 1? (vs. Phase 1.5)

**Decision:** Include sprite expressions in Phase 1.

**Reasons:**
- User is already building sprite sheet (high engagement signal)
- Personality increases adoption likelihood (makes testing fun)
- Implementation simple (~1-2 hours, just response formatting)
- From day 1, Sebastian feels alive, not just a database

**Trade-off accepted:** Slightly delays "basic functionality working" milestone by 1-2 hours. This is acceptable because personality is core to making Sebastian engaging.

### Why New Directory? (vs. In-Place Evolution)

**Decision:** Create `sebastian2/` directory, archive v1.0.

**Reasons:**
- v1.0 rarely used → no critical workflows to migrate
- Clean separation (can run both during testing)
- Easy rollback if Phase 1 fails
- Fresh start encourages new patterns

**Trade-off accepted:** Some code duplication (config loading, Telegram setup). This is acceptable because architectures are fundamentally different.

### Why MariaDB? (vs. PostgreSQL or SQLite)

**Decision:** Use existing MariaDB on seb01.

**Reasons:**
- Already running (no new DB overhead)
- Personal data is tiny (<100MB)
- JSON column support adequate (MariaDB 10.x)
- Familiar (used in other seb01 projects)

**Trade-off accepted:** MariaDB's JSON support less powerful than PostgreSQL's JSONB. This is acceptable for Phase 1 scope. Can migrate to PostgreSQL in Phase 3 if JSON querying becomes bottleneck.

---

## 10. Open Questions & Future Considerations

### Resolved During Design

1. ✅ **Google Calendar sync?** - Keep v1.0's Google Calendar as optional Phase 1.5 feature (read-only)
2. ✅ **Multi-user?** - Architecture supports it (user_id everywhere), but Phase 1 is single-user (Josem only)
3. ✅ **Authorization?** - Keep v1.0 pattern (MariaDB table of authorized users can wait for Phase 2)
4. ✅ **Reminders?** - Phase 1.5 via n8n workflow (not critical for Phase 1)

### Still Open (Defer to Implementation)

1. **Haiku prompt engineering** - exact system prompt for intent parsing (iterate during dev)
2. **Sprite mapping edge cases** - what expression for "item not found", "ambiguous query", etc.
3. **Error messages** - friendly Spanish error messages when Haiku can't parse
4. **Threshold defaults** - global default = 2? Or force user to set per-item?
5. **List creation** - auto-create "compra" list on first use, or require explicit creation?

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Haiku parsing errors (>10%) | Medium | High | Add correction flow ("no, corrígelo"), log errors, add Tier 2 Sonnet if needed |
| User doesn't adopt (stops using after 1 week) | Medium | High | Focus on friction points, iterate UX before adding features |
| Telegram voice-to-text quality poor | Low | Medium | Fallback to Whisper API (already exists in v1.0) |
| MariaDB performance slow | Low | Low | Personal data tiny, queries simple, connection pooling |
| Sprite expressions feel gimmicky | Low | Low | Can disable in config, default to text-only |
| Cost exceeds budget ($10/month) | Low | Low | Haiku very cheap, can add Tier 0 patterns to reduce API calls |

---

## 12. Summary

Sebastian 2.0 transforms a rarely-used tech demo into a **daily-driver personal assistant** by solving a real problem: scattered notes and poor organization.

**Core insight:** Persistence + personality + low friction (voice input) = behavior change.

**Phase 1 focus:** Inventory, shopping lists, packing lists, notes - the minimum viable features to solve the real-world organization problem.

**Architecture:** Simple and debuggable (Haiku → Module → MariaDB → Sprite response). No over-engineering, no premature optimization.

**Success metric:** Not "cool project", but **"Rebe notices you're more organized"**.

Let's build it.

---

**Next Steps:**
1. Create implementation plan (via writing-plans skill)
2. Scaffold project structure
3. Implement core modules
4. Test with real usage
5. Iterate based on friction points

**Questions or concerns before implementation?**
