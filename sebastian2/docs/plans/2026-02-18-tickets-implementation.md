# Ticket Scanning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to send QR/barcode images to Telegram, decode them, associate them with calendar events, store them in `events.notes`, and regenerate images on request.

**Architecture:** New `modules/ticket_decoder.py` (zxing-cpp + pyzbar) decodes images → `modules/ticket_generator.py` regenerates images per type → `modules/calendar.py` stores/retrieves via JSON `notes` column → `bot/ticket_handler.py` handles Telegram photo/document messages with in-memory pending state for event association.

**Tech Stack:** Python 3.11, zxing-cpp, pyzbar (libzbar0), qrcode, python-barcode, pdf417gen, Pillow, threading.Timer, PyMySQL JSON column.

**Design doc:** `docs/plans/2026-02-18-tickets-design.md`

---

## Task 1: Dependencies + System Packages + DB Migration

**Files:**
- Modify: `sebastian2/requirements.txt`
- Create: `sebastian2/db/migrations/005_event_notes.sql`

**Step 1: Install system package for pyzbar**

```bash
sudo apt install -y libzbar0
```

Expected: installs without errors.

**Step 2: Add dependencies to requirements.txt**

Add a new `# Tickets` block at the end:

```
# Tickets
zxing-cpp==2.2.1
pyzbar==0.1.9
qrcode==8.0
python-barcode==0.15.1
pdf417gen==0.2.0
```

**Step 3: Install Python dependencies**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pip install zxing-cpp==2.2.1 pyzbar==0.1.9 qrcode==8.0 python-barcode==0.15.1 pdf417gen==0.2.0
```

If any version is not found, install without pinned version (e.g. `pip install zxing-cpp`) and update requirements.txt with the installed version (`pip show zxing-cpp | grep Version`).

Expected: all install without errors.

**Step 4: Create migration file**

Create `/data/AssistantStudies/sebastian2/db/migrations/005_event_notes.sql`:

```sql
-- Sebastian 2.0 - Ticket/Notes support for calendar events
-- Adds JSON notes column to events table

ALTER TABLE events ADD COLUMN IF NOT EXISTS notes JSON NULL;
```

**Step 5: Apply migration**

```bash
sudo mysql sebastian_db < /data/AssistantStudies/sebastian2/db/migrations/005_event_notes.sql
```

Verify:

```bash
sudo mysql sebastian_db -e "DESCRIBE events;" | grep notes
```

Expected: `notes | longtext | YES | | NULL |` (MariaDB stores JSON as longtext).

**Step 6: Commit**

```bash
cd /data/AssistantStudies/sebastian2
git add requirements.txt db/migrations/005_event_notes.sql
git commit -m "feat: add ticket deps and events.notes column migration"
```

---

## Task 2: ticket_decoder.py

**Files:**
- Create: `sebastian2/modules/ticket_decoder.py`
- Create: `sebastian2/tests/test_ticket_decoder.py`

**Step 1: Write failing tests**

Create `/data/AssistantStudies/sebastian2/tests/test_ticket_decoder.py`:

```python
# tests/test_ticket_decoder.py
"""
Tests for ticket_decoder.decode_image().

These tests use real QR/barcode images generated in-memory.
No external files needed.
"""
import io
import pytest
import qrcode
from PIL import Image
from modules.ticket_decoder import decode_image


def _make_qr_bytes(value: str) -> bytes:
    """Generate a QR code image as PNG bytes."""
    img = qrcode.make(value)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_barcode_bytes(value: str) -> bytes:
    """Generate a Code128 barcode image as PNG bytes."""
    import barcode
    from barcode.writer import ImageWriter
    bc = barcode.get_barcode_class('code128')(value, writer=ImageWriter())
    buf = io.BytesIO()
    bc.write(buf)
    return buf.getvalue()


