# Calendar Module Design — Sebastian 2.0

**Date:** 2026-02-18
**Status:** Approved, pending implementation

---

## Overview

New `calendar` module for managing personal events via natural language (Spanish). Follows the existing architecture: Haiku parser → Router → Module → MySQL.

---

## Scope

### Phase 1 (this implementation)
- Single events (timed and all-day)
- Recurring events (daily, weekly, monthly)
- On-demand queries by time window and content search
- Daily morning reminder via APScheduler

### Phase 2 (future)
- Notes/attachments per event: `notes JSON NULL` field
  - Structured data: address, phone, link, QR text, free text
  - No schema redesign needed — just add the JSON column

---

## Database Schema

Single new table `events`:

```sql
CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    event_date DATE NULL,               -- for all-day events
    start_datetime DATETIME NULL,       -- for timed events
    end_datetime DATETIME NULL,         -- optional (duration)
    all_day BOOLEAN DEFAULT FALSE,
    recurrence_rule VARCHAR(100) NULL,  -- NULL = single event (see below)
    recurrence_end DATE NULL,           -- when recurrence stops (NULL = forever)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_event_date (event_date),
    INDEX idx_start_datetime (start_datetime)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### Recurrence rule format

| Value | Meaning |
|-------|---------|
| `NULL` | Single event |
| `'daily'` | Every day |
| `'weekly:MON'` | Every Monday |
| `'weekly:MON,WED,FRI'` | Multiple days per week |
| `'monthly:15'` | 15th of every month |
| `'monthly:first-TUE'` | First Tuesday of every month |

---

## Actions

| Action | Example (Spanish) | Parser fields |
|--------|-------------------|---------------|
| `add` | "apunta dentista el jueves a las 5" | title, date, time |
| `add` | "el 15 es el cumpleaños de rebe" | title, date, all_day=true |
| `add` | "cada lunes tengo inglés a las 7" | title, time, recurrence_rule |
| `add` | "inglés cada lunes y miércoles a las 7 hasta junio" | title, time, recurrence_rule, recurrence_end |
| `list` | "qué tengo hoy / mañana / esta semana / en marzo" | time_window |
| `search` | "cuándo tengo dentista" / "próxima reunión" | query |
| `remove` | "borra el dentista del jueves" | title + date |
| `remove` | "borra el inglés" (recurrent) | title → Sebastian asks: solo esta vez o todas? |

### Remove of recurring events

When removing a recurring event, Sebastian asks for clarification:
- **"¿Solo esta ocurrencia o todas?"**
  - "Solo esta" → stores an exception date (or simply not shown for that day)
  - "Todas" → deletes the event record entirely

---

## Parser — new fields for Haiku

New `calendar` module added to `haiku_parser.py` system prompt:

```json
{
  "module": "calendar",
  "action": "add | list | search | remove",
  "title": "dentista",
  "date": "2026-02-20",
  "time": "17:00",
  "all_day": false,
  "recurrence_rule": "weekly:MON",
  "recurrence_end": "2026-06-30",
  "time_window": "today | tomorrow | week | month | YYYY-MM",
  "query": "dentista"
}
```

**Key:** Haiku resolves relative dates to absolute dates. The current date is injected into the system prompt. Examples:
- "el jueves" → `"date": "2026-02-19"`
- "mañana" → `"date": "2026-02-19"`
- "esta semana" → `"time_window": "week"`
- "en marzo" → `"time_window": "2026-03"`

---

## Module — `modules/calendar.py`

Class `CalendarModule` with methods:

- `add_event(title, date, time, all_day, recurrence_rule, recurrence_end)` → dict with status
- `list_events(time_window)` → list of events (expanding recurring ones via `dateutil.rrule`)
- `search_events(query)` → list of matching events
- `remove_event(title, date)` → bool; for recurring: return disambiguation info

### Recurring event expansion

Uses `python-dateutil` (`dateutil.rrule`) to expand recurring events into the queried date range. The module translates the internal `recurrence_rule` string to an `rrule` object at query time.

---

## Daily Reminder

**Library:** APScheduler (BackgroundScheduler)
**Integration:** Started in `main.py` alongside the bot

**Behavior:**
- Runs every morning at configurable time (default `08:00`)
- Configured in `config.yaml`: `calendar.daily_reminder_time: "08:00"`
- Queries each authorized user's events for today (single + recurring)
- If no events → sends nothing (no spam)
- Format:

```
📅 Buenos días! Tu agenda de hoy:

• 09:00 — Dentista
• 13:00 — Comida con Pedro
• 🔄 19:00 — Inglés

Que tengas un buen día!
```

The 🔄 emoji marks recurring events.

---

## New Files

| File | Purpose |
|------|---------|
| `modules/calendar.py` | CalendarModule class |
| `db/migrations/004_calendar.sql` | events table |

## Modified Files

| File | Change |
|------|--------|
| `core/haiku_parser.py` | Add calendar module + actions + examples |
| `core/router.py` | Add `_route_calendar()` method |
| `main.py` | Start APScheduler for daily reminder |
| `requirements.txt` | Add `APScheduler`, ensure `python-dateutil` present |
| `utils/config.py` | Support `calendar.daily_reminder_time` config key |

---

## Dependencies

```
APScheduler>=3.10.0
python-dateutil>=2.8.0   # likely already installed as transitive dep
```

---

## Out of Scope (Phase 1)

- Google Calendar sync
- Multi-user/shared events
- Event attachments / QR codes (Phase 2: `notes JSON NULL` column)
- Push notifications beyond daily summary
- Event editing (modify existing event)
