# Sebastian 2.0 - Progress & Next Steps

**Branch:** `orquestador`
**Date updated:** 2026-03-02
**Status:** 🟢 **274/274 tests passing — branch ready for production testing**

---

## ✅ Completed This Session

### Weather forecast fix
- `_weather_get` and `_weather_forecast` in `core/tool_executor.py` now return `response['result']` (pre-formatted plain text) instead of raw data dicts
- **Why**: Alfred was receiving JSON arrays and generating markdown tables that Telegram can't render
- **Result**: Multi-day forecast now comes out as clean plain text (emoji + temp + precip per line)

### Ticket retrieval via Orchestrator (Option B)
- Added `calendar_get_tickets` and `calendar_clear_tickets` tool definitions to `core/tools/calendar_tools.py`
- Added `_calendar_get_tickets` and `_calendar_clear_tickets` handlers to `core/tool_executor.py`
- `Orchestrator.handle()` now returns `{"text": str, "images": list[bytes]}` instead of bare string
- Added `_collect_images()` — generates ticket images from `calendar_get_tickets` results via `ticket_generator.generate_image()`
- `bot/handlers.py` unpacks the result dict and sends text + photos (`bot.send_photo()`)
- Ticket retrieval now fully integrated: Haiku finds event → gets tickets → Alfred writes response → images sent

### Josem skin (previous session)
- New sprite skin `josem` added to `sprites/images/josem/` (12 webp files)
- Registered in `sprites/mapping.yaml`
- Skin available via `/skin josem` or `/skins`

---

## 🚀 Next Step: Production Testing + PR

The `orquestador` branch is feature-complete and fully tested. The user wants to test in production before creating a PR.

### Deploy to production (migrations 006–008 still needed)
```bash
# Backup
mysqldump -u root -p sebastian_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Stop bot
sudo systemctl stop sebastian.service

# Pull code (after merging or directly pushing)
git pull origin orquestador   # or main after PR

# Run missing migrations (if not already done)
mysql -u root -p sebastian_db < db/migrations/006_weather_settings.sql
mysql -u root -p sebastian_db < db/migrations/007_conversations.sql
mysql -u root -p sebastian_db < db/migrations/008_pending_plans.sql

# Start bot
sudo systemctl start sebastian.service
sudo journalctl -u sebastian.service -f
```

### Smoke tests to run in production
```
✅ "el tiempo esta semana en Madrid"  → plain text forecast (no markdown table)
✅ "qué tickets tengo para el teatro" → Alfred text + ticket images sent as photos
✅ "borra los tickets del teatro"     → tickets cleared
✅ "¿debo llevar paraguas a pilates?" → asks city → resumes → weather answer
✅ /abort                              → "Plan cancelado, señor."
✅ /skin josem                         → activates josem sprites
```

### Create PR when smoke tests pass
Branch `orquestador` → `main`

---

## 📊 Full Feature List (branch `orquestador`)

All these features are implemented, tested (274/274), and committed:

- **Orchestrator** ✅ — Haiku planner (tool loop, max 8 iter) + Sonnet/Alfred synthesizer
- **Pending plans** ✅ — request_clarification tool, save/resume/abort/expire loop state
- **Weather** ✅ — current weather + multi-day forecast (plain text, no markdown tables)
- **Calendar** ✅ — full CRUD + tickets (get/clear via orchestrator)
- **Tickets** ✅ — photo upload + storage; orchestrator retrieval with auto image generation
- **Notes** ✅ — create/append/add_tag/remove_tag/delete
- **Inventory** ✅ — full CRUD + low stock check + set_quantity upserts
- **Lists** ✅ — shopping/packing lists with named list support
- **Sprites** ✅ — josem skin added; `/skin` and `/skins` commands
- **`/abort`** ✅ — cancels open pending plan

---

## 🗂️ Key Files

| File | Purpose |
|------|---------|
| `core/orchestrator.py` | Main pipeline — returns `{"text": str, "images": list}` |
| `core/tool_executor.py` | Tool dispatch (29 tools) |
| `core/tools/` | Anthropic tool definitions per domain |
| `db/pending_plan_repo.py` | Pending plan persistence |
| `db/migrations/008_pending_plans.sql` | Migration needed in production |
| `bot/handlers.py` | Telegram handlers incl. /abort |

---

**Tests:** 274/274 passing
**Branch:** `orquestador` (ahead of `main`)
