# Calendar Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a calendar module to Sebastian 2.0 that stores personal events in MySQL and supports natural language commands in Spanish for adding, listing, searching, and removing events (single, all-day, and recurring), plus a daily morning reminder via APScheduler.

**Architecture:** Haiku parser extracts structured calendar intent → Router dispatches to CalendarModule → CalendarModule queries/writes MySQL `events` table. Recurring events are stored once with a `recurrence_rule` string and expanded at query time using `dateutil.rrule`. APScheduler runs as a background thread inside the bot process and fires the morning summary.

**Tech Stack:** Python 3.11, PyMySQL, `python-dateutil` (rrule), `APScheduler>=3.10`, Claude Haiku 4.5 (parser), pyTelegramBotAPI.

**Design doc:** `docs/plans/2026-02-18-calendar-design.md`

---

## Task 1: Dependencies and Database Migration

**Files:**
- Modify: `sebastian2/requirements.txt`
- Create: `sebastian2/db/migrations/004_calendar.sql`

**Step 1: Add dependencies to requirements.txt**

Add after the `# LLM` block:

```
APScheduler==3.10.4
python-dateutil==2.9.0
```

**Step 2: Install dependencies**

```bash
cd sebastian2
source .venv/bin/activate
pip install APScheduler==3.10.4 python-dateutil==2.9.0
```

Expected: both install without errors.

**Step 3: Create the migration file**

Create `sebastian2/db/migrations/004_calendar.sql`:

```sql
-- Sebastian 2.0 - Calendar Module
-- Adds events table for personal calendar management

CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    event_date DATE NULL,               -- for all-day events
    start_datetime DATETIME NULL,       -- for timed events
    end_datetime DATETIME NULL,         -- optional end time
    all_day BOOLEAN DEFAULT FALSE,
    recurrence_rule VARCHAR(100) NULL,  -- NULL=single | 'daily' | 'weekly:MON' | 'weekly:MON,WED' | 'monthly:15' | 'monthly:first-TUE'
    recurrence_end DATE NULL,           -- when recurrence stops (NULL = forever)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_event_date (event_date),
    INDEX idx_start_datetime (start_datetime)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Step 4: Apply migration to DB**

```bash
mysql -u <user> <dbname> < db/migrations/004_calendar.sql
```

Verify:
```bash
mysql -u <user> <dbname> -e "DESCRIBE events;"
```

Expected: table with columns id, user_id, title, event_date, start_datetime, end_datetime, all_day, recurrence_rule, recurrence_end, created_at, updated_at.

**Step 5: Commit**

```bash
git add requirements.txt db/migrations/004_calendar.sql
git commit -m "feat: add APScheduler/dateutil deps and events table migration"
```

---

## Task 2: CalendarModule — Core (add, remove, get)

**Files:**
- Create: `sebastian2/modules/calendar.py`
- Create: `sebastian2/tests/test_calendar_module.py`

**Step 1: Write the failing tests**

Create `sebastian2/tests/test_calendar_module.py`:

```python
# tests/test_calendar_module.py
import pytest
from datetime import date, datetime
from modules.calendar import CalendarModule
from db.connection import get_connection, close_connection


@pytest.fixture
def cal(db_conn):
    user_id = "test_user_calendar"
    module = CalendarModule(db_conn, user_id)
    # Cleanup before test
    cursor = db_conn.cursor()
    cursor.execute("DELETE FROM events WHERE user_id = %s", (user_id,))
    db_conn.commit()
    yield module
    # Cleanup after test
    cursor.execute("DELETE FROM events WHERE user_id = %s", (user_id,))
    db_conn.commit()


@pytest.fixture
def db_conn():
    conn = get_connection()
    yield conn
    close_connection()


class TestAddEvent:
    def test_add_single_timed_event(self, cal):
        result = cal.add_event(
            title="Dentista",
            event_date=date(2026, 3, 10),
            event_time="17:00",
            all_day=False
        )
        assert result['status'] == 'added'
        assert 'Dentista' in result['message']

    def test_add_all_day_event(self, cal):
        result = cal.add_event(
            title="Cumpleaños Rebe",
            event_date=date(2026, 3, 15),
            all_day=True
        )
        assert result['status'] == 'added'

    def test_add_recurring_weekly_event(self, cal):
        result = cal.add_event(
            title="Inglés",
            event_date=date(2026, 2, 18),
            event_time="19:00",
            all_day=False,
            recurrence_rule="weekly:MON"
        )
        assert result['status'] == 'added'

    def test_add_recurring_with_end_date(self, cal):
        result = cal.add_event(
            title="Pilates",
            event_date=date(2026, 2, 18),
            event_time="10:00",
            all_day=False,
            recurrence_rule="weekly:WED",
            recurrence_end=date(2026, 6, 30)
        )
        assert result['status'] == 'added'


