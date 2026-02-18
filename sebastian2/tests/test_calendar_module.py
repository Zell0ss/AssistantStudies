# tests/test_calendar_module.py
import pytest
from datetime import date, datetime
from modules.calendar import CalendarModule
from db.connection import get_connection, close_connection


@pytest.fixture
def db_conn():
    conn = get_connection()
    yield conn
    close_connection()


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
    cursor = db_conn.cursor()
    cursor.execute("DELETE FROM events WHERE user_id = %s", (user_id,))
    db_conn.commit()


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
        assert result.get('type') == 'recurring'


class TestListEvents:
    def test_list_today(self, cal):
        today = date.today()
        cal.add_event(title="Reunión", event_date=today, event_time="10:00")
        events = cal.list_events('today')
        assert any(e['title'] == 'Reunión' for e in events)

    def test_list_today_excludes_other_days(self, cal):
        from datetime import timedelta
        tomorrow = date.today() + timedelta(days=1)
        cal.add_event(title="EventoMañana", event_date=tomorrow, event_time="10:00")
        events = cal.list_events('today')
        assert not any(e['title'] == 'EventoMañana' for e in events)

    def test_list_week_includes_7_days(self, cal):
        from datetime import timedelta
        today = date.today()
        cal.add_event(title="FinDeSemana", event_date=today + timedelta(days=6), event_time="12:00")
        events = cal.list_events('week')
        assert any(e['title'] == 'FinDeSemana' for e in events)

    def test_recurring_weekly_appears_in_range(self, cal):
        from datetime import timedelta
        today = date.today()
        # Find next Monday from today (or today if it's Monday)
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)
        cal.add_event(
            title="InglésRecurrente",
            event_date=next_monday,
            event_time="19:00",
            recurrence_rule="weekly:MON"
        )
        # Query the week that contains next_monday
        # Use 'week' if next_monday is within 6 days, otherwise use YYYY-MM format
        if days_until_monday <= 6:
            events = cal.list_events('week')
        else:
            events = cal.list_events(next_monday.strftime('%Y-%m'))
        titles = [e['title'] for e in events]
        assert 'InglésRecurrente' in titles

    def test_recurring_marks_recurrent_flag(self, cal):
        from datetime import timedelta
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)
        cal.add_event(
            title="YogaRecurrente",
            event_date=next_monday,
            event_time="08:00",
            recurrence_rule="weekly:MON"
        )
        if days_until_monday <= 6:
            events = cal.list_events('week')
        else:
            events = cal.list_events(next_monday.strftime('%Y-%m'))
        yoga_events = [e for e in events if e['title'] == 'YogaRecurrente']
        assert len(yoga_events) >= 1
        assert yoga_events[0]['recurring'] is True

    def test_recurring_with_end_date_excludes_after_end(self, cal):
        from datetime import timedelta
        today = date.today()
        yesterday = today - timedelta(days=1)
        cal.add_event(
            title="EventoExpirado",
            event_date=today - timedelta(days=30),
            event_time="10:00",
            recurrence_rule="daily",
            recurrence_end=yesterday
        )
        events = cal.list_events('today')
        assert not any(e['title'] == 'EventoExpirado' for e in events)

    def test_list_month_format(self, cal):
        cal.add_event(title="EventoMarzo", event_date=date(2027, 3, 15), event_time="10:00")
        events = cal.list_events('2027-03')
        assert any(e['title'] == 'EventoMarzo' for e in events)

    def test_events_sorted_by_time(self, cal):
        today = date.today()
        cal.add_event(title="Tarde", event_date=today, event_time="18:00")
        cal.add_event(title="Mañana", event_date=today, event_time="09:00")
        events = cal.list_events('today')
        titles = [e['title'] for e in events]
        assert titles.index('Mañana') < titles.index('Tarde')


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

    def test_search_partial_match(self, cal):
        cal.add_event(title="Reunión de equipo", event_date=date(2026, 5, 10), event_time="10:00")
        results = cal.search_events("equipo")
        assert len(results) == 1

    def test_search_no_results(self, cal):
        results = cal.search_events("cita_inexistente_xyz")
        assert results == []

    def test_search_returns_soonest_first(self, cal):
        from datetime import timedelta
        today = date.today()
        cal.add_event(title="Revisión", event_date=today + timedelta(days=30), event_time="09:00")
        cal.add_event(title="Revisión", event_date=today + timedelta(days=10), event_time="09:00")
        results = cal.search_events("Revisión")
        assert results[0]['date'] == today + timedelta(days=10)

    def test_search_recurring_shows_next_occurrence(self, cal):
        from datetime import timedelta
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)
        cal.add_event(
            title="InglésSearch",
            event_date=next_monday,
            event_time="19:00",
            recurrence_rule="weekly:MON"
        )
        results = cal.search_events("InglésSearch")
        assert len(results) == 1
        assert results[0]['recurring'] is True
        assert results[0]['date'] >= today


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
        upcoming = cal.find_upcoming_events(limit=5)
        assert isinstance(upcoming, list)

    def test_ticket_added_at_is_set(self, cal):
        result = cal.add_event(title="FechaTest", event_date=date(2026, 6, 1), event_time="19:00")
        cal.add_ticket(result['event_id'], {'type': 'QR_CODE', 'value': 'test'})
        notes = cal.get_event_notes(result['event_id'])
        assert 'added_at' in notes['tickets'][0]
