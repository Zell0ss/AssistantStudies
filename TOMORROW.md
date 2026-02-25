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

### Test counts
- 206 passing / 221 total (15 pre-existing failures in item_list/handlers/integration)

### Pending
- Deploy to seb01 (migration 006 for weather still needs to run on production)
- Push remaining commits (`git push`)