class TestRemoveEvent:
    def test_remove_existing_event(self, cal):
        cal.add_event(title="Dentista", event_date=date(2026, 3, 10), event_time="17:00")
        result = cal.remove_event(title="Dentista", event_date=date(2026, 3, 10))
        assert result['status'] == 'removed'

    def test_remove_nonexistent_event(self, cal):
        result = cal.remove_event(title="NoExiste", event_date=date(2026, 3, 10))
        assert result['status'] == 'not_found'

    def test_remove_recurring_returns_disambiguation(self, cal):
        cal.add_event(
            title="Inglés",
            event_date=date(2026, 2, 16),
            event_time="19:00",
            recurrence_rule="weekly:MON"
        )
        result = cal.remove_event(title="Inglés")
        assert result['status'] == 'needs_clarification'
        assert 'recurrent' in result or 'recurring' in result.get('type', '')
```

**Step 2: Run tests to verify they fail**

```bash
cd sebastian2
source .venv/bin/activate
pytest tests/test_calendar_module.py -v
```

Expected: `ModuleNotFoundError: No module named 'modules.calendar'`

**Step 3: Implement CalendarModule**

Create `sebastian2/modules/calendar.py`:

```python
# modules/calendar.py
"""
Calendar module - personal event management with recurrence support.
"""
from datetime import date, datetime, time
from typing import Optional, List, Dict, Any
from modules.base import BaseModule
from loguru import logger


