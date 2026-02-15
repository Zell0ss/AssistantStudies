# Sebastian 2.0 — Architecture Document

> **Author:** Claude (Opus) + Josem  
> **Date:** 2026-02-15  
> **Status:** Draft for review  
> **Purpose:** Define architecture for Sebastian's evolution from Q&A bot to full personal assistant

---

## 1. Vision

Sebastian 2.0 is a **personal assistant with persistent memory**, accessible primarily through Telegram (Phase 1) and a web frontend (Phase 2+). It manages notes, lists, events, media tracking, travel documents, and project status — all backed by MariaDB on seb01.

The assistant has **personality** expressed through sprite-based expressions mapped to response context (Phase 1 stretch goal / early Phase 2). A unique sprite sheet will be provided with the different expressions thereof. These expressions will be used to **enhance the response mood** and **add flair and personal touch** to the assistant's responses.

Although comments and documentation on the project will be in english, all the interactions are to be thought for an Spanish user.

Multi-tenant support is supported through separate user id from twelegram in the tables in MariaDB for each user.

Users allowed to use sebastian will be added to a MariaDB table of authorized users, migrating current .env auth user list.

Access to Google calendar & mail (for reading tasks and emails) is only for the main user (me) not sure how to manage this. 

### What changes from Sebastian 1.0

| Aspect | Sebastian 1.0 | Sebastian 2.0 |
|--------|--------------|---------------|
| Core function | Q&A + external API queries | CRUD personal data + conversational AI |
| State | Stateless (no persistence) | MariaDB as source of truth |
| LLM role | Agent selects tools for external APIs | Orchestrator for intent → action on local data |
| Providers | Weather, Calendar, Storage, Transcription | DB, Lists, Events, Media, QR, TMDB + legacy |
| Interface | Telegram only | Telegram + Web frontend for calendar and lists|
| Personality | None | Sprite expressions mapped to response mood |

---

## 2. Infrastructure Constraints

**seb01 specs:** Ubuntu 22.04, 4 vCores, 16GB RAM, 75GB SSD  
**Already running:** Docker, n8n, MariaDB, glasspannel, mangataro, Claude Gazette, current Sebastian bot  
**Available headroom:** ~6-8GB RAM, ~30-40GB disk (estimated)

**Implications:**
- No local LLM — all intelligence via API
- New services must be lightweight (no heavy Docker containers)
- MariaDB is already running — no extra DB overhead
- Python services preferred (familiar stack, .venv pattern)

---

## 3. LLM Strategy: Three-Tier Routing

All LLM calls go through APIs. Routing is by complexity, not by provider.

### Tier 0: Deterministic (no LLM)
- **When:** Intent is unambiguous from patterns
- **Examples:** "añade 3 aguacates a la compra", "¿qué tengo mañana?", "lista de la compra"
- **How:** Regex/keyword matching + entity extraction
- **Cost:** $0, <50ms latency
- **Coverage estimate:** ~40-50% of daily interactions

### Tier 1: Claude Haiku
- **When:** Intent needs NLU but response is structured/short
- **Examples:** "quiero ver algo de ciencia ficción esta noche", "¿cuándo es lo del teatro?", ambiguous commands
- **How:** Claude Haiku with function calling / structured output
- **Cost:** ~$0.25 / vMTok input, $1.25 / MTok output
- **Coverage estimate:** ~30-40% of interactions

### Tier 2: Claude Sonnet
- **When:** Conversational response, reasoning, creative tasks, complex multi-step
- **Examples:** "planifica la semana que viene", "resúmeme qué tengo pendiente", wine notes, creative writing
- **How:** Claude Sonnet with full system prompt + conversation context
- **Cost:** ~$3 / MTok input, $15 / MTok output
- **Coverage estimate:** ~10-20% of interactions

### Estimated monthly cost
Personal use (~50-100 interactions/day): **$3-8/month**

---

## 4. Architecture Approaches

