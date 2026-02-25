# TOMORROW — Sebastian 2.0

## Session summary (2026-02-25)

### Fixed today
1. **Calendar `update` action** — "Cambia la cita de pilates a las 19:00" was failing with "Acción desconocida: update"
   - `CalendarModule.update_event()` — new method (title, new_time, new_date, new_title, new_all_day)
   - Router: `update` dispatch in `_route_calendar()`
   - Haiku: update action + new_time/new_date/new_title/new_all_day fields + 5 examples

2. **Notes tag editing** — "Pon tag a nota 728: scroogebot" was failing with "Acción desconocida: update"
   - `NotesModule.add_tag()` — fixed return value (was returning None)
   - `NotesModule.remove_tag()` — new method
   - Router: `update` handler in `_route_notes()` using `add_tags[]` / `remove_tags[]` from intent
   - Haiku: add_tags/remove_tags schema fields + 4 examples

3. **Notes append text** — "Añade a nota 97 acordarse de regar las plantas" was failing with "Acción desconocida: unknown"
   - `NotesModule.append_text()` — new method (appends `\n` + text)
   - Router: `append` handler in `_route_notes()`
   - Haiku: append action + 3 examples

4. **refranes.txt** — Deduplicated (~125 → 106 lines) + 7 new weather-themed rhyming refranes

5. **Conversation (Alfred) message bug** — `chat.respond()` was receiving `"..."` instead of the actual user message
   - Root cause: router used `parsed.get('message') or parsed.get('item')`, but Haiku never outputs a `message` field
   - Fix: `handlers.py` now injects `parsed['_raw_message'] = message.text` before routing
   - Fix: `_route_unknown()` uses `parsed.get('_raw_message') or parsed.get('message')`
   - Tests: 3 new tests in `TestRouterDispatch` (including `test_router_passes_raw_message_to_respond`)

### Test counts
- 208 passing / 223 total (15 pre-existing failures in item_list/handlers/integration)

### Pending
- **Deploy to seb01**: migrations 006 (weather) and 007 (conversations) need to run on production
- **Calendar note bug** (next to fix): "añade a la cita de mañana de las 19:00 nota: llevar dinero"
  - Haiku parses: `{module: calendar, action: update, title: None, date: 2026-02-26, time: '19:00', note: 'llevar dinero'}`
  - Error: `'NoneType' object has no attribute 'strip'` in `_route_calendar()` update handler
  - Root cause: `title = intent.get('title', '').strip()` — key exists with value `None`, so `intent.get('title', '')` returns `None`, not `''`
  - Fix needed: `(intent.get('title') or '').strip()` + support note-only update (find event by date+time, add note to it)