class CalendarModule(BaseModule):
    """
    Manages personal calendar events.

    Supports:
    - Single events (timed or all-day)
    - Recurring events (daily, weekly, monthly)
    - Querying by time window or content search
    - Removing single or recurring events

    recurrence_rule format:
        None         → single event
        'daily'      → every day
        'weekly:MON' → every Monday (MON,TUE,WED,THU,FRI,SAT,SUN)
        'weekly:MON,WED,FRI' → multiple days
        'monthly:15' → 15th of each month
        'monthly:first-TUE' → first Tuesday of each month
    """

    def add_event(
        self,
        title: str,
        event_date: Optional[date] = None,
        event_time: Optional[str] = None,
        all_day: bool = False,
        recurrence_rule: Optional[str] = None,
        recurrence_end: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Add a new event.

        Args:
            title: Event title
            event_date: Date of event (or start date for recurring)
            event_time: Time as "HH:MM" string (None for all-day)
            all_day: True if all-day event
            recurrence_rule: Recurrence pattern string or None
            recurrence_end: Date when recurrence ends (None = forever)

        Returns:
            Dict with status ('added') and message
        """
        start_datetime = None
        if event_date and event_time and not all_day:
            h, m = map(int, event_time.split(':'))
            start_datetime = datetime.combine(event_date, time(h, m))

        query = """
            INSERT INTO events
                (user_id, title, event_date, start_datetime, all_day,
                 recurrence_rule, recurrence_end)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor = self.execute_query(query, (
            self.user_id,
            title,
            event_date if all_day else None,
            start_datetime,
            all_day,
            recurrence_rule,
            recurrence_end,
        ))
        self.commit()

        logger.info(f"Added event '{title}' for user {self.user_id}")
        return {
            'status': 'added',
            'message': f"Evento añadido: {title}",
            'event_id': cursor.lastrowid
        }

    def remove_event(
        self,
        title: str,
        event_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Remove an event by title (and optionally date).

        If the event is recurring and no date is given, returns a
        'needs_clarification' status so the caller can ask the user.

        Args:
            title: Event title (case-insensitive)
            event_date: Specific date (for timed events); None = search by title only

        Returns:
            Dict with status: 'removed' | 'not_found' | 'needs_clarification'
        """
        # Find matching events
        if event_date:
            query = """
                SELECT id, recurrence_rule FROM events
                WHERE user_id = %s AND LOWER(title) = LOWER(%s)
                AND (DATE(start_datetime) = %s OR event_date = %s)
            """
            cursor = self.execute_query(query, (self.user_id, title, event_date, event_date))
        else:
            query = """
                SELECT id, recurrence_rule FROM events
                WHERE user_id = %s AND LOWER(title) = LOWER(%s)
            """
            cursor = self.execute_query(query, (self.user_id, title))

        rows = cursor.fetchall()

        if not rows:
            return {'status': 'not_found', 'message': f"No encontré ningún evento llamado '{title}'"}

        # If recurring and no specific date → ask for clarification
        recurring_rows = [r for r in rows if r['recurrence_rule']]
        if recurring_rows and not event_date:
            return {
                'status': 'needs_clarification',
                'type': 'recurring',
                'message': (
                    f"'{title}' es un evento recurrente. ¿Borro solo una ocurrencia o todas?\n"
                    f"• \"borra el {title} de esta semana\" (solo esta vez)\n"
                    f"• \"borra todos los {title}\" (elimina el evento)"
                ),
                'event_id': recurring_rows[0]['id']
            }

        # Delete all matched rows
        ids = [r['id'] for r in rows]
        placeholders = ', '.join(['%s'] * len(ids))
        self.execute_query(
            f"DELETE FROM events WHERE id IN ({placeholders})",
            tuple(ids)
        )
        self.commit()

        logger.info(f"Removed {len(ids)} event(s) named '{title}' for user {self.user_id}")
        return {'status': 'removed', 'message': f"Evento eliminado: {title}"}

    def remove_event_by_id(self, event_id: int) -> bool:
        """Remove a specific event by ID."""
        cursor = self.execute_query(
            "DELETE FROM events WHERE id = %s AND user_id = %s",
            (event_id, self.user_id)
        )
        self.commit()
        return cursor.rowcount > 0
```

**Step 4: Run tests**

```bash
pytest tests/test_calendar_module.py::TestAddEvent tests/test_calendar_module.py::TestRemoveEvent -v
```

Expected: all tests pass.

**Step 5: Commit**

```bash
git add modules/calendar.py tests/test_calendar_module.py
git commit -m "feat: add CalendarModule with add/remove event support"
```

---

## Task 3: CalendarModule — list_events with recurring expansion

**Files:**
- Modify: `sebastian2/modules/calendar.py`
- Modify: `sebastian2/tests/test_calendar_module.py`

**Step 1: Write failing tests**

Add to `tests/test_calendar_module.py`:

```python
class TestListEvents:
    def test_list_today(self, cal):
        today = date.today()
        cal.add_event(title="Reunión", event_date=today, event_time="10:00")
        events = cal.list_events('today')
        assert any(e['title'] == 'Reunión' for e in events)

    def test_list_today_excludes_other_days(self, cal):
        from datetime import timedelta
        tomorrow = date.today() + timedelta(days=1)
        cal.add_event(title="Mañana", event_date=tomorrow, event_time="10:00")
        events = cal.list_events('today')
        assert not any(e['title'] == 'Mañana' for e in events)

    def test_list_week_includes_7_days(self, cal):
        from datetime import timedelta
        today = date.today()
        cal.add_event(title="Fin de semana", event_date=today + timedelta(days=6), event_time="12:00")
        events = cal.list_events('week')
        assert any(e['title'] == 'Fin de semana' for e in events)

    def test_recurring_weekly_appears_in_range(self, cal):
        # Add a weekly:MON recurring event starting in the past
        from datetime import timedelta
        # Find next Monday
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)

        cal.add_event(
            title="Inglés",
            event_date=next_monday,
            event_time="19:00",
            recurrence_rule="weekly:MON"
        )
        events = cal.list_events('week')
        titles = [e['title'] for e in events]
        assert 'Inglés' in titles

    def test_recurring_marks_recurrent_flag(self, cal):
        from datetime import timedelta
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)
        cal.add_event(
            title="Yoga",
            event_date=next_monday,
            event_time="08:00",
            recurrence_rule="weekly:MON"
        )
        events = cal.list_events('week')
        yoga_events = [e for e in events if e['title'] == 'Yoga']
        assert len(yoga_events) >= 1
        assert yoga_events[0]['recurring'] is True

    def test_recurring_with_end_date_excludes_after_end(self, cal):
        from datetime import timedelta
        today = date.today()
        yesterday = today - timedelta(days=1)
        # Recurrence ended yesterday → should not appear today
        cal.add_event(
            title="Expirado",
            event_date=today - timedelta(days=30),
            event_time="10:00",
            recurrence_rule="daily",
            recurrence_end=yesterday
        )
        events = cal.list_events('today')
        assert not any(e['title'] == 'Expirado' for e in events)
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_calendar_module.py::TestListEvents -v
```

Expected: `AttributeError: 'CalendarModule' object has no attribute 'list_events'`

**Step 3: Implement list_events**

Add to `sebastian2/modules/calendar.py` (after the imports, add dateutil imports at top of file):

```python
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU
from dateutil.parser import parse as parse_dt
```

Add constant and methods to `CalendarModule`:

```python
    _WEEKDAY_MAP = {
        'MON': MO, 'TUE': TU, 'WED': WE, 'THU': TH,
        'FRI': FR, 'SAT': SA, 'SUN': SU
    }

    def _rule_to_rrule(self, rule_str: str, start_dt: datetime, until_date: Optional[date]):
        """Convert recurrence_rule string to dateutil rrule object."""
        until = datetime.combine(until_date, time(23, 59)) if until_date else None

        if rule_str == 'daily':
            return rrule(DAILY, dtstart=start_dt, until=until)

        if rule_str.startswith('weekly:'):
            days_str = rule_str[7:]  # e.g. 'MON' or 'MON,WED,FRI'
            days = [self._WEEKDAY_MAP[d.strip()] for d in days_str.split(',')]
            return rrule(WEEKLY, byweekday=days, dtstart=start_dt, until=until)

        if rule_str.startswith('monthly:'):
            spec = rule_str[8:]  # e.g. '15' or 'first-TUE'
            if spec.isdigit():
                return rrule(MONTHLY, bymonthday=int(spec), dtstart=start_dt, until=until)
            # e.g. 'first-TUE'
            ordinal_map = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'last': -1}
            parts = spec.split('-')
            ordinal = ordinal_map[parts[0]]
            weekday = self._WEEKDAY_MAP[parts[1]](ordinal)
            return rrule(MONTHLY, byweekday=weekday, dtstart=start_dt, until=until)

        return None

    def _time_window_to_range(self, time_window: str):
        """Convert time_window string to (start_date, end_date) tuple."""
        from datetime import timedelta
        today = date.today()

        if time_window == 'today':
            return today, today
        if time_window == 'tomorrow':
            return today + timedelta(days=1), today + timedelta(days=1)
        if time_window == 'week':
            # Current week: today → today+6
            return today, today + timedelta(days=6)
        if time_window == 'month':
            import calendar
            last_day = calendar.monthrange(today.year, today.month)[1]
            return today, date(today.year, today.month, last_day)
        # YYYY-MM format
        if len(time_window) == 7 and '-' in time_window:
            import calendar
            year, month = map(int, time_window.split('-'))
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, last_day)

        return today, today  # fallback

    def list_events(self, time_window: str) -> List[Dict[str, Any]]:
        """
        List events in the given time window, expanding recurring events.

        Args:
            time_window: 'today' | 'tomorrow' | 'week' | 'month' | 'YYYY-MM'

        Returns:
            List of event dicts sorted by datetime, each with:
            {title, date, time, all_day, recurring, event_id}
        """
        start_date, end_date = self._time_window_to_range(time_window)
        start_dt = datetime.combine(start_date, time(0, 0))
        end_dt = datetime.combine(end_date, time(23, 59, 59))

        # Fetch all candidate events: single events in range + all recurring events
        query = """
            SELECT id, title, event_date, start_datetime, end_datetime,
                   all_day, recurrence_rule, recurrence_end
            FROM events
            WHERE user_id = %s
            AND (
                recurrence_rule IS NOT NULL
                OR (all_day = TRUE AND event_date BETWEEN %s AND %s)
                OR (all_day = FALSE AND start_datetime BETWEEN %s AND %s)
            )
            ORDER BY start_datetime, event_date
        """
        cursor = self.execute_query(query, (
            self.user_id,
            start_date, end_date,
            start_dt, end_dt
        ))
        rows = cursor.fetchall()

        results = []

        for row in rows:
            rule_str = row['recurrence_rule']

            if not rule_str:
                # Single event — already in range from WHERE clause
                results.append(self._row_to_event_dict(row, recurring=False))
                continue

            # Recurring event: expand within range
            base_dt = row['start_datetime'] or datetime.combine(
                row['event_date'] or date.today(), time(0, 0)
            )
            rule = self._rule_to_rrule(rule_str, base_dt, row['recurrence_end'])
            if not rule:
                continue

            occurrences = rule.between(start_dt, end_dt, inc=True)
            for occ in occurrences:
                event = self._row_to_event_dict(row, recurring=True)
                event['date'] = occ.date()
                event['time'] = occ.strftime('%H:%M') if not row['all_day'] else None
                results.append(event)

        # Sort by date then time
        results.sort(key=lambda e: (e['date'], e['time'] or '00:00'))
        return results

    def _row_to_event_dict(self, row: dict, recurring: bool) -> Dict[str, Any]:
        """Convert a DB row to a clean event dict."""
        if row['start_datetime']:
            event_date = row['start_datetime'].date()
            event_time = row['start_datetime'].strftime('%H:%M')
        else:
            event_date = row['event_date']
            event_time = None

        return {
            'event_id': row['id'],
            'title': row['title'],
            'date': event_date,
            'time': event_time,
            'all_day': bool(row['all_day']),
            'recurring': recurring,
        }
```

**Step 4: Run tests**

```bash
pytest tests/test_calendar_module.py::TestListEvents -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add modules/calendar.py tests/test_calendar_module.py
git commit -m "feat: add list_events with recurring event expansion via dateutil.rrule"
```

---

## Task 4: CalendarModule — search_events

**Files:**
- Modify: `sebastian2/modules/calendar.py`
- Modify: `sebastian2/tests/test_calendar_module.py`

**Step 1: Write failing tests**

Add to `tests/test_calendar_module.py`:

```python
class TestSearchEvents:
    def test_search_finds_by_title(self, cal):
        cal.add_event(title="Dentista", event_date=date(2026, 5, 10), event_time="17:00")
        cal.add_event(title="Reunión Pedro", event_date=date(2026, 5, 11), event_time="10:00")
        results = cal.search_events("dentista")
        assert len(results) == 1
        assert results[0]['title'] == 'Dentista'

    def test_search_case_insensitive(self, cal):
        cal.add_event(title="Dentista", event_date=date(2026, 5, 10), event_time="17:00")
        results = cal.search_events("DENTISTA")
        assert len(results) == 1

    def test_search_no_results(self, cal):
        results = cal.search_events("cita_inexistente_xyz")
        assert results == []

    def test_search_returns_next_upcoming_first(self, cal):
        from datetime import timedelta
        today = date.today()
        cal.add_event(title="Revisión", event_date=today + timedelta(days=30), event_time="09:00")
        cal.add_event(title="Revisión", event_date=today + timedelta(days=10), event_time="09:00")
        results = cal.search_events("Revisión")
        assert results[0]['date'] == today + timedelta(days=10)
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_calendar_module.py::TestSearchEvents -v
```

Expected: `AttributeError: 'CalendarModule' object has no attribute 'search_events'`

**Step 3: Implement search_events**

Add to `CalendarModule` in `modules/calendar.py`:

```python
    def search_events(self, query: str) -> List[Dict[str, Any]]:
        """
        Search events by title (case-insensitive, partial match).

        Returns events sorted by date (soonest first), including future
        occurrences of recurring events.

        Args:
            query: Search string

        Returns:
            List of event dicts
        """
        cursor = self.execute_query(
            """
            SELECT id, title, event_date, start_datetime, end_datetime,
                   all_day, recurrence_rule, recurrence_end
            FROM events
            WHERE user_id = %s AND LOWER(title) LIKE LOWER(%s)
            ORDER BY start_datetime, event_date
            """,
            (self.user_id, f'%{query}%')
        )
        rows = cursor.fetchall()

        from datetime import timedelta
        today = date.today()
        results = []

        for row in rows:
            rule_str = row['recurrence_rule']

            if not rule_str:
                results.append(self._row_to_event_dict(row, recurring=False))
                continue

            # For recurring: find next occurrence from today
            base_dt = row['start_datetime'] or datetime.combine(
                row['event_date'] or today, time(0, 0)
            )
            rule = self._rule_to_rrule(rule_str, base_dt, row['recurrence_end'])
            if not rule:
                continue

            now = datetime.combine(today, time(0, 0))
            next_occ = rule.after(now, inc=True)
            if next_occ:
                event = self._row_to_event_dict(row, recurring=True)
                event['date'] = next_occ.date()
                event['time'] = next_occ.strftime('%H:%M') if not row['all_day'] else None
                results.append(event)

        results.sort(key=lambda e: (e['date'], e['time'] or '00:00'))
        return results
```

**Step 4: Run tests**

```bash
pytest tests/test_calendar_module.py::TestSearchEvents -v
```

Expected: all pass.

**Step 5: Run full test suite**

```bash
pytest tests/test_calendar_module.py -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add modules/calendar.py tests/test_calendar_module.py
git commit -m "feat: add search_events to CalendarModule"
```

---

## Task 5: Update Haiku Parser for Calendar

**Files:**
- Modify: `sebastian2/core/haiku_parser.py`

**Step 1: Understand what to add**

Open `sebastian2/core/haiku_parser.py`. In the `system_prompt` string, find the modules list and add `calendar`. This requires:
- Injecting today's date so Haiku can resolve relative dates ("mañana", "el jueves")
- Adding `calendar` to the module list
- Adding new actions: `add`, `list`, `search`, `remove`
- Adding new JSON fields: `date`, `time`, `all_day`, `recurrence_rule`, `recurrence_end`, `time_window`, `query`
- Adding ~15 Spanish examples

**Step 2: Inject today's date into parse()**

In `haiku_parser.py`, modify the `parse()` method to inject the current date at the top of the system prompt. Locate the `system_prompt = """..."""` string and change the start of it:

```python
def parse(self, user_message):
    from datetime import date
    today_str = date.today().strftime('%Y-%m-%d')
    today_weekday = date.today().strftime('%A')  # e.g. 'Wednesday'

    system_prompt = f"""Hoy es {today_str} ({today_weekday}). Eres un asistente que parsea mensajes en español a JSON estructurado.
```

Note: change the `system_prompt = """` to `system_prompt = f"""` and add the date line at the very top.

**Step 3: Add calendar to the modules list in the prompt**

In the modules section, add:
```
- **calendar**: eventos y citas personales (dentista, reuniones, cumpleaños)
```

**Step 4: Add calendar actions to the Acciones section**

Add in the actions block:
```
- **add**: añadir/apuntar evento o cita
- **list**: ver agenda (hoy, mañana, esta semana, este mes, en marzo)
- **search**: buscar evento por nombre ("cuándo tengo dentista")
- **remove**: borrar un evento o cita
```

**Step 5: Add calendar fields to the JSON schema section**

In the JSON output schema, add:
```
  "date": "YYYY-MM-DD (fecha del evento, resuelta desde lenguaje natural)",
  "time": "HH:MM (hora del evento, 24h)",
  "all_day": true/false,
  "recurrence_rule": "daily | weekly:MON | weekly:MON,WED | monthly:15 | monthly:first-TUE | null",
  "recurrence_end": "YYYY-MM-DD o null",
  "time_window": "today | tomorrow | week | month | YYYY-MM",
  "query": "texto de búsqueda (para search)"
```

**Step 6: Add Spanish calendar examples**

Add these examples to the prompt (after the existing examples):

```
"apunta dentista el jueves a las 5" → {"module": "calendar", "action": "add", "title": "dentista", "date": "2026-02-19", "time": "17:00", "all_day": false}
"el 15 de marzo es el cumpleaños de rebe" → {"module": "calendar", "action": "add", "title": "cumpleaños rebe", "date": "2026-03-15", "all_day": true}
"cada lunes tengo inglés a las 7" → {"module": "calendar", "action": "add", "title": "inglés", "time": "19:00", "all_day": false, "recurrence_rule": "weekly:MON"}
"inglés cada lunes y miércoles a las 7 hasta junio" → {"module": "calendar", "action": "add", "title": "inglés", "time": "19:00", "recurrence_rule": "weekly:MON,WED", "recurrence_end": "2026-06-30"}
"todos los días tengo medicación a las 8" → {"module": "calendar", "action": "add", "title": "medicación", "time": "08:00", "recurrence_rule": "daily"}
"el día 1 de cada mes pago el alquiler" → {"module": "calendar", "action": "add", "title": "pago alquiler", "all_day": true, "recurrence_rule": "monthly:1"}
"qué tengo hoy" → {"module": "calendar", "action": "list", "time_window": "today"}
"qué tengo mañana" → {"module": "calendar", "action": "list", "time_window": "tomorrow"}
"agenda de esta semana" → {"module": "calendar", "action": "list", "time_window": "week"}
"qué tengo en marzo" → {"module": "calendar", "action": "list", "time_window": "2026-03"}
"cuándo tengo dentista" → {"module": "calendar", "action": "search", "query": "dentista"}
"próxima reunión" → {"module": "calendar", "action": "search", "query": "reunión"}
"borra el dentista del jueves" → {"module": "calendar", "action": "remove", "title": "dentista", "date": "2026-02-19"}
"elimina el inglés" → {"module": "calendar", "action": "remove", "title": "inglés"}
"cancela la reunión del martes" → {"module": "calendar", "action": "remove", "title": "reunión", "date": "2026-02-17"}
```

**Step 7: Manual test**

Run Sebastian and send test messages to verify parsing:
```
"apunta dentista el viernes a las 17:00"
"qué tengo esta semana"
"cuándo tengo dentista"
```

Check logs for parsed JSON output.

**Step 8: Commit**

```bash
git add core/haiku_parser.py
git commit -m "feat: add calendar module to Haiku parser with date injection"
```

---

## Task 6: Router — add _route_calendar()

**Files:**
- Modify: `sebastian2/core/router.py`
- Modify: `sebastian2/tests/test_router.py`

**Step 1: Write failing test**

Open `sebastian2/tests/test_router.py` and add:

```python
class TestCalendarRouting:
    def test_route_calendar_add(self, router):
        intent = {
            'module': 'calendar',
            'action': 'add',
            'title': 'Dentista',
            'date': '2026-03-10',
            'time': '17:00',
            'all_day': False,
            'recurrence_rule': None,
        }
        result = router.route(intent)
        assert result['success'] is True
        assert 'Dentista' in result['result']

    def test_route_calendar_list_today(self, router):
        intent = {
            'module': 'calendar',
            'action': 'list',
            'time_window': 'today',
        }
        result = router.route(intent)
        assert result['success'] is True

    def test_route_calendar_search(self, router):
        intent = {
            'module': 'calendar',
            'action': 'search',
            'query': 'dentista',
        }
        result = router.route(intent)
        assert result['success'] is True
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_router.py::TestCalendarRouting -v
```

Expected: `KeyError` or route falls through to "unknown module".

**Step 3: Add calendar import to router**

At the top of `sebastian2/core/router.py`, add:

```python
from modules.calendar import CalendarModule
```

**Step 4: Add calendar route in route() method**

In `route()`, after the `elif module == 'notes':` block and before the `elif module == 'unknown':` block, add:

```python
            elif module == 'calendar':
                return self._route_calendar(action, parsed_intent)
```

**Step 5: Implement _route_calendar()**

Add this method to `ModuleRouter` in `router.py` (after `_route_notes`):

```python
    def _route_calendar(self, action: str, intent: dict) -> dict:
        """Route calendar actions to CalendarModule."""
        from datetime import date as date_type

        cal = CalendarModule(self.conn, self.user_id)

        if action == 'add':
            title = intent.get('title', '')
            if not title:
                return {'success': False, 'result': "¿Cuál es el nombre del evento?"}

            # Parse date string
            raw_date = intent.get('date')
            event_date = None
            if raw_date:
                try:
                    from dateutil.parser import parse as parse_dt
                    event_date = parse_dt(raw_date).date()
                except Exception:
                    event_date = None

            result = cal.add_event(
                title=title,
                event_date=event_date,
                event_time=intent.get('time'),
                all_day=intent.get('all_day', False),
                recurrence_rule=intent.get('recurrence_rule'),
                recurrence_end=_parse_date_optional(intent.get('recurrence_end')),
            )
            return {'success': True, 'result': result['message'], 'data': result}

        if action == 'list':
            time_window = intent.get('time_window', 'today')
            events = cal.list_events(time_window)
            return {
                'success': True,
                'result': _format_events_list(events, time_window),
                'data': events
            }

        if action == 'search':
            query = intent.get('query', '')
            events = cal.search_events(query)
            if not events:
                return {'success': True, 'result': f"No encontré ningún evento sobre '{query}'."}
            return {
                'success': True,
                'result': _format_events_list(events, label=f"Eventos sobre '{query}'"),
                'data': events
            }

        if action == 'remove':
            title = intent.get('title', '')
            raw_date = intent.get('date')
            event_date = None
            if raw_date:
                try:
                    from dateutil.parser import parse as parse_dt
                    event_date = parse_dt(raw_date).date()
                except Exception:
                    event_date = None

            result = cal.remove_event(title=title, event_date=event_date)
            return {
                'success': result['status'] in ('removed', 'needs_clarification'),
                'result': result['message'],
                'data': result
            }

        return {'success': False, 'result': f"Acción de calendario desconocida: {action}"}
```

**Step 6: Add helper functions**

Add these module-level helper functions at the bottom of `router.py` (before the class ends, or after it as module-level):

```python
def _parse_date_optional(date_str):
    """Parse an optional date string to a date object."""
    if not date_str:
        return None
    try:
        from dateutil.parser import parse as parse_dt
        return parse_dt(date_str).date()
    except Exception:
        return None


def _format_events_list(events: list, time_window: str = '', label: str = '') -> str:
    """Format a list of events into a readable string."""
    if not events:
        header = label or _time_window_label(time_window)
        return f"📅 {header}\n\nNo tienes eventos."

    header = label or _time_window_label(time_window)
    lines = [f"📅 **{header}**\n"]

    current_date = None
    for e in events:
        # Group by date
        if e['date'] != current_date:
            current_date = e['date']
            day_str = current_date.strftime('%A %-d de %B').capitalize()
            lines.append(f"\n**{day_str}**")

        recurring_icon = " 🔄" if e['recurring'] else ""
        if e['all_day']:
            lines.append(f"• (todo el día) — {e['title']}{recurring_icon}")
        else:
            lines.append(f"• {e['time']} — {e['title']}{recurring_icon}")

    return '\n'.join(lines)


def _time_window_label(time_window: str) -> str:
    """Human-readable label for time window."""
    labels = {
        'today': 'Agenda de hoy',
        'tomorrow': 'Agenda de mañana',
        'week': 'Agenda de esta semana',
        'month': 'Agenda de este mes',
    }
    if time_window in labels:
        return labels[time_window]
    if len(time_window) == 7:
        try:
            from dateutil.parser import parse as parse_dt
            from datetime import date
            d = parse_dt(time_window + '-01').date()
            return f"Agenda de {d.strftime('%B %Y').capitalize()}"
        except Exception:
            pass
    return 'Agenda'
```

**Step 7: Run tests**

```bash
pytest tests/test_router.py::TestCalendarRouting -v
```

Expected: all pass.

**Step 8: Commit**

```bash
git add core/router.py tests/test_router.py
git commit -m "feat: add calendar routing to ModuleRouter"
```

---

## Task 7: Daily Reminder via APScheduler

**Files:**
- Modify: `sebastian2/sebastian_bot.py`
- Modify: `sebastian2/config.yaml` (add `calendar` section — manual step)

**Step 1: Add calendar section to config.yaml**

Manually edit `sebastian2/config.yaml` and add:

```yaml
calendar:
  daily_reminder_time: "08:00"
```

**Step 2: Create scheduler module**

Create `sebastian2/bot/scheduler.py`:

```python
# bot/scheduler.py
"""
APScheduler-based daily reminder for calendar events.
Fires every morning and sends today's agenda to authorized users.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from db.connection import get_connection, close_connection
from modules.calendar import CalendarModule
from loguru import logger


def _send_daily_reminder(bot, user_ids: list):
    """
    Query today's events for each user and send a summary if non-empty.

    Args:
        bot: TeleBot instance
        user_ids: List of Telegram user IDs (strings or ints)
    """
    conn = get_connection()
    try:
        for user_id in user_ids:
            try:
                cal = CalendarModule(conn, str(user_id))
                events = cal.list_events('today')

                if not events:
                    continue  # No events today → no message

                lines = ["📅 **Buenos días! Tu agenda de hoy:**\n"]
                for e in events:
                    recurring_icon = " 🔄" if e['recurring'] else ""
                    if e['all_day']:
                        lines.append(f"• (todo el día) — {e['title']}{recurring_icon}")
                    else:
                        lines.append(f"• {e['time']} — {e['title']}{recurring_icon}")
                lines.append("\n¡Que tengas un buen día!")

                message = '\n'.join(lines)
                bot.send_message(chat_id=int(user_id), text=message)
                logger.info(f"Daily reminder sent to user {user_id} ({len(events)} events)")

            except Exception as e:
                logger.error(f"Error sending daily reminder to {user_id}: {e}")
    finally:
        close_connection()


def start_daily_reminder(bot, config: dict) -> BackgroundScheduler:
    """
    Start the APScheduler background scheduler.

    Reads reminder time from config['calendar']['daily_reminder_time'] (default '08:00').
    Sends morning summary to all authorized_ids in config.

    Args:
        bot: TeleBot instance
        config: Full config dict

    Returns:
        Running BackgroundScheduler instance
    """
    reminder_time = config.get('calendar', {}).get('daily_reminder_time', '08:00')
    hour, minute = map(int, reminder_time.split(':'))

    user_ids = config.get('authorized_ids', [])
    if not user_ids:
        logger.warning("No authorized_ids in config — daily reminder will have no recipients")

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _send_daily_reminder,
        trigger='cron',
        hour=hour,
        minute=minute,
        args=[bot, user_ids],
        id='daily_calendar_reminder',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Daily calendar reminder scheduled at {reminder_time} for {len(user_ids)} user(s)")
    return scheduler
```

**Step 3: Integrate scheduler into sebastian_bot.py**

In `sebastian_bot.py`, add import at top:

```python
from bot.scheduler import start_daily_reminder
```

In `main()`, after `setup_handlers(bot, config)`, add:

```python
        # Start daily calendar reminder
        scheduler = start_daily_reminder(bot, config)
        logger.info("Daily calendar reminder scheduler started")
```

Also update the shutdown logic — after the `bot.infinity_polling(...)` line and inside the `except KeyboardInterrupt` block, add:

```python
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
        if 'scheduler' in locals():
            scheduler.shutdown()
```

**Step 4: Manual test**

Temporarily set a reminder 2 minutes in the future in config, restart bot, verify you receive the message. Then restore the proper time.

**Step 5: Run existing tests to check nothing broke**

```bash
cd sebastian2
source .venv/bin/activate
pytest tests/ -v --ignore=tests/test_haiku_parser.py -x
```

(Skip haiku_parser tests as they hit the API.)

Expected: all existing tests pass.

**Step 6: Commit**

```bash
git add bot/scheduler.py sebastian_bot.py
git commit -m "feat: add APScheduler daily calendar reminder"
```

---

## Task 8: End-to-End Manual Verification

**Step 1: Start the bot**

```bash
cd sebastian2
source .venv/bin/activate
python sebastian_bot.py
```

**Step 2: Test each flow via Telegram**

Send these messages and verify responses:

```
"apunta dentista el próximo lunes a las 5 de la tarde"
→ "Evento añadido: dentista"

"qué tengo esta semana"
→ Lista con dentista en el día correcto

"cada miércoles tengo pilates a las 19:00"
→ "Evento añadido: pilates"

"agenda de esta semana"
→ Pilates aparece si hay un miércoles en la semana

"cuándo tengo dentista"
→ Fecha del dentista

"borra el dentista"
→ "Evento eliminado: dentista"

"el 5 de mayo es el cumpleaños de Juan"
→ "Evento añadido: cumpleaños juan" (all-day)

"qué tengo en mayo"
→ Cumpleaños juan el día 5
```

**Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: calendar end-to-end adjustments after manual testing"
```

---

## Summary

| Task | Key deliverable |
|------|----------------|
| 1 | `events` table + APScheduler/dateutil deps |
| 2 | `CalendarModule.add_event()` + `remove_event()` |
| 3 | `CalendarModule.list_events()` with rrule expansion |
| 4 | `CalendarModule.search_events()` |
| 5 | Haiku parser: calendar module + date injection |
| 6 | Router: `_route_calendar()` + formatting helpers |
| 7 | APScheduler daily reminder in `bot/scheduler.py` |
| 8 | End-to-end manual validation |