Three approaches considered. All share the same data model and Telegram interface — the difference is in the **orchestration layer**.

### Approach A: "Smart Router" — Intent classifier + direct DB operations

```
Telegram → Bot Handler → Intent Classifier (Tier 0/1) → Module Router
                                                           ├── ListModule.add_item()
                                                           ├── EventModule.create()
                                                           ├── NoteModule.search()
                                                           └── ConversationModule (Tier 2)
                                                                    ↓
                                                              MariaDB ← All modules
```

**How it works:**
1. Message arrives, Tier 0 regex tries to match known patterns
2. If no match, Tier 1 (Haiku) classifies intent + extracts entities as structured JSON
3. Router calls appropriate module method directly
4. Module executes SQL, returns result
5. Response formatted and sent (with sprite selection)

**Pros:**
- Simplest to implement and debug
- Fastest response times (most operations skip LLM entirely)
- Cheapest (minimal API calls)
- Each module is a plain Python class with clear CRUD methods
- Easy to unit test

**Cons:**
- Multi-step operations require explicit chaining logic
- No "reasoning" about complex requests without escalating to Tier 2
- Adding new modules requires updating the router's classification

**Best for:** Getting Phase 1 running fast with reliable, predictable behavior.

---

### Approach B: "Agent with Tools" — LangChain/Claude tool-use agent

```
Telegram → Bot Handler → Agent (Claude Sonnet with tools)
                              ├── tool: list_add(list, item, qty)
                              ├── tool: list_query(list, filter)
                              ├── tool: event_create(title, date, ...)
                              ├── tool: note_save(content, tags)
                              ├── tool: note_search(query)
                              └── tool: db_query(sql)  ← escape hatch
                                       ↓
                                  MariaDB ← All tools
```

**How it works:**
1. Every message goes to Claude Sonnet with a system prompt describing all available tools
2. Claude decides which tool(s) to call, in what order
3. Tools execute against MariaDB, return results
4. Claude formats the response naturally

**Pros:**
- Most natural conversational experience
- Can handle complex multi-step requests ("añade la obra de teatro del viernes y recuérdame el jueves")
- Easy to add new tools without changing routing logic
- Claude handles ambiguity resolution natively

**Cons:**
- Every interaction hits Sonnet API — highest cost (~$15-25/month at 100 interactions/day)
- Latency: 2-5 seconds per interaction even for "¿cuántos aguacates quedan?"
- Harder to debug (LLM decides the flow)
- Occasional hallucinated tool calls or wrong parameter extraction
- Overkill for simple CRUD that doesn't need reasoning

**Best for:** If cost isn't a concern and you want maximum flexibility from day one.

---

### Approach C: "Hybrid" — Smart Router with Agent escalation (RECOMMENDED)

```
Telegram → Bot Handler → Tier 0 Pattern Matcher ──→ Module (direct)
                              │ (no match)              ↓
                              ↓                     MariaDB
                         Tier 1 Haiku Classifier
                              │
                         ┌────┴────────┐
                    Structured intent   Ambiguous / complex
                         │                    │
                    Module (direct)      Tier 2 Sonnet Agent
                         ↓               (with tools)
                     MariaDB                  ↓
                                          MariaDB
```

**How it works:**
1. Tier 0: Regex patterns for common operations (add/remove/list/query)
2. Tier 1: If no pattern match, Haiku classifies intent as structured JSON: `{module, action, params}`
3. If Haiku is confident (>0.8), route directly to module
4. If Haiku is uncertain OR request is multi-step/conversational, escalate to Tier 2 Sonnet agent with full tool access
5. All modules share the same MariaDB operations regardless of which tier called them

**Pros:**
- Best cost/performance balance
- Simple operations are instant and free (Tier 0)
- Complex operations get full agent intelligence (Tier 2)
- Modules are the same regardless of routing — clean separation
- Progressive: start with Tier 0+1, add Tier 2 agent later
- Debuggable: you can see exactly which tier handled each request