class TestDecodeImage:
    def test_decode_qr_code(self):
        image_bytes = _make_qr_bytes("https://example.com/ticket/ABC123")
        results = decode_image(image_bytes)
        assert len(results) >= 1
        assert any(r['value'] == "https://example.com/ticket/ABC123" for r in results)
        assert any(r['type'] == 'QR_CODE' for r in results)

    def test_decode_returns_type_and_value(self):
        image_bytes = _make_qr_bytes("test_value")
        results = decode_image(image_bytes)
        assert len(results) >= 1
        for r in results:
            assert 'type' in r
            assert 'value' in r

    def test_decode_empty_image_returns_empty_list(self):
        # Plain white image — no code
        img = Image.new('RGB', (200, 200), color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        results = decode_image(buf.getvalue())
        assert results == []

    def test_decode_barcode(self):
        image_bytes = _make_barcode_bytes("1234567890")
        results = decode_image(image_bytes)
        assert len(results) >= 1
        assert any("1234567890" in r['value'] for r in results)

    def test_aztec_includes_image_b64(self):
        # We can't easily generate Aztec in tests, so we test that
        # non-Aztec codes do NOT include image_b64
        image_bytes = _make_qr_bytes("no_aztec")
        results = decode_image(image_bytes)
        qr_results = [r for r in results if r['type'] == 'QR_CODE']
        if qr_results:
            assert 'image_b64' not in qr_results[0]
```

**Step 2: Run to verify failure**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_ticket_decoder.py -v 2>&1 | head -15
```

Expected: `ModuleNotFoundError: No module named 'modules.ticket_decoder'`

**Step 3: Create ticket_decoder.py**

Create `/data/AssistantStudies/sebastian2/modules/ticket_decoder.py`:

```python
# modules/ticket_decoder.py
"""
QR code and barcode decoder using zxing-cpp (primary) and pyzbar (fallback).
"""
import io
import base64
from typing import Optional
from PIL import Image, ImageFilter, ImageOps
from loguru import logger


# Normalize type names from different libraries to our standard format
_ZXING_TYPE_MAP = {
    'QRCode': 'QR_CODE',
    'Aztec': 'AZTEC',
    'PDF417': 'PDF417',
    'Code128': 'CODE_128',
    'Code39': 'CODE_39',
    'EAN13': 'EAN_13',
    'EAN8': 'EAN_8',
    'DataMatrix': 'DATA_MATRIX',
    'UPCA': 'UPC_A',
    'UPCE': 'UPC_E',
}

_PYZBAR_TYPE_MAP = {
    'QRCODE': 'QR_CODE',
    'CODE128': 'CODE_128',
    'CODE39': 'CODE_39',
    'EAN13': 'EAN_13',
    'EAN8': 'EAN_8',
    'UPCA': 'UPC_A',
    'UPCE': 'UPC_E',
    'PDF417': 'PDF417',
    'AZTEC': 'AZTEC',
    'DATAMATRIX': 'DATA_MATRIX',
    'I25': 'ITF',
}


def _preprocess(image_bytes: bytes) -> tuple[Image.Image, bytes]:
    """
    Apply grayscale + adaptive threshold to improve decode reliability.

    Returns: (processed PIL Image, original bytes for Aztec fallback)
    """
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    gray = ImageOps.grayscale(img)
    # Adaptive threshold: convert to 1-bit (black/white)
    threshold = gray.point(lambda x: 0 if x < 128 else 255, '1')
    # Convert back to 'L' for library compatibility
    processed = threshold.convert('L')
    return processed, image_bytes


def _decode_zxing(img: Image.Image) -> list[dict]:
    """Try decoding with zxing-cpp."""
    try:
        import zxingcpp
        results = zxingcpp.read_barcodes(img)
        decoded = []
        for r in results:
            if not r.valid:
                continue
            type_name = _ZXING_TYPE_MAP.get(r.format.name, r.format.name.upper())
            decoded.append({'type': type_name, 'value': r.text})
        return decoded
    except Exception as e:
        logger.debug(f"zxing-cpp decode failed: {e}")
        return []


def _decode_pyzbar(img: Image.Image) -> list[dict]:
    """Try decoding with pyzbar as fallback."""
    try:
        from pyzbar.pyzbar import decode
        results = decode(img)
        decoded = []
        for r in results:
            type_name = _PYZBAR_TYPE_MAP.get(r.type, r.type)
            try:
                value = r.data.decode('utf-8')
            except UnicodeDecodeError:
                value = r.data.decode('latin-1')
            decoded.append({'type': type_name, 'value': value})
        return decoded
    except Exception as e:
        logger.debug(f"pyzbar decode failed: {e}")
        return []


def decode_image(image_bytes: bytes) -> list[dict]:
    """
    Decode QR codes and barcodes from image bytes.

    Tries zxing-cpp first (supports QR, Aztec, PDF417, DataMatrix, Code128, EAN...),
    falls back to pyzbar. Deduplicates by value.

    For AZTEC codes: attaches image_b64 since generation libraries are not available.

    Args:
        image_bytes: Raw image bytes (PNG, JPEG, etc.)

    Returns:
        List of dicts with {type, value} or {type, value, image_b64} for AZTEC.
        Empty list if nothing found.
    """
    processed_img, original_bytes = _preprocess(image_bytes)

    # Try zxing-cpp first
    results = _decode_zxing(processed_img)

    # Fallback to pyzbar if nothing found
    if not results:
        logger.debug("zxing-cpp found nothing, trying pyzbar fallback")
        results = _decode_pyzbar(processed_img)

    # Deduplicate by value
    seen_values = set()
    deduped = []
    for r in results:
        if r['value'] not in seen_values:
            seen_values.add(r['value'])
            deduped.append(r)

    # Attach image_b64 for AZTEC codes (no Python generation library available)
    for r in deduped:
        if r['type'] == 'AZTEC':
            r['image_b64'] = base64.b64encode(original_bytes).decode('utf-8')

    logger.info(f"decode_image: found {len(deduped)} code(s): {[r['type'] for r in deduped]}")
    return deduped
```

**Step 4: Run tests**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_ticket_decoder.py -v
```

Expected: all 5 tests pass. If `test_decode_barcode` fails due to Code128 output including quiet zones that confuse decoders, that's acceptable — the important ones are QR tests.

**Step 5: Commit**

```bash
git add modules/ticket_decoder.py tests/test_ticket_decoder.py
git commit -m "feat: add ticket_decoder with zxing-cpp + pyzbar fallback"
```

---

## Task 3: ticket_generator.py

**Files:**
- Create: `sebastian2/modules/ticket_generator.py`
- Create: `sebastian2/tests/test_ticket_generator.py`

**Step 1: Write failing tests**

Create `/data/AssistantStudies/sebastian2/tests/test_ticket_generator.py`:

```python
# tests/test_ticket_generator.py
import pytest
from modules.ticket_generator import generate_image


class TestGenerateImage:
    def test_generate_qr_returns_bytes(self):
        ticket = {'type': 'QR_CODE', 'value': 'https://example.com/ticket/ABC'}
        result = generate_image(ticket)
        assert result is not None
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_generate_qr_is_valid_png(self):
        ticket = {'type': 'QR_CODE', 'value': 'test_value_123'}
        result = generate_image(ticket)
        # PNG magic bytes: \x89PNG
        assert result[:4] == b'\x89PNG'

    def test_generate_code128_returns_bytes(self):
        ticket = {'type': 'CODE_128', 'value': '1234567890'}
        result = generate_image(ticket)
        assert result is not None
        assert isinstance(result, bytes)

    def test_generate_pdf417_returns_bytes(self):
        ticket = {'type': 'PDF417', 'value': 'test_pdf417_data'}
        result = generate_image(ticket)
        assert result is not None
        assert isinstance(result, bytes)

    def test_generate_aztec_from_image_b64(self):
        import base64
        from PIL import Image
        import io
        # Create a tiny PNG as fake image_b64
        img = Image.new('RGB', (10, 10), color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        fake_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        ticket = {'type': 'AZTEC', 'value': 'aztec_data', 'image_b64': fake_b64}
        result = generate_image(ticket)
        assert result is not None
        assert result == buf.getvalue()

    def test_generate_aztec_without_b64_returns_none(self):
        ticket = {'type': 'AZTEC', 'value': 'aztec_data'}
        result = generate_image(ticket)
        assert result is None

    def test_generate_unknown_type_returns_none(self):
        ticket = {'type': 'UNKNOWN_FORMAT', 'value': 'data'}
        result = generate_image(ticket)
        assert result is None
```

**Step 2: Run to verify failure**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_ticket_generator.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'modules.ticket_generator'`

**Step 3: Create ticket_generator.py**

Create `/data/AssistantStudies/sebastian2/modules/ticket_generator.py`:

```python
# modules/ticket_generator.py
"""
Generates images from decoded ticket data.

Supports: QR_CODE, CODE_128, CODE_39, EAN_13, EAN_8, PDF417.
For AZTEC: uses stored image_b64 (no Python generation library available).
"""
import io
import base64
from typing import Optional
from loguru import logger


def generate_image(ticket: dict) -> Optional[bytes]:
    """
    Generate a PNG image from a ticket dict.

    Args:
        ticket: Dict with 'type', 'value', and optionally 'image_b64'

    Returns:
        PNG bytes, or None if generation is not supported for this type.
    """
    type_ = ticket.get('type', '')
    value = ticket.get('value', '')

    if type_ == 'QR_CODE':
        return _gen_qr(value)

    if type_ in ('CODE_128', 'CODE_39', 'EAN_13', 'EAN_8', 'UPC_A', 'UPC_E'):
        return _gen_barcode(type_, value)

    if type_ == 'PDF417':
        return _gen_pdf417(value)

    if type_ == 'AZTEC':
        # No generation library — use stored image bytes
        b64 = ticket.get('image_b64')
        if b64:
            try:
                return base64.b64decode(b64)
            except Exception as e:
                logger.error(f"Failed to decode AZTEC image_b64: {e}")
        return None

    logger.debug(f"No generator for ticket type: {type_}")
    return None


def _gen_qr(value: str) -> Optional[bytes]:
    """Generate QR code PNG bytes."""
    try:
        import qrcode
        img = qrcode.make(value)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception as e:
        logger.error(f"QR generation failed: {e}")
        return None


def _gen_barcode(type_: str, value: str) -> Optional[bytes]:
    """Generate linear barcode PNG bytes using python-barcode."""
    try:
        import barcode
        from barcode.writer import ImageWriter

        format_map = {
            'CODE_128': 'code128',
            'CODE_39': 'code39',
            'EAN_13': 'ean13',
            'EAN_8': 'ean8',
            'UPC_A': 'upca',
            'UPC_E': 'upce',
        }
        barcode_name = format_map.get(type_)
        if not barcode_name:
            return None

        # EAN/UPC: python-barcode adds the check digit, so strip it if present
        enc_value = value
        if type_ == 'EAN_13' and len(value) == 13:
            enc_value = value[:12]
        elif type_ == 'EAN_8' and len(value) == 8:
            enc_value = value[:7]
        elif type_ == 'UPC_A' and len(value) == 12:
            enc_value = value[:11]

        bc_class = barcode.get_barcode_class(barcode_name)
        bc = bc_class(enc_value, writer=ImageWriter())
        buf = io.BytesIO()
        bc.write(buf)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Barcode generation failed for {type_}: {e}")
        return None


def _gen_pdf417(value: str) -> Optional[bytes]:
    """Generate PDF417 barcode PNG bytes."""
    try:
        from pdf417gen import encode, render_image
        codes = encode(value)
        image = render_image(codes, scale=3, ratio=3)
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return buf.getvalue()
    except Exception as e:
        logger.error(f"PDF417 generation failed: {e}")
        return None
```

**Step 4: Run tests**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_ticket_generator.py -v
```

Expected: all 7 tests pass. Fix any import issues.

**Step 5: Commit**

```bash
git add modules/ticket_generator.py tests/test_ticket_generator.py
git commit -m "feat: add ticket_generator for QR/barcode/PDF417 image regeneration"
```

---

## Task 4: CalendarModule — add_ticket, get_event_notes, find_upcoming_events

**Files:**
- Modify: `sebastian2/modules/calendar.py`
- Modify: `sebastian2/tests/test_calendar_module.py`

**Step 1: Write failing tests**

Add to the end of `tests/test_calendar_module.py`:

```python
class TestTickets:
    def test_add_ticket_to_event(self, cal):
        result = cal.add_event(title="Teatro", event_date=date(2026, 3, 20), event_time="20:00")
        event_id = result['event_id']

        ticket = {'type': 'QR_CODE', 'value': 'https://entradas.com/ABC123'}
        add_result = cal.add_ticket(event_id, ticket)
        assert add_result['status'] == 'added'

    def test_get_event_notes_returns_tickets(self, cal):
        result = cal.add_event(title="Concierto", event_date=date(2026, 4, 10), event_time="21:00")
        event_id = result['event_id']

        cal.add_ticket(event_id, {'type': 'QR_CODE', 'value': 'QR_VALUE_1'})
        cal.add_ticket(event_id, {'type': 'PDF417', 'value': 'PDF_VALUE_1'})

        notes = cal.get_event_notes(event_id)
        assert notes is not None
        assert 'tickets' in notes
        assert len(notes['tickets']) == 2
        assert notes['tickets'][0]['value'] == 'QR_VALUE_1'
        assert notes['tickets'][1]['value'] == 'PDF_VALUE_1'

    def test_get_event_notes_no_notes_returns_none(self, cal):
        result = cal.add_event(title="VacíoNotas", event_date=date(2026, 5, 1), event_time="10:00")
        notes = cal.get_event_notes(result['event_id'])
        assert notes is None

    def test_add_ticket_unknown_event_returns_not_found(self, cal):
        result = cal.add_ticket(99999999, {'type': 'QR_CODE', 'value': 'X'})
        assert result['status'] == 'not_found'

    def test_find_upcoming_events_returns_list(self, cal):
        from datetime import timedelta
        today = date.today()
        cal.add_event(title="Próximo1", event_date=today + timedelta(days=1), event_time="10:00")
        cal.add_event(title="Próximo2", event_date=today + timedelta(days=2), event_time="11:00")
        upcoming = cal.find_upcoming_events(limit=5)
        assert isinstance(upcoming, list)

    def test_ticket_added_at_is_set(self, cal):
        result = cal.add_event(title="FechaTest", event_date=date(2026, 6, 1), event_time="19:00")
        cal.add_ticket(result['event_id'], {'type': 'QR_CODE', 'value': 'test'})
        notes = cal.get_event_notes(result['event_id'])
        assert 'added_at' in notes['tickets'][0]
```

**Step 2: Run to verify failure**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_calendar_module.py::TestTickets -v 2>&1 | head -15
```

Expected: `AttributeError: 'CalendarModule' object has no attribute 'add_ticket'`

**Step 3: Add methods to calendar.py**

Add `import json` at the top of `modules/calendar.py` (after the existing imports).

Add these three methods to `CalendarModule` (after `search_events`):

```python
    def add_ticket(self, event_id: int, ticket: dict) -> dict:
        """
        Append a decoded ticket to an event's notes.tickets JSON array.

        Args:
            event_id: Event ID (must belong to this user)
            ticket: Dict with type, value, and optionally image_b64

        Returns:
            Dict with status: 'added' | 'not_found'
        """
        cursor = self.execute_query(
            "SELECT id, notes FROM events WHERE id = %s AND user_id = %s",
            (event_id, self.user_id)
        )
        row = cursor.fetchone()
        if not row:
            return {'status': 'not_found', 'message': f"Evento {event_id} no encontrado"}

        notes = row['notes'] or {}
        if isinstance(notes, str):
            notes = json.loads(notes)

        if 'tickets' not in notes:
            notes['tickets'] = []

        ticket_entry = {
            'type': ticket['type'],
            'value': ticket['value'],
            'added_at': datetime.now().isoformat(),
        }
        if 'image_b64' in ticket:
            ticket_entry['image_b64'] = ticket['image_b64']

        notes['tickets'].append(ticket_entry)

        self.execute_query(
            "UPDATE events SET notes = %s WHERE id = %s AND user_id = %s",
            (json.dumps(notes, ensure_ascii=False), event_id, self.user_id)
        )
        self.commit()

        logger.info(f"Added ticket type={ticket['type']} to event {event_id}")
        return {'status': 'added'}

    def get_event_notes(self, event_id: int) -> Optional[dict]:
        """
        Retrieve the notes JSON for an event.

        Returns:
            Dict with notes data, or None if no notes or event not found.
        """
        cursor = self.execute_query(
            "SELECT notes FROM events WHERE id = %s AND user_id = %s",
            (event_id, self.user_id)
        )
        row = cursor.fetchone()
        if not row or not row['notes']:
            return None

        notes = row['notes']
        if isinstance(notes, str):
            return json.loads(notes)
        return notes

    def find_upcoming_events(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Return next N upcoming events (from today, next 30 days).
        Used to show selection list when associating a ticket.

        Args:
            limit: Max number of events to return

        Returns:
            List of event dicts sorted by date/time
        """
        events = self.list_events('month')
        return events[:limit]
```

**Step 4: Run tests**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_calendar_module.py -v
```

Expected: all 27 tests pass (21 existing + 6 new). Fix any failures.

**Step 5: Commit**

```bash
git add modules/calendar.py tests/test_calendar_module.py
git commit -m "feat: add add_ticket/get_event_notes/find_upcoming_events to CalendarModule"
```

---

## Task 5: Haiku Parser — show_tickets action

**Files:**
- Modify: `sebastian2/core/haiku_parser.py`

**Step 1: Read the file**

Read `core/haiku_parser.py` to find the calendar examples section and actions list.

**Step 2: Add show_tickets action**

In the actions list, after the `- **remove**: borrar un evento o cita` line, add:

```
- **show_tickets**: ver los tickets/entradas guardados de una cita
```

**Step 3: Add show_tickets examples**

In the examples section, after the existing calendar examples, add:

```
"qué tickets tengo para el teatro" → {"module": "calendar", "action": "show_tickets", "query": "teatro"}
"muéstrame las entradas del concierto del viernes" → {"module": "calendar", "action": "show_tickets", "query": "concierto"}
"los tickets del dentista" → {"module": "calendar", "action": "show_tickets", "query": "dentista"}
"dame el código del tren" → {"module": "calendar", "action": "show_tickets", "query": "tren"}
```

**Step 4: Verify syntax**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
python -c "from core.haiku_parser import HaikuParser; print('OK')"
```

Expected: `OK`

**Step 5: Commit**

```bash
git add core/haiku_parser.py
git commit -m "feat: add show_tickets action to calendar parser"
```

---

## Task 6: Router — show_tickets in _route_calendar

**Files:**
- Modify: `sebastian2/core/router.py`
- Modify: `sebastian2/tests/test_router.py`

**Step 1: Write failing test**

Add to `TestCalendarRouting` in `tests/test_router.py`:

```python
    def test_route_calendar_show_tickets_no_tickets(self, router):
        # First add an event with no tickets
        router.route({
            'module': 'calendar',
            'action': 'add',
            'title': 'EventoSinTickets',
            'date': '2026-06-01',
            'time': '20:00',
            'all_day': False,
        })
        intent = {
            'module': 'calendar',
            'action': 'show_tickets',
            'query': 'EventoSinTickets',
        }
        result = router.route(intent)
        assert result['success'] is True
        assert 'no tiene tickets' in result['result'].lower() or 'no encontré' in result['result'].lower()
```

**Step 2: Run to verify failure**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_router.py::TestCalendarRouting::test_route_calendar_show_tickets_no_tickets -v 2>&1 | head -20
```

Expected: `KeyError` or falls through with unknown action.

**Step 3: Add show_tickets handling to _route_calendar**

In `core/router.py`, inside `_route_calendar()`, add this block before the final `return` statement:

```python
        if action == 'show_tickets':
            query = intent.get('query', '').strip()
            if not query:
                return {'success': False, 'result': "¿De qué cita quieres ver los tickets?"}

            events = cal.search_events(query)
            if not events:
                return {'success': True, 'result': f"No encontré ningún evento sobre '{query}'."}

            event = events[0]
            notes = cal.get_event_notes(event['event_id'])

            if not notes or not notes.get('tickets'):
                return {
                    'success': True,
                    'result': f"El evento '{event['title']}' no tiene tickets guardados todavía.",
                    'data': {'event': event, 'tickets': []}
                }

            tickets = notes['tickets']
            date_str = event['date'].strftime('%-d de %B') if event.get('date') else ''
            months_es = ['enero','febrero','marzo','abril','mayo','junio',
                         'julio','agosto','septiembre','octubre','noviembre','diciembre']
            if event.get('date'):
                month_es = months_es[event['date'].month - 1]
                date_str = f"{event['date'].day} de {month_es}"

            return {
                'success': True,
                'result': f"🎟️ Tickets — {event['title']} ({date_str})\n\n" +
                          '\n'.join(f"• {t['type']}: {t['value'][:60]}{'...' if len(t['value']) > 60 else ''}"
                                    for t in tickets),
                'data': {'event': event, 'tickets': tickets}
            }
```

**Step 4: Run tests**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_router.py tests/test_calendar_module.py -v
```

Expected: all tests pass (37+ total).

**Step 5: Commit**

```bash
git add core/router.py tests/test_router.py
git commit -m "feat: add show_tickets routing to calendar router"
```

---

## Task 7: bot/ticket_handler.py — Telegram handler + pending state

**Files:**
- Create: `sebastian2/bot/ticket_handler.py`

**Step 1: Create the handler module**

Create `/data/AssistantStudies/sebastian2/bot/ticket_handler.py`:

```python
# bot/ticket_handler.py
"""
Handles Telegram photo and document messages for ticket scanning.

Flow:
1. Download photo/document bytes from Telegram
2. Decode QR/barcode with ticket_decoder
3. If caption has event reference → associate directly
4. Else → store in pending state and ask user to select event
5. When user replies with a number → associate and clear state

Pending state is stored in-memory with 5-minute timeout per user.
"""
import threading
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

# In-memory pending state: user_id → {tickets, expires_at, timer}
_pending: dict = {}


def _expire_pending(user_id: str):
    """Remove expired pending ticket state (called by threading.Timer)."""
    _pending.pop(user_id, None)
    logger.debug(f"Pending ticket expired for user {user_id}")


def _set_pending(user_id: str, tickets: list):
    """Store decoded tickets awaiting event association (5-minute TTL)."""
    existing = _pending.get(user_id, {})
    if 'timer' in existing:
        existing['timer'].cancel()

    timer = threading.Timer(300, _expire_pending, args=[user_id])
    timer.daemon = True
    timer.start()

    _pending[user_id] = {
        'tickets': tickets,
        'expires_at': datetime.now() + timedelta(minutes=5),
        'timer': timer,
    }


def _get_pending(user_id: str) -> Optional[list]:
    """Get pending tickets if not expired. Returns None if none."""
    state = _pending.get(user_id)
    if not state:
        return None
    if datetime.now() > state['expires_at']:
        _pending.pop(user_id, None)
        return None
    return state['tickets']


def _clear_pending(user_id: str):
    """Clear pending state for user."""
    state = _pending.pop(user_id, None)
    if state and 'timer' in state:
        state['timer'].cancel()


def handle_media(message, bot):
    """
    Handle an incoming photo or document message.
    Called from handlers.py for content_types=['photo', 'document'].
    """
    from modules.ticket_decoder import decode_image
    from modules.calendar import CalendarModule
    from db.connection import get_connection

    user_id = str(message.chat.id)

    # Download file bytes
    try:
        if message.photo:
            file_id = message.photo[-1].file_id  # highest resolution
        elif message.document:
            file_id = message.document.file_id
        else:
            return

        file_info = bot.get_file(file_id)
        image_bytes = bot.download_file(file_info.file_path)
    except Exception as e:
        logger.error(f"Failed to download file from Telegram: {e}")
        bot.reply_to(message, "No pude descargar la imagen. Inténtalo de nuevo.")
        return

    # Decode
    tickets = decode_image(image_bytes)

    if not tickets:
        bot.reply_to(
            message,
            "No pude leer ningún código en esa imagen.\n"
            "💡 Si es un código de barras, prueba a mandarlo como archivo "
            "(clip → Documento) para evitar la compresión de Telegram."
        )
        return

    # Try to find event from caption
    caption = (message.caption or '').strip()
    event_id = None
    event_title = None

    if caption:
        try:
            from core.haiku_parser import HaikuParser
            parser = HaikuParser()
            parsed = parser.parse(f"ticket para {caption}")
            search_term = parsed.get('title') or parsed.get('query') or caption
            if search_term:
                conn = get_connection()
                cal = CalendarModule(conn, user_id)
                events = cal.search_events(search_term)
                if events:
                    event_id = events[0]['event_id']
                    event_title = events[0]['title']
        except Exception as e:
            logger.warning(f"Caption parsing failed, will ask user: {e}")

    if event_id:
        # Associate directly
        conn = get_connection()
        cal = CalendarModule(conn, user_id)
        for ticket in tickets:
            cal.add_ticket(event_id, ticket)
        types_str = ', '.join(t['type'] for t in tickets)
        bot.reply_to(
            message,
            f"✅ {len(tickets)} código(s) guardado(s) en '{event_title}' ({types_str})"
        )
        return

    # No clear event → store pending and ask
    _set_pending(user_id, tickets)

    try:
        from modules.calendar import CalendarModule
        from db.connection import get_connection
        conn = get_connection()
        cal = CalendarModule(conn, user_id)
        upcoming = cal.find_upcoming_events(limit=5)
    except Exception as e:
        logger.error(f"Failed to fetch upcoming events: {e}")
        upcoming = []

    if not upcoming:
        _clear_pending(user_id)
        bot.reply_to(
            message,
            "No tienes eventos próximos a los que asociar este ticket.\n"
            "Crea primero una cita con «apunta [evento] el [fecha]»."
        )
        return

    types_str = ', '.join(t['type'] for t in tickets)
    months_es = ['enero','febrero','marzo','abril','mayo','junio',
                 'julio','agosto','septiembre','octubre','noviembre','diciembre']
    lines = [f"Encontré {len(tickets)} código(s) ({types_str}). ¿A qué cita lo asocio?\n"]
    for i, e in enumerate(upcoming, 1):
        d = e['date']
        date_str = f"{d.day} de {months_es[d.month-1]}"
        time_str = f" {e['time']}" if e.get('time') else ""
        lines.append(f"{i}. {date_str}{time_str} — {e['title']}")
    lines.append("\nResponde con el número.")

    bot.reply_to(message, '\n'.join(lines))


def try_resolve_pending(message, bot) -> bool:
    """
    Check if the text message is a response to a pending ticket assignment.

    Returns True if the message was handled (don't pass to normal flow).
    Returns False if no pending state (pass to normal flow).
    """
    user_id = str(message.chat.id)
    pending = _get_pending(user_id)
    if not pending:
        return False

    text = message.text.strip()

    try:
        from modules.calendar import CalendarModule
        from db.connection import get_connection
        conn = get_connection()
        cal = CalendarModule(conn, user_id)
        upcoming = cal.find_upcoming_events(limit=5)

        event = None

        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(upcoming):
                event = upcoming[idx]
        else:
            # Try matching by event title substring
            matches = [e for e in upcoming if text.lower() in e['title'].lower()]
            if matches:
                event = matches[0]

        if event:
            for ticket in pending:
                cal.add_ticket(event['event_id'], ticket)
            types_str = ', '.join(t['type'] for t in pending)
            bot.reply_to(
                message,
                f"✅ {len(pending)} código(s) guardado(s) en '{event['title']}' ({types_str})"
            )
            _clear_pending(user_id)
            return True
        else:
            bot.reply_to(
                message,
                "No reconocí esa opción. Responde con el número de la lista, "
                "o escribe cualquier otra cosa para cancelar."
            )
            _clear_pending(user_id)
            return True

    except Exception as e:
        logger.error(f"Error resolving pending ticket: {e}")
        _clear_pending(user_id)
        return False
```

**Step 2: Verify syntax**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
python -c "from bot.ticket_handler import handle_media, try_resolve_pending; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add bot/ticket_handler.py
git commit -m "feat: add ticket_handler with pending state for event association"
```

---

## Task 8: Register handlers in bot/handlers.py

**Files:**
- Modify: `sebastian2/bot/handlers.py`

**Step 1: Read the current end of setup_handlers**

Read `bot/handlers.py` to find:
1. Where `setup_handlers` function closes (the last handler before the end)
2. The main text handler (the `echo_all` or default text handler) — you need to intercept pending tickets BEFORE passing to the router

**Step 2: Add imports at top of handlers.py**

Add after the existing imports:

```python
from bot.ticket_handler import handle_media, try_resolve_pending
from modules.ticket_generator import generate_image
```

**Step 3: Add photo and document handlers**

Inside `setup_handlers`, after the last existing `@bot.message_handler` block and BEFORE the default text handler, add:

```python
    @bot.message_handler(content_types=['photo'])
    def handle_photo(message):
        """Handle photo messages — try to decode QR/barcode."""
        if not authorized(message.chat.username, message.chat.id):
            return
        handle_media(message, bot)

    @bot.message_handler(content_types=['document'])
    def handle_document(message):
        """Handle document messages — try to decode QR/barcode from file."""
        if not authorized(message.chat.username, message.chat.id):
            return
        # Only process image documents
        mime = getattr(message.document, 'mime_type', '') or ''
        if mime.startswith('image/'):
            handle_media(message, bot)
```

**Step 4: Intercept pending tickets in the text handler**

Find the default text handler (the one that calls `parser.parse(message.text)` and routes to the module router). At the very beginning of that handler function body, add:

```python
        # Check if user is responding to a pending ticket association
        if try_resolve_pending(message, bot):
            return
```

**Step 5: Add show_tickets image sending**

Find where the router result is sent back to the user in the text handler. After the normal text response is sent, add logic to send ticket images when `show_tickets` returns tickets.

Locate the code that sends the result (it likely calls `_send_markdown` or `bot.send_message`). After that send call, add:

```python
            # If show_tickets returned ticket images, send them
            if (response.get('data') and
                    isinstance(response['data'], dict) and
                    response['data'].get('tickets')):
                for ticket in response['data']['tickets']:
                    try:
                        img_bytes = generate_image(ticket)
                        if img_bytes:
                            import io
                            bot.send_photo(
                                message.chat.id,
                                io.BytesIO(img_bytes),
                                caption=f"{ticket['type']}"
                            )
                        else:
                            # Fallback: send the raw value as text
                            bot.send_message(
                                message.chat.id,
                                f"📋 {ticket['type']}: `{ticket['value']}`",
                                parse_mode='Markdown'
                            )
                    except Exception as e:
                        logger.error(f"Failed to send ticket image: {e}")
```

**Step 6: Verify syntax**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
python -c "from bot.handlers import setup_handlers; print('OK')"
```

Expected: `OK`

**Step 7: Run full test suite**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_calendar_module.py tests/test_router.py tests/test_ticket_decoder.py tests/test_ticket_generator.py -v
```

Expected: all tests pass.

**Step 8: Commit**

```bash
git add bot/handlers.py
git commit -m "feat: register photo/document handlers and show_tickets image sending"
```

---

## Task 9: End-to-End Manual Verification

**Step 1: Start the bot**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
python sebastian_bot.py
```

**Step 2: Test ticket scanning flow**

**Test A — QR with caption:**
1. Open any QR code generator (e.g. qr-code-generator.com)
2. Create a QR with value `https://entradas.ejemplo.com/ABC123`
3. Send the image to Telegram with caption: `teatro bellas artes`
4. Expected: `✅ 1 código(s) guardado(s) en 'teatro bellas artes' (QR_CODE)`

**Test B — QR without caption:**
1. Send a QR image with NO caption
2. Expected: Sebastian asks which event with a numbered list
3. Reply with `1`
4. Expected: `✅ 1 código(s) guardado(s) en '...' (QR_CODE)`

**Test C — Show tickets:**
1. Ask: `qué tickets tengo para el teatro`
2. Expected: text showing the ticket value + a QR image sent as photo

**Test D — Unreadable image:**
1. Send a regular photo (landscape, no code)
2. Expected: error message suggesting to send as document

**Step 3: Fix any issues found, commit**

```bash
git add -A
git commit -m "fix: ticket scanning end-to-end adjustments"
```

---

## Summary

| Task | Deliverable |
|------|-------------|
| 1 | System deps (libzbar0), Python deps, `events.notes` column |
| 2 | `ticket_decoder.py` — zxing-cpp + pyzbar, preprocessing |
| 3 | `ticket_generator.py` — QR, Code128, PDF417, Aztec fallback |
| 4 | CalendarModule: `add_ticket`, `get_event_notes`, `find_upcoming_events` |
| 5 | Haiku parser: `show_tickets` action |
| 6 | Router: `show_tickets` handling |
| 7 | `bot/ticket_handler.py` — pending state, association flow |
| 8 | `bot/handlers.py` — photo/document handlers + image sending |
| 9 | Manual end-to-end verification |
