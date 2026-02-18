# Ticket Scanning Module Design — Sebastian 2.0

**Date:** 2026-02-18
**Status:** Approved, pending implementation

---

## Overview

Users can send a photo or document containing a QR code or barcode to Telegram. Sebastian decodes it, associates it with a calendar event, and stores it. When the user asks for the ticket later, Sebastian regenerates and sends back a clean image.

---

## Scope (Phase 1)

- Decode QR codes and barcodes from Telegram photos and documents
- Associate decoded tickets to calendar events (via caption or interactive selection)
- Store ticket data (type, value, image_b64 for Aztec) in `events.notes` JSON field
- Regenerate ticket images on request (QR, linear barcodes, PDF417; Aztec via stored image)
- Multi-user: all authorized users can use the feature

### Out of scope
- PDF scanning (Phase 2)
- Aztec code generation (investigate external library; use image_b64 fallback for now)

---

## Database

Single migration — adds `notes JSON NULL` to the existing `events` table:

```sql
ALTER TABLE events ADD COLUMN notes JSON NULL;
```

### JSON structure

```json
{
  "address": "Calle Gran Vía 45, Madrid",
  "free_text": "Llevar DNI",
  "tickets": [
    {
      "type": "QR_CODE",
      "value": "https://entradas.ejemplo.com/v/ABC123XYZ",
      "added_at": "2026-02-18T19:00:00"
    },
    {
      "type": "AZTEC",
      "value": "encoded_renfe_data",
      "image_b64": "iVBORw0KGgo...",
      "added_at": "2026-02-18T19:01:00"
    }
  ]
}
```

`image_b64` is stored **only for AZTEC** codes (no Python generation library available). For all other types the image is regenerated from `value` on demand.

---

## Decoding Pipeline — `modules/ticket_decoder.py`

Single public function:

```python
def decode_image(image_bytes: bytes) -> list[dict]:
    # Returns list of {type, value} or {type, value, image_b64} for Aztec
    # Returns [] if nothing found
```

**Internally:**
1. Pillow preprocessing: grayscale → adaptive threshold (improves reliability)
2. Try **zxing-cpp** first (QR, Aztec, PDF417, DataMatrix, Code128, EAN...)
3. If empty → try **pyzbar** as fallback
4. Deduplicate results if both find the same value
5. For AZTEC results: attach `image_b64` of the preprocessed image
6. Return `[]` if both fail

---

## Image Generation — `modules/ticket_generator.py`

```python
def generate_image(ticket: dict) -> bytes | None:
    # Returns PNG bytes or None if generation not supported
```

| Type | Library | Notes |
|------|---------|-------|
| QR_CODE | `qrcode` | Clean regeneration, always works |
| CODE_128, EAN_13, EAN_8, CODE_39 | `python-barcode` | Standard linear barcodes |
| PDF417 | `pdf417gen` | Boarding passes, Renfe classic |
| AZTEC | — | Decode `image_b64` from stored JSON |
| Others | — | Return `None`, send text value instead |

---

## Association Flow — `bot/ticket_handler.py`

```
User sends photo/document
        │
        ▼
  Download bytes from Telegram
        │
        ▼
  decode_image(bytes)
        │
   ┌────┴────┐
  [] ?      codes found
   │              │
   ▼              ▼
"No pude    Parse caption (Haiku)
 leer..."   for event reference
                  │
           ┌──────┴──────┐
         clear?        unclear/none
           │              │
           ▼              ▼
     add_ticket()   pending_tickets[user_id] = {
     → "✅ Guardado    tickets: [...],
        en [evento]"   expires_at: now+5min
                     }
                     Bot: "¿A qué cita lo asocio?
                           1. Teatro Bellas Artes (vie 20)
                           2. Dentista (sáb 21)
                           Responde con el número."
```

**Pending state resolution:** next text message from user is intercepted. If it matches a number or event name → `add_ticket()` → clear state.

**State expiry:** `threading.Timer(300, cleanup_func)` restarted on each pending write. Simple, no extra dependencies.

---

## CalendarModule additions — `modules/calendar.py`

```python
def add_ticket(self, event_id: int, ticket: dict) -> dict:
    """Append ticket to events.notes.tickets JSON array."""

def get_event_notes(self, event_id: int) -> dict | None:
    """Return notes JSON for an event, or None."""

def find_upcoming_events(self, limit: int = 5) -> list[dict]:
    """Return next N upcoming events (for pending ticket selection UI)."""
```

`list_events()` and `search_events()` already return `event_id` — callers use it to fetch notes separately.

---

## Showing tickets — parser + router

New action in Haiku parser:

```json
{"module": "calendar", "action": "show_tickets", "query": "teatro"}
```

Spanish examples:
- "qué tickets tengo para el teatro"
- "muéstrame las entradas del concierto del viernes"
- "los tickets del dentista"

Router `_route_calendar` handles `show_tickets`:
1. `search_events(query)` → find event
2. `get_event_notes(event_id)` → extract tickets
3. For each ticket: `generate_image(ticket)` → `bot.send_photo()` or fallback to text
4. Response format:

```
🎟️ Tickets — Teatro Bellas Artes (Viernes 20)

• QR_CODE: https://entradas.ejemplo.com/v/ABC123
[image sent as photo]
```

---

## New Files

| File | Purpose |
|------|---------|
| `db/migrations/005_event_notes.sql` | ALTER TABLE events ADD COLUMN notes |
| `modules/ticket_decoder.py` | decode_image() using zxing-cpp + pyzbar |
| `modules/ticket_generator.py` | generate_image() per code type |
| `bot/ticket_handler.py` | Telegram photo/document handler + pending state |

## Modified Files

| File | Change |
|------|--------|
| `modules/calendar.py` | add_ticket(), get_event_notes(), find_upcoming_events() |
| `core/haiku_parser.py` | show_tickets action + examples |
| `core/router.py` | show_tickets handling in _route_calendar |
| `bot/handlers.py` | Register photo + document handlers from ticket_handler |
| `requirements.txt` | zxing-cpp, pyzbar, qrcode, python-barcode, pdf417gen |

---

## Dependencies

```
zxing-cpp>=2.2.0
pyzbar>=0.1.9          # requires: sudo apt install libzbar0
qrcode>=7.4.2
python-barcode>=0.15.1
pdf417gen>=0.2.0
Pillow>=10.0.0         # already present
```

---

## Out of Scope (Phase 1)

- PDF ticket scanning (Phase 2: pdf2image + poppler)
- Aztec code generation (investigate; fallback = stored image_b64)
- Editing/removing individual tickets from an event
- Bulk ticket import