**Cons:**
- More moving parts than A or B alone
- Need to maintain pattern matchers AND agent tools
- Edge cases where Tier 1 misroutes (mitigated by escalation to Tier 2)

**Best for:** Production personal assistant that's fast for daily tasks and smart when needed.

### Recommendation

**Approach C (Hybrid)**. Start implementation with only Tier 0 + Tier 1 (no Sonnet agent yet). This gets you a working assistant fast. Add Tier 2 escalation when you have enough real usage to know when you actually need it. The module layer is identical in all approaches, so you're not throwing away work.

---

## 5. Data Model (MariaDB)

Database: `sebastian_db` on seb01's existing MariaDB instance.

All the data will be related to the user asking the bot in telegram, hence the telegram user ID should be stored to retrieve the personalized data. 

### Core Tables

```sql
-- Notes: free-form text with tags
CREATE TABLE notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL, -- telegram user id
    content TEXT NOT NULL,
    tags JSON,                          -- ["personal", "idea", "rebe"]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    archived BOOLEAN DEFAULT FALSE
);

-- Lists: named collections (compra, gijón, proteína, etc.)
CREATE TABLE lists (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL, -- telegram user id
    name VARCHAR(100) NOT NULL UNIQUE,  -- "compra", "gijón_llevar", "gijón_inventario"
    description TEXT,
    list_type ENUM('inventory', 'checklist', 'freeform') DEFAULT 'freeform',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- List items: entries within a list, with optional quantity
CREATE TABLE list_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    list_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    quantity DECIMAL(10,2),             -- NULL for non-quantifiable items
    unit VARCHAR(50),                   -- "unidades", "kg", "gramos", "cucharadas"
    checked BOOLEAN DEFAULT FALSE,      -- for checklists
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
);

-- Events: calendar entries with dates
CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL, -- telegram user id
    title VARCHAR(255) NOT NULL,
    description TEXT,
    event_date DATE NOT NULL,
    event_time TIME,                    -- NULL for all-day events
    end_date DATE,                      -- NULL for single-day
    end_time TIME,
    location VARCHAR(255),
    category ENUM('cita', 'ocio', 'viaje', 'trabajo', 'personal', 'otro') DEFAULT 'otro',
    reminder_minutes INT,               -- minutes before event to remind
    recurrence JSON,                    -- {"type": "weekly", "day": "monday"} or NULL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### Phase 2 Tables

```sql
-- Media tracking: movies, series, books
CREATE TABLE media (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL, -- telegram user id
    title VARCHAR(255) NOT NULL,
    media_type ENUM('movie', 'series', 'book', 'game') NOT NULL,
    status ENUM('pending', 'watching', 'completed', 'dropped') DEFAULT 'pending',
    platform VARCHAR(100),              -- "Netflix", "HBO", "Disney+", "Kindle"
    tmdb_id INT,                        -- The Movie Database ID for metadata
    rating DECIMAL(3,1),                -- personal rating 0-10
    notes TEXT,
    shared_with VARCHAR(100),           -- "rebe", "solo", NULL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Travel documents: tickets, bookings, QR codes
CREATE TABLE travel_docs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL, -- telegram user id
    trip_name VARCHAR(255),             -- "Madrid-Gijón Febrero"
    doc_type ENUM('train', 'flight', 'hotel', 'event_ticket', 'other') NOT NULL,
    carrier VARCHAR(100),               -- "Renfe", "Iberia", "Vueling"
    origin VARCHAR(100),
    destination VARCHAR(100),
    departure_date DATE,
    departure_time TIME,
    arrival_date DATE,
    arrival_time TIME,
    booking_ref VARCHAR(100),           -- localizador
    seat VARCHAR(20),
    barcode_type ENUM('qr', 'code128', 'pdf417', 'aztec'),
    barcode_payload TEXT,               -- raw payload to regenerate
    raw_email_id VARCHAR(255),          -- gmail message ID for reference
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Projects: personal project tracking
CREATE TABLE projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL, -- telegram user id
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status ENUM('idea', 'active', 'paused', 'completed', 'abandoned') DEFAULT 'idea',
    repo_url VARCHAR(500),
    tech_stack JSON,                    -- ["Python", "FastAPI", "MariaDB"]
    priority ENUM('high', 'medium', 'low') DEFAULT 'medium',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### Design Decisions

**Why JSON columns for tags/tech_stack:** MariaDB 10.x supports JSON functions (`JSON_CONTAINS`, `JSON_SEARCH`). Avoids junction tables for simple tag lists. If search becomes a bottleneck, we can add a tags table + full-text index later.

**Why ENUM for categories/status:** Finite, known values. Prevents typo-based data corruption. Easy to extend with ALTER TABLE if needed.

**Why barcode_payload as TEXT:** QR codes can encode up to ~3KB of data. Storing raw payload lets us regenerate the visual representation on demand with python-qrcode/python-barcode without storing images in the DB.

**Why no separate reminders table:** Reminders are a property of events (reminder_minutes). For Phase 1 this is sufficient. If reminder logic gets complex (multiple reminders, snooze, etc.), we extract to a separate table.

---

## 6. Module Architecture

Each domain (lists, notes, events) is a self-contained Python module that:
- Inherits from a `BaseModule` (not BaseProvider — different concern)
- Owns its SQL operations
- Exposes methods that work identically whether called from Tier 0, 1, or 2
- Returns structured results (dict/list) that the response layer formats

```
sebastian2/
├── CLAUDE.md
├── config.yaml
├── requirements.txt
├── sebastian.service
│
├── bot/                        # Telegram interface
│   ├── __init__.py
│   ├── handlers.py             # Command + message handlers
│   └── formatter.py            # Response formatting + sprite selection
│
├── core/                       # Orchestration layer
│   ├── __init__.py
│   ├── router.py               # Tier 0 pattern matcher + Tier 1 classifier
│   ├── agent.py                # Tier 2 Sonnet agent (Phase 1.5+)
│   └── llm.py                  # LLM client abstraction (Haiku/Sonnet)
│
├── modules/                    # Business logic
│   ├── __init__.py
│   ├── base.py                 # BaseModule with DB connection
│   ├── lists.py                # List + item CRUD
│   ├── notes.py                # Notes CRUD + search
│   ├── events.py               # Events CRUD + reminders
│   ├── media.py                # Media tracking (Phase 2)
│   ├── travel.py               # Travel docs + QR (Phase 2)
│   └── projects.py             # Project tracking (Phase 2)
│
├── providers/                  # External service integrations (from v1)
│   ├── __init__.py             # ProviderRegistry
│   ├── base.py                 # BaseProvider with retry
│   ├── weather.py              # OpenMeteo (migrated from v1)
│   └── tmdb.py                 # TMDB API (Phase 2)
│
├── db/                         # Database layer
│   ├── __init__.py
│   ├── connection.py           # MariaDB connection pool
│   └── migrations/             # SQL migration files
│       ├── 001_initial.sql
│       └── 002_phase2.sql
│
├── sprites/                    # Expression images
│   ├── mapping.yaml            # expression → image file
│   └── images/                 # PNG sprites
│
└── utils/
    ├── __init__.py
    ├── config.py               # Config loading
    └── logging.py              # Loguru setup
```

### Module vs Provider distinction

**Modules** operate on local data (MariaDB). They are the core of Sebastian 2.0.  
**Providers** integrate with external APIs (weather, TMDB, etc.). They are inherited from v1.

Both can be called from any routing tier. Both are registered and discoverable. But they have different base classes because the concerns are different (DB transactions vs API retries).

---

## 7. Tier 0: Pattern Matching

Simple but effective. Covers the most common daily operations.

```python
# Example patterns (Spanish-first, English fallback)
PATTERNS = {
    "list_add": [
        r"(?:añade|agrega|pon)\s+(\d+)?\s*(.+?)\s+(?:a|en)\s+(?:la\s+)?(?:lista\s+(?:de\s+)?)?(.+)",
        # "añade 3 aguacates a la compra" → qty=3, item=aguacates, list=compra
        # "pon leche en la lista de la compra" → qty=None, item=leche, list=compra
    ],
    "list_remove": [
        r"(?:quita|elimina|borra)\s+(.+?)\s+(?:de)\s+(?:la\s+)?(?:lista\s+(?:de\s+)?)?(.+)",
    ],
    "list_query": [
        r"(?:qué|que|cuántos?|cuantos?)\s+(?:hay|tengo|queda[n]?)\s+(?:en\s+)?(?:la\s+)?(?:lista\s+(?:de\s+)?)?(.+)",
        r"(?:lista|dame|muestra|enséñame)\s+(?:la\s+)?(?:lista\s+(?:de\s+)?)?(.+)",
    ],
    "event_query_tomorrow": [
        r"(?:qué|que)\s+(?:tengo|hay)\s+(?:mañana|para mañana)",
    ],
    "event_query_date": [
        r"(?:qué|que)\s+(?:tengo|hay)\s+(?:el\s+)?(\d{1,2})\s+(?:de\s+)?(\w+)",
    ],
    "note_add": [
        r"(?:nota|apunta|recuerda)\s*:?\s+(.+)",
    ],
}
```

This is intentionally conservative — it only matches clear, unambiguous patterns. Anything else falls through to Tier 1.

If a question is not understood, the pattern should be passed to the LLM so it can inform the user what queries can be understood to manage the lists, notes and calendar events.

---

## 8. Sprite Expression System

### Concept

Each response includes an `expression` tag that maps to a sprite image. The bot sends the sprite as a photo with the text as caption (or text first, then sprite — TBD based on UX testing).

### Expression Vocabulary (proposed ~12 expressions)
to illustrate we refer to phoenix wright & edgeworth expressions in the game
| Expression | When to use | PW equivalent |
|------------|-------------|---------------|
| `neutral` | Default, informational responses | Phoenix standing normally |
| `thinking` | Processing, searching, "let me check" | Phoenix hand on chin |
| `confident` | Successful operation, clear answer | Phoenix smiling/nodding |
| `surprised` | Unexpected data, "oh interesting" | Phoenix shocked face |
| `concerned` | Warnings, low stock, conflicts | Phoenix worried |
| `triumphant` | Task completed, "done!" | Phoenix pointing (¡OBJECIÓN!) |
| `confused` | Needs clarification, ambiguous input | Phoenix sweating |
| `serious` | Important reminders, deadlines | Edgeworth arms crossed |
| `skeptical` | Questioning, "are you sure?" | Edgeworth smirking |
| `apologetic` | Errors, can't do something | Phoenix nervous |
| `excited` | Good news, fun plans | Phoenix grinning |
| `deadpan` | Dry humor, obvious answers | Edgeworth unimpressed |

the sprite expression sheet will be provided

### Mapping Logic

Expression selection happens in the response formatter, not in the LLM:

- **Tier 0/1 responses:** Expression mapped deterministically from action result (add success → `confident`, empty list → `concerned`, error → `apologetic`, query not understood-> `confused`)
- **Tier 2 responses:** Claude includes an `expression` field in its structured output.


---

## 9. Phasing Plan

### Phase 1: Core Assistant (target: functional in 1 week of dev sessions)

**Scope:**
- New project scaffolding (sebastian2/)
- MariaDB schema: notes, lists, list_items, events
- Modules: ListModule, NoteModule, EventModule
- Tier 0 pattern matching for common operations
- Tier 1 Haiku classification for ambiguous input
- Telegram bot with basic response formatting
- Config migration from v1 (auth, telegram token, etc.)
- systemd service

**Not in Phase 1:**
- Tier 2 Sonnet agent
- Sprite system (text-only responses)
- Web frontend
- Legacy provider migration (weather, etc.)
- Conversation history/context

**Exit criteria:** From Telegram, you can add/query/remove list items, create/query events, save/search notes. All persisted in MariaDB.

### Phase 1.5: Personality + Intelligence

**Scope:**
- Sprite expression system (images + mapping)
- Tier 2 Sonnet agent with tool calling for complex requests
- Conversation context (last N messages stored for multi-turn)
- Reminder system (n8n workflow or cron to check upcoming events and send Telegram notification)
- Migrate weather provider from v1

### Phase 2: Extended Capabilities

**Scope:**
- MediaModule: movie/series tracking with TMDB integration
- TravelModule: ticket storage + QR regeneration
- ProjectModule: project status tracking
- JustWatch/TMDB provider for streaming platform lookup
- Email parsing for travel tickets (Gmail API or n8n workflow)
- Web frontend for calendar view + list browsing (Astro, as you know it from glasspannel/mangataro)

### Phase 3: Advanced

**Scope:**
- Vector DB (ChromaDB) for semantic search across notes
- MCP server for claude.ai direct access to sebastian_db
- n8n integration for automated workflows
- Recurring events and complex scheduling
- Voice messages (Whisper transcription → intent processing)
- Shared lists/events with Rebe (multi-user light)

---

## 10. Technology Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Language | Python 3.11 | Consistent with stack, .venv pattern |
| Telegram lib | pyTelegramBotAPI (telebot) | Same as v1, known quantity |
| DB access | PyMySQL + connection pool | Already used in other projects, no ORM overhead |
| LLM client | anthropic SDK | Direct, no LangChain overhead for structured calls |
| Config | YAML | Same as v1 |
| Logging | loguru | Same as v1 |
| QR/Barcode | python-qrcode + python-barcode | Lightweight, no external deps |
| Migrations | Raw SQL files, manual | Simple enough for personal project |
| Web frontend (Ph2) | Astro + React | Consistent with glasspannel/mangataro |

### Why NOT LangChain for the core

Sebastian 1.0 uses LangChain for agent orchestration. For 2.0, we think **dropping LangChain for the core** and using the Anthropic SDK directly. Reasons:

- The Tier 0/1 routing doesn't need an agent framework at all
- For Tier 2, Claude's native tool_use API is cleaner than LangChain's abstraction
- LangChain adds dependency weight, version churn, and debugging opacity
- You already experienced the `create_openai_functions_agent` pattern — it works but it's a lot of abstraction for what's ultimately "send messages + parse tool calls"

LangChain tools from v1 (wine chains, etc.) can be migrated as simple functions without the framework.

But we will discuss this as every other point in this draft

---

## 11. Open Questions

1. **Name:** Sebastian 2.0. I think we should not call it claude. its a different use/persona. But im open to suggestions
2. **Google Calendar sync:** Keep v1's Google Calendar provider as a read-only secondary source alongside MariaDB events? Or fully replace?
3. **User access:** the users will interact sebastian through telegram, it should be a list in mariadb of authorized users with their ids. This is the same as v1 but perhaps we need to discuss this.
4. **n8n integration:** Use n8n for scheduled tasks (reminders, email parsing) or keep everything in Python? n8n is already running and good for scheduled triggers.

---

## 12. notes

These points, if change, would significantly change this architecture:

1. **seb01 stays as-is** — no migration planned. If in the future we move to a beefier server, local LLM becomes viable again.
2. **Spanish is primary language** — patterns, prompts, and responses are Spanish-first. English is fallback for LLM interactions.
3. **MariaDB 10.x stays** — JSON column support is adequate. If I upgrade to MariaDB 11.x or migrate to PostgreSQL, some queries could be simpler.
4. **Anthropic API access is reliable** — no local fallback. If API goes down, Tier 0 still works but Tier 1/2 degrades.

---
