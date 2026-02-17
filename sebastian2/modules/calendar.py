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
