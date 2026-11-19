# modules/calendar.py
"""
Calendar module - personal event management with recurrence support.
"""
import json
import re
from datetime import date, datetime, time
from typing import Optional, List, Dict, Any
from modules.base import BaseModule
from modules.compromisos import CompromisosModule
from logcentral_client import get_logger

logger = get_logger("sebastian")
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU
import calendar as cal_lib
import unicodedata

# D61: palabras que no sirven para buscar un evento («cena de Navidad de BNP» → cena, navidad, bnp).
_PALABRAS_VACIAS = frozenset(
    "de del la las el los en a al y con para por un una mi mis".split()
)


def _normalizar_titulo(texto: str) -> str:
    """Minúsculas, sin acentos y solo letras y dígitos separados por un espacio (D61)."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", texto or "") if not unicodedata.combining(c))
    return " ".join(re.split(r"[^a-z0-9]+", sin_acentos.lower())).strip()


def _palabras_de_busqueda(consulta: str) -> List[str]:
    """Las palabras útiles de una consulta: sin las vacías ni las de menos de 2 caracteres (D61)."""
    return [p for p in _normalizar_titulo(consulta).split() if len(p) >= 2 and p not in _PALABRAS_VACIAS]


class CalendarModule(BaseModule):
    """
    Manages personal calendar events.

    Supports single events (timed or all-day) and recurring events.

    recurrence_rule format:
        None             → single event
        'daily'          → every day
        'weekly:MON'     → every Monday
        'weekly:MON,WED' → multiple days
        'monthly:15'     → 15th of each month
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
            Dict with status ('added') and message; o `status: 'exists'` con `event_id`, `time` y `message` si el usuario
            ya tiene un evento ese mismo día con ese mismo título (H3b R3, sin distinguir mayúsculas).
        """
        start_datetime = None
        if event_date and event_time and not all_day:
            h, m = map(int, event_time.split(':'))
            start_datetime = datetime.combine(event_date, time(h, m))

        # Fase 3 H3b (R3): crear no duplica. Solo mismo día y mismo título: nada difuso (lo difuso, a la fase 4 si el uso lo pide).
        if event_date:
            existente = self.execute_query(
                """SELECT id, start_datetime FROM events
                   WHERE user_id = %s AND LOWER(title) = LOWER(%s)
                   AND (DATE(start_datetime) = %s OR event_date = %s)
                   ORDER BY id LIMIT 1""",
                (self.user_id, title, event_date, event_date)
            ).fetchone()
            if existente:
                hora = existente['start_datetime'].strftime('%H:%M') if existente['start_datetime'] else None
                logger.info(f"Event '{title}' already exists for user {self.user_id}: id={existente['id']}")
                return {
                    'status': 'exists',
                    'message': f"Ya existe el evento '{title}' ese día: usa ese evento, no lo crees de nuevo",
                    'event_id': existente['id'],
                    'time': hora,
                }

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

        If the event is recurring and no date is given, returns
        'needs_clarification' so the caller can ask the user.

        Returns:
            Dict with status: 'removed' | 'not_found' | 'needs_clarification'
        """
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
        # D50: los compromisos atados a estos eventos se cancelan en la misma transacción que el borrado.
        cancelados = CompromisosModule(self.db, self.user_id).cancelar_por_eventos_borrados(ids)
        self.execute_query(
            f"DELETE FROM events WHERE id IN ({placeholders})",
            tuple(ids)
        )
        self.commit()

        logger.info(f"Removed {len(ids)} event(s) named '{title}' for user {self.user_id}")
        resultado = {'status': 'removed', 'message': f"Evento eliminado: {title}"}
        if cancelados:
            # H1-revision R1: Alfred ve el campo y le cuenta al usuario que su preparación ha desaparecido.
            resultado['compromisos_cancelados'] = cancelados
        return resultado

    def remove_event_by_id(self, event_id: int) -> bool:
        """Remove a specific event by ID."""
        # D50: sus compromisos pendientes se cancelan antes (la FK no lleva ON DELETE), en la misma transacción.
        CompromisosModule(self.db, self.user_id).cancelar_por_eventos_borrados([event_id])
        cursor = self.execute_query(
            "DELETE FROM events WHERE id = %s AND user_id = %s",
            (event_id, self.user_id)
        )
        self.commit()
        return cursor.rowcount > 0

    def update_event(
        self,
        title: Optional[str] = None,
        event_date: Optional[date] = None,
        new_title: Optional[str] = None,
        new_date: Optional[date] = None,
        new_time: Optional[str] = None,
        new_all_day: Optional[bool] = None,
        event_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update fields of an existing event (or all occurrences of a recurring event).

        Args:
            title: Existing event title to find (case-insensitive)
            event_date: Optional date to disambiguate which single event
            new_title: Rename the event
            new_date: Change the event date
            new_time: Change the event time as "HH:MM"
            new_all_day: Change the all-day flag
            event_id: (H3b R2) el evento por su id; si viene, manda sobre `title` y `event_date`. Solo del propio usuario.

        Returns:
            Dict with status: 'updated' | 'not_found'
        """
        if event_id is not None:
            cursor = self.execute_query(
                """SELECT id, title, event_date, start_datetime, all_day, recurrence_rule
                   FROM events WHERE user_id = %s AND id = %s""",
                (self.user_id, event_id)
            )
        elif not title:
            cursor = None
        elif event_date:
            cursor = self.execute_query(
                """SELECT id, title, event_date, start_datetime, all_day, recurrence_rule
                   FROM events
                   WHERE user_id = %s AND LOWER(title) = LOWER(%s)
                   AND (DATE(start_datetime) = %s OR event_date = %s)""",
                (self.user_id, title, event_date, event_date)
            )
        else:
            cursor = self.execute_query(
                """SELECT id, title, event_date, start_datetime, all_day, recurrence_rule
                   FROM events WHERE user_id = %s AND LOWER(title) = LOWER(%s)""",
                (self.user_id, title)
            )

        rows = cursor.fetchall() if cursor is not None else []
        if not rows:
            # H3b R2: el modelo no debe responder a un not_found creando el evento otra vez (E10, ejecución 3).
            nombre = title if event_id is None else f"con id {event_id}"
            return {'status': 'not_found',
                    'message': f"No lo he encontrado ({nombre}): pregunta al usuario, no lo crees de nuevo"}
        title = title or rows[0]['title']

        for row in rows:
            set_parts = ['updated_at = CURRENT_TIMESTAMP']
            params = []

            if new_title:
                set_parts.append('title = %s')
                params.append(new_title)

            is_all_day = new_all_day if new_all_day is not None else bool(row['all_day'])

            if new_all_day is not None:
                set_parts.append('all_day = %s')
                params.append(new_all_day)

            if new_date or new_time:
                if is_all_day:
                    # All-day: just update event_date, clear start_datetime
                    target_date = new_date or (
                        row['start_datetime'].date() if row['start_datetime'] else row['event_date']
                    )
                    set_parts.append('event_date = %s')
                    params.append(target_date)
                    set_parts.append('start_datetime = NULL')
                else:
                    # Timed event: rebuild start_datetime
                    if new_date:
                        base_date = new_date
                    elif row['start_datetime']:
                        base_date = row['start_datetime'].date()
                    elif row['event_date']:
                        base_date = row['event_date']
                    else:
                        base_date = date.today()

                    if new_time:
                        h, m = map(int, new_time.split(':'))
                        new_event_time = time(h, m)
                    elif row['start_datetime']:
                        new_event_time = row['start_datetime'].time()
                    else:
                        new_event_time = time(0, 0)

                    set_parts.append('start_datetime = %s')
                    params.append(datetime.combine(base_date, new_event_time))
                    set_parts.append('event_date = NULL')

            params.append(row['id'])
            self.execute_query(
                f"UPDATE events SET {', '.join(set_parts)} WHERE id = %s",
                tuple(params)
            )

        self.commit()

        change_desc = []
        if new_title:
            change_desc.append(f"nombre → '{new_title}'")
        if new_time:
            change_desc.append(f"hora → {new_time}")
        if new_date:
            change_desc.append(f"fecha → {new_date}")
        if new_all_day is not None:
            change_desc.append("todo el día" if new_all_day else "con hora")

        display_name = new_title or title
        changes_str = ', '.join(change_desc) if change_desc else 'sin cambios'
        logger.info(f"Updated event '{title}' ({changes_str}) for user {self.user_id}")
        return {
            'status': 'updated',
            'message': f"✅ Actualizado '{display_name}': {changes_str}",
        }

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
            days_str = rule_str[7:]
            days = [self._WEEKDAY_MAP[d.strip()] for d in days_str.split(',')]
            return rrule(WEEKLY, byweekday=days, dtstart=start_dt, until=until)

        if rule_str.startswith('monthly:'):
            spec = rule_str[8:]
            if spec.isdigit():
                return rrule(MONTHLY, bymonthday=int(spec), dtstart=start_dt, until=until)
            ordinal_map = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'last': -1}
            parts = spec.split('-')
            ordinal = ordinal_map[parts[0]]
            weekday = self._WEEKDAY_MAP[parts[1]](ordinal)
            return rrule(MONTHLY, byweekday=weekday, dtstart=start_dt, until=until)

        return None

    VENTANAS_VALIDAS = ("today, tomorrow, week, month (este mes, desde hoy), next_month (el mes siguiente entero), "
                        "weekend (el próximo fin de semana) o YYYY-MM (un mes concreto, entero)")

    def _time_window_to_range(self, time_window: str, hoy: Optional[date] = None):
        """Convert time_window string to (start_date, end_date) tuple. `hoy` inyecta el día (por defecto, el del sistema).

        Valores: 'today', 'tomorrow', 'week' (7 días desde hoy), 'month' (lo que queda del mes en curso, desde hoy),
        'next_month' (el mes siguiente, entero), 'weekend' y 'YYYY-MM' (ese mes, entero).

        'weekend' (H5, R15) es el próximo sábado y domingo. Si hoy es sábado, hoy y mañana; si es domingo, solo hoy.

        Un valor desconocido lanza `ValueError` con los valores válidos (H5, R16): antes caía en «hoy» sin avisar.
        """
        from datetime import timedelta
        today = hoy or date.today()

        if time_window == 'today':
            return today, today
        if time_window == 'tomorrow':
            return today + timedelta(days=1), today + timedelta(days=1)
        if time_window == 'week':
            return today, today + timedelta(days=6)
        if time_window == 'month':
            last_day = cal_lib.monthrange(today.year, today.month)[1]
            return today, date(today.year, today.month, last_day)
        if time_window == 'next_month':
            year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
            return date(year, month, 1), date(year, month, cal_lib.monthrange(year, month)[1])
        if time_window == 'weekend':
            weekday = today.weekday()                       # lunes 0 … sábado 5, domingo 6
            if weekday == 6:
                return today, today
            sabado = today if weekday == 5 else today + timedelta(days=5 - weekday)
            return sabado, sabado + timedelta(days=1)
        # YYYY-MM: cuatro cifras, guion y un mes de 01 a 12
        if isinstance(time_window, str) and re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', time_window):
            year, month = map(int, time_window.split('-'))
            return date(year, month, 1), date(year, month, cal_lib.monthrange(year, month)[1])

        raise ValueError(f"time_window {time_window!r} no es válido: usa {self.VENTANAS_VALIDAS}")

    def _row_to_event_dict(self, row: dict, recurring: bool) -> Dict[str, Any]:
        """Convert a DB row to a clean event dict."""
        if row['start_datetime']:
            event_date = row['start_datetime'].date()
            event_time = row['start_datetime'].strftime('%H:%M')
        else:
            event_date = row['event_date']
            event_time = None

        notes_raw = row.get('notes')
        if isinstance(notes_raw, str):
            notes_raw = json.loads(notes_raw)
        note = notes_raw.get('note') if isinstance(notes_raw, dict) else None

        return {
            'event_id': row['id'],
            'title': row['title'],
            'date': event_date,
            'time': event_time,
            'all_day': bool(row['all_day']),
            'recurring': recurring,
            'note': note,
        }

    def list_events(self, time_window: str, hoy: Optional[date] = None) -> List[Dict[str, Any]]:
        """
        List events in the given time window, expanding recurring events.

        Args:
            time_window: 'today' | 'tomorrow' | 'week' | 'month' | 'next_month' | 'weekend' | 'YYYY-MM'
                (cualquier otro valor lanza ValueError, ver `_time_window_to_range`)

        Returns:
            List of event dicts sorted by date and time, each with:
            {event_id, title, date, time, all_day, recurring}
        """
        start_date, end_date = self._time_window_to_range(time_window, hoy)
        start_dt = datetime.combine(start_date, time(0, 0))
        end_dt = datetime.combine(end_date, time(23, 59, 59))

        query = """
            SELECT id, title, event_date, start_datetime, end_datetime,
                   all_day, recurrence_rule, recurrence_end, notes
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
                results.append(self._row_to_event_dict(row, recurring=False))
                continue

            # Recurring: expand within range
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

        results.sort(key=lambda e: (e['date'], e['time'] or '00:00'))
        return results

    def add_ticket(self, event_id: int, ticket: dict) -> dict:
        """Append a decoded ticket to an event's notes.tickets JSON array."""
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
        """Retrieve the notes JSON for an event. Returns None if no notes."""
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

    def clear_tickets(self, event_id: int) -> Dict[str, Any]:
        """Remove all tickets from an event's notes."""
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

        count = len(notes.pop('tickets', []))
        self.execute_query(
            "UPDATE events SET notes = %s WHERE id = %s AND user_id = %s",
            (json.dumps(notes, ensure_ascii=False), event_id, self.user_id)
        )
        self.commit()
        logger.info(f"Cleared {count} ticket(s) from event {event_id}")
        return {'status': 'cleared', 'count': count}

    def add_note(
        self,
        event_id: Optional[int] = None,
        note_text: str = "",
        title: Optional[str] = None,
        event_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Store a free-text note on an event's notes JSON (key 'note').

        Args:
            event_id: Event ID. Si viene, manda sobre `title` y `event_date`.
            note_text: Text to store
            title: (H3c R8) sin `event_id`, el evento se busca por título (sin mayúsculas) y, si viene, `event_date`.
            event_date: Día del evento, para desambiguar.

        Returns:
            Dict with status: 'noted' (con `event_id`) | 'not_found' | 'ambiguous' (con `candidates`, sin escribir).
        """
        if event_id is not None:
            cursor = self.execute_query(
                "SELECT id, notes FROM events WHERE id = %s AND user_id = %s",
                (event_id, self.user_id)
            )
            row = cursor.fetchone()
            rotulo = f"con id {event_id}"
        elif title:
            consulta = ("SELECT id, title, event_date, start_datetime, notes FROM events "
                        "WHERE user_id = %s AND LOWER(title) = LOWER(%s)")
            params = [self.user_id, title]
            if event_date:
                consulta += " AND (DATE(start_datetime) = %s OR event_date = %s)"
                params += [event_date, event_date]
            filas = self.execute_query(consulta + " ORDER BY id", tuple(params)).fetchall()
            if len(filas) > 1:
                # Sin escribir: el modelo tiene que preguntar cuál (o repetir con `date`/`event_id`).
                return {
                    'status': 'ambiguous',
                    'message': f"Hay {len(filas)} eventos '{title}': pregunta al usuario cuál, o repite con su día o su event_id",
                    'candidates': [{
                        'event_id': f['id'], 'title': f['title'],
                        'date': (f['start_datetime'].date() if f['start_datetime'] else f['event_date']),
                        'time': (f['start_datetime'].strftime('%H:%M') if f['start_datetime'] else None),
                    } for f in filas],
                }
            row = filas[0] if filas else None
            rotulo = f"'{title}'"
        else:
            row, rotulo = None, "sin id ni título"
        if not row:
            # Mismo texto que en `update_event` (R2): el modelo no debe responder a un not_found creando el evento.
            return {'status': 'not_found',
                    'message': f"No lo he encontrado ({rotulo}): pregunta al usuario, no lo crees de nuevo"}
        event_id = row['id']

        notes = row['notes'] or {}
        if isinstance(notes, str):
            notes = json.loads(notes)

        notes['note'] = note_text
        self.execute_query(
            "UPDATE events SET notes = %s WHERE id = %s AND user_id = %s",
            (json.dumps(notes, ensure_ascii=False), event_id, self.user_id)
        )
        self.commit()
        logger.info(f"Added note to event {event_id}: {note_text[:60]}")
        return {'status': 'noted', 'note': note_text, 'event_id': event_id}

    def find_by_datetime(self, event_date: date, event_time: str) -> Optional[Dict[str, Any]]:
        """
        Find an event by exact date and time.

        Checks single events first, then recurring events that fall on event_date.

        Args:
            event_date: Date to search
            event_time: Time as "HH:MM" string

        Returns:
            Event dict (with event_id, title) or None if not found
        """
        from datetime import time as time_type
        time_obj = datetime.strptime(event_time, '%H:%M').time()

        cursor = self.execute_query(
            """
            SELECT id, title, recurrence_rule, recurrence_end, start_datetime, event_date, all_day
            FROM events
            WHERE user_id = %s AND TIME(start_datetime) = %s
            """,
            (self.user_id, time_obj)
        )
        rows = cursor.fetchall()

        for row in rows:
            if not row['recurrence_rule']:
                # Single event: check date matches
                if row['start_datetime'] and row['start_datetime'].date() == event_date:
                    return {'event_id': row['id'], 'title': row['title']}
            else:
                # Recurring: check if it occurs on event_date
                base_dt = row['start_datetime']
                if not base_dt:
                    continue
                rule = self._rule_to_rrule(row['recurrence_rule'], base_dt, row['recurrence_end'])
                if not rule:
                    continue
                start = datetime.combine(event_date, time_type(0, 0))
                end = datetime.combine(event_date, time_type(23, 59, 59))
                if rule.between(start, end, inc=True):
                    return {'event_id': row['id'], 'title': row['title']}

        return None

    def find_upcoming_events(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return next N upcoming events (next 30 days). Used for ticket association UI."""
        events = self.list_events('month')
        return events[:limit]

    def _eventos_de_filas(self, rows) -> List[Dict[str, Any]]:
        """Filas de `events` → dicts de evento. Un recurrente da su próxima ocurrencia desde hoy (y ninguno si ya no
        tiene). Sin ordenar."""
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

        return results

    def search_events(self, query: str) -> List[Dict[str, Any]]:
        """
        Search events by the words of their title (D61).

        Query and titles are normalised (lowercase, no accents, split on anything that is not a letter or digit);
        stop words and 1-character words are dropped from the query.
          - Level 1: events whose title contains ALL the words. If there are any, only those are returned.
          - Level 2 (only if level 1 is empty): events containing SOME word, most matches first, then soonest.
            Each carries `coincidencia: "parcial"` (level 1 events carry no such key).
        If no word is left (empty query, or only stop words) it falls back to the old substring match
        (`search_events("")` returns every event).

        For recurring events, returns the next upcoming occurrence.
        Results sorted soonest first.

        Args:
            query: Search string

        Returns:
            List of event dicts
        """
        palabras = _palabras_de_busqueda(query)
        # D42: solo el tamaño de la consulta va al log, nunca el texto.
        logger.info(f"Búsqueda de eventos | user={self.user_id} | query_chars={len(query or '')} palabras={len(palabras)}")

        if not palabras:
            cursor = self.execute_query(
                """
                SELECT id, title, event_date, start_datetime, end_datetime,
                       all_day, recurrence_rule, recurrence_end, notes
                FROM events
                WHERE user_id = %s AND LOWER(title) LIKE LOWER(%s)
                ORDER BY start_datetime, event_date
                """,
                (self.user_id, f'%{query}%')
            )
            results = self._eventos_de_filas(cursor.fetchall())
            results.sort(key=lambda e: (e['date'], e['time'] or '00:00'))
            return results

        # Se filtra en Python: son los eventos de un solo usuario, pocos.
        cursor = self.execute_query(
            """
            SELECT id, title, event_date, start_datetime, end_datetime,
                   all_day, recurrence_rule, recurrence_end, notes
            FROM events
            WHERE user_id = %s
            ORDER BY start_datetime, event_date
            """,
            (self.user_id,)
        )
        filas = []
        for row in cursor.fetchall():
            titulo = _normalizar_titulo(row['title'])
            filas.append((row, sum(1 for p in palabras if p in titulo)))

        completas = self._eventos_de_filas([row for row, n in filas if n == len(palabras)])
        if completas:
            completas.sort(key=lambda e: (e['date'], e['time'] or '00:00'))
            return completas

        # Segundo nivel: el evento se vincula a su fila por id para saber cuántas palabras casó.
        aciertos = {row['id']: n for row, n in filas if n > 0}
        parciales = self._eventos_de_filas([row for row, n in filas if n > 0])
        for e in parciales:
            e['coincidencia'] = "parcial"
        parciales.sort(key=lambda e: (-aciertos[e['event_id']], e['date'], e['time'] or '00:00'))
        return parciales
