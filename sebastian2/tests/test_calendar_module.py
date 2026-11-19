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


def _cuantos(cal, titulo):
    cur = cal.db.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM events WHERE user_id = %s AND LOWER(title) = LOWER(%s)", (cal.user_id, titulo))
    return cur.fetchone()["n"]


class TestAddEventNoDuplica:
    """Fase 3 H3b (R3): el mismo día y el mismo título (sin distinguir mayúsculas) no se inserta dos veces."""

    def test_add_event_mismo_dia_y_titulo_devuelve_existente(self, cal):
        primero = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")
        segundo = cal.add_event(title="endoscopia", event_date=date(2027, 1, 28), event_time="10:00")
        assert primero['status'] == 'added'
        assert segundo['status'] == 'exists'
        assert segundo['event_id'] == primero['event_id']
        assert segundo['time'] == '09:30'                       # la hora del que ya existía, no la de la segunda petición
        assert _cuantos(cal, "Endoscopia") == 1

    def test_add_event_otro_dia_o_otro_titulo_si_inserta(self, cal):
        base = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")
        otro_dia = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 29), event_time="09:30")
        otro_titulo = cal.add_event(title="Endoscopia de control", event_date=date(2027, 1, 28), event_time="09:30")
        assert {otro_dia['status'], otro_titulo['status']} == {'added'}
        assert len({base['event_id'], otro_dia['event_id'], otro_titulo['event_id']}) == 3

    def test_add_event_de_otro_usuario_no_cuenta_como_existente(self, cal, db_conn):
        cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")
        otro = CalendarModule(db_conn, "test_user_calendar_otro")
        try:
            assert otro.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")['status'] == 'added'
        finally:
            db_conn.cursor().execute("DELETE FROM events WHERE user_id = %s", ("test_user_calendar_otro",))
            db_conn.commit()

    def test_add_event_de_todo_el_dia_tambien_se_reconoce(self, cal):
        a = cal.add_event(title="Cumpleaños Rebe", event_date=date(2026, 3, 15), all_day=True)
        b = cal.add_event(title="cumpleaños rebe", event_date=date(2026, 3, 15), all_day=True)
        assert b['status'] == 'exists' and b['event_id'] == a['event_id'] and b['time'] is None


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


class TestUpdateEvent:
    def test_update_time_of_timed_event(self, cal):
        """Change time of a single timed event."""
        cal.add_event(title="Dentista", event_date=date(2026, 3, 10), event_time="17:00")
        result = cal.update_event(title="Dentista", new_time="19:00")
        assert result['status'] == 'updated'
        # Verify time changed
        events = cal.search_events("Dentista")
        assert events[0]['time'] == '19:00'

    def test_update_time_of_recurring_event(self, cal):
        """Change time of a recurring event — changes all future occurrences."""
        cal.add_event(
            title="Pilates",
            event_date=date(2026, 2, 17),
            event_time="18:00",
            recurrence_rule="weekly:TUE"
        )
        result = cal.update_event(title="Pilates", new_time="19:00")
        assert result['status'] == 'updated'
        events = cal.search_events("Pilates")
        assert events[0]['time'] == '19:00'

    def test_update_title(self, cal):
        """Rename an event."""
        cal.add_event(title="Dentista", event_date=date(2026, 3, 10), event_time="17:00")
        result = cal.update_event(title="Dentista", new_title="Revisión dental")
        assert result['status'] == 'updated'
        events = cal.search_events("Revisión dental")
        assert len(events) > 0
        # Old title should be gone
        old_events = cal.search_events("Dentista")
        assert len(old_events) == 0

    def test_update_date_of_single_event(self, cal):
        """Move a single event to a new date."""
        cal.add_event(title="Reunión", event_date=date(2026, 3, 10), event_time="10:00")
        result = cal.update_event(title="Reunión", new_date=date(2026, 3, 15))
        assert result['status'] == 'updated'
        events = cal.search_events("Reunión")
        assert events[0]['date'] == date(2026, 3, 15)

    def test_update_nonexistent_event_returns_not_found(self, cal):
        """Updating a non-existent event returns not_found."""
        result = cal.update_event(title="NoExiste", new_time="10:00")
        assert result['status'] == 'not_found'

    def test_update_event_por_id(self, cal):
        """Fase 3 H3b (R2): con `event_id` no hace falta acertar el título, y el id manda si vienen los dos."""
        cita = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")["event_id"]
        otra = cal.add_event(title="Dentista", event_date=date(2027, 1, 28), event_time="12:00")["event_id"]
        result = cal.update_event(title="Dentista", event_id=cita, new_date=date(2027, 1, 29))
        assert result['status'] == 'updated'
        fechas = {e['title']: e['date'] for e in cal.search_events("") if e['title'] in ("Endoscopia", "Dentista")}
        assert fechas == {"Endoscopia": date(2027, 1, 29), "Dentista": date(2027, 1, 28)}
        assert otra != cita

    def test_update_event_por_id_sin_titulo(self, cal):
        cita = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")["event_id"]
        assert cal.update_event(event_id=cita, new_time="10:15")['status'] == 'updated'
        assert cal.search_events("Endoscopia")[0]['time'] == '10:15'

    def test_update_event_por_id_de_otro_usuario_no_toca_nada(self, cal, db_conn):
        cita = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")["event_id"]
        intruso = CalendarModule(db_conn, "test_user_calendar_otro")
        result = intruso.update_event(event_id=cita, new_date=date(2027, 2, 2), new_title="Otra cosa")
        assert result['status'] == 'not_found'
        ev = cal.search_events("Endoscopia")
        assert len(ev) == 1 and ev[0]['date'] == date(2027, 1, 28) and ev[0]['time'] == '09:30'

    def test_update_not_found_dice_que_no_lo_cree_de_nuevo(self, cal):
        for kwargs in ({"title": "NoExiste"}, {"event_id": 999999999}, {}):
            result = cal.update_event(new_time="10:00", **kwargs)
            assert result['status'] == 'not_found'
            assert "pregunta al usuario" in result['message'] and "no lo crees de nuevo" in result['message']

    def test_update_time_and_title_together(self, cal):
        """Update both time and title in one call."""
        cal.add_event(title="Inglés", event_date=date(2026, 3, 10), event_time="18:00")
        result = cal.update_event(title="Inglés", new_time="19:00", new_title="Clase de inglés")
        assert result['status'] == 'updated'
        events = cal.search_events("Clase de inglés")
        assert events[0]['time'] == '19:00'


class TestNoteVisibleInSearch:
    def test_search_events_includes_note_field(self, cal):
        """search_events() result includes 'note' from the notes JSON when present."""
        result = cal.add_event(title="Pilates", event_date=date(2026, 3, 10), event_time="19:00")
        cal.add_note(result['event_id'], "llevar dinero")
        events = cal.search_events("Pilates")
        assert len(events) == 1
        assert events[0].get('note') == 'llevar dinero'

    def test_search_events_note_is_none_when_not_set(self, cal):
        """search_events() result has note=None when event has no note."""
        cal.add_event(title="Yoga", event_date=date(2026, 3, 10), event_time="08:00")
        events = cal.search_events("Yoga")
        assert events[0].get('note') is None

    def test_list_events_includes_note(self, cal):
        """list_events() result includes 'note' when present."""
        from datetime import timedelta
        tomorrow = date.today() + timedelta(days=1)
        result = cal.add_event(title="Médico", event_date=tomorrow, event_time="10:00")
        cal.add_note(result['event_id'], "llevar informe")
        events = cal.list_events('tomorrow')
        médico = next((e for e in events if e['title'] == 'Médico'), None)
        assert médico is not None
        assert médico.get('note') == 'llevar informe'


class TestAddNote:
    def test_add_note_to_event(self, cal):
        """add_note() stores note text in notes JSON."""
        result = cal.add_event(title="Pilates", event_date=date(2026, 3, 10), event_time="19:00")
        event_id = result['event_id']
        result = cal.add_note(event_id, "llevar dinero")
        assert result['status'] == 'noted'
        notes = cal.get_event_notes(event_id)
        assert notes['note'] == 'llevar dinero'

    def test_add_note_preserves_existing_tickets(self, cal):
        """add_note() does not wipe tickets already in the notes JSON."""
        import json
        result = cal.add_event(title="Concierto", event_date=date(2026, 3, 20), event_time="21:00")
        event_id = result['event_id']
        cal.add_ticket(event_id, {'type': 'QR_CODE', 'value': 'ABC123'})
        cal.add_note(event_id, "llevar carnet")
        notes = cal.get_event_notes(event_id)
        assert notes['note'] == 'llevar carnet'
        assert len(notes['tickets']) == 1

    def test_add_note_overwrites_previous_note(self, cal):
        """A second add_note() replaces the first."""
        result = cal.add_event(title="Yoga", event_date=date(2026, 3, 10), event_time="08:00")
        event_id = result['event_id']
        cal.add_note(event_id, "primera nota")
        cal.add_note(event_id, "nota actualizada")
        notes = cal.get_event_notes(event_id)
        assert notes['note'] == 'nota actualizada'

    def test_add_note_event_not_found(self, cal):
        """add_note() on missing event returns not_found."""
        result = cal.add_note(99999999, "llevar algo")
        assert result['status'] == 'not_found'


class TestAddNotePorTitulo:
    """Fase 3 H3c (R8): `add_note` por título y día, como `update_event`; el `event_id` sigue mandando. Así el paso que más
    fallaba en E10 (buscar y luego apuntar) se hace con una sola llamada."""

    def test_add_note_por_id_sigue_igual_y_devuelve_el_id(self, cal):
        eid = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")['event_id']
        r = cal.add_note(event_id=eid, note_text="planta baja")
        assert r['status'] == 'noted' and r['event_id'] == eid
        assert cal.get_event_notes(eid)['note'] == 'planta baja'

    def test_add_note_por_titulo_y_dia(self, cal):
        eid = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")['event_id']
        cal.add_event(title="Endoscopia", event_date=date(2027, 2, 4), event_time="09:30")
        r = cal.add_note(note_text="acompaña Marta", title="endoscopia", event_date=date(2027, 1, 28))
        assert r['status'] == 'noted' and r['event_id'] == eid
        assert cal.get_event_notes(eid)['note'] == 'acompaña Marta'

    def test_add_note_por_titulo_sin_dia_con_un_solo_evento(self, cal):
        eid = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")['event_id']
        assert cal.add_note(note_text="planta baja", title="Endoscopia")['event_id'] == eid

    def test_add_note_ambiguo_devuelve_candidatos_y_no_escribe(self, cal):
        a = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")['event_id']
        b = cal.add_event(title="Endoscopia", event_date=date(2027, 2, 4), event_time="10:00")['event_id']
        r = cal.add_note(note_text="planta baja", title="Endoscopia")
        assert r['status'] == 'ambiguous'
        assert {c['event_id'] for c in r['candidates']} == {a, b}
        assert all({'event_id', 'title', 'date', 'time'} <= set(c) for c in r['candidates'])
        assert cal.get_event_notes(a) is None and cal.get_event_notes(b) is None

    def test_add_note_not_found_dice_que_no_lo_cree_de_nuevo(self, cal):
        for kwargs in ({"title": "NoExiste"}, {"event_id": 999999999}, {}):
            r = cal.add_note(note_text="x", **kwargs)
            assert r['status'] == 'not_found'
            assert "pregunta al usuario" in r['message'] and "no lo crees de nuevo" in r['message']

    def test_add_note_de_otro_usuario_no_toca_nada(self, cal, db_conn):
        eid = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")['event_id']
        intruso = CalendarModule(db_conn, "test_user_calendar_otro")
        por_id = intruso.add_note(event_id=eid, note_text="intruso")
        por_titulo = intruso.add_note(note_text="intruso", title="Endoscopia", event_date=date(2027, 1, 28))
        assert por_id['status'] == 'not_found' and por_titulo['status'] == 'not_found'
        assert cal.get_event_notes(eid) is None

    def test_el_id_manda_sobre_el_titulo(self, cal):
        a = cal.add_event(title="Endoscopia", event_date=date(2027, 1, 28), event_time="09:30")['event_id']
        b = cal.add_event(title="Dentista", event_date=date(2027, 1, 28), event_time="12:00")['event_id']
        assert cal.add_note(event_id=a, note_text="x", title="Dentista")['event_id'] == a
        assert cal.get_event_notes(b) is None


class TestFindByDatetime:
    def test_find_single_event_by_date_and_time(self, cal):
        """find_by_datetime() returns event dict for a matching single event."""
        cal.add_event(title="Médico", event_date=date(2026, 3, 15), event_time="10:30")
        result = cal.find_by_datetime(date(2026, 3, 15), "10:30")
        assert result is not None
        assert result['title'] == 'Médico'

    def test_find_by_datetime_returns_none_when_no_match(self, cal):
        """find_by_datetime() returns None when no event at that date/time."""
        result = cal.find_by_datetime(date(2026, 12, 31), "23:59")
        assert result is None

    def test_find_recurring_event_by_datetime(self, cal):
        """find_by_datetime() finds a recurring event that occurs on the given date."""
        from datetime import timedelta
        next_monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
        cal.add_event(title="Pilates semanal", event_date=next_monday,
                      event_time="19:00", recurrence_rule="weekly:MON")
        result = cal.find_by_datetime(next_monday, "19:00")
        assert result is not None
        assert 'Pilates' in result['title']


class TestSearchEventsPorPalabras:
    """Fase 3 H9 (R23, D61): la búsqueda es por palabras (sin acentos ni mayúsculas ni palabras vacías), en dos niveles."""

    def _titulos(self, resultados):
        return [e['title'] for e in resultados]

    def _cena(self, cal):
        cal.add_event(title="Cena de Navidad BNP - TBC", event_date=date(2026, 11, 27), event_time="20:30")

    def test_la_frase_con_de_de_mas_encuentra_el_titulo_en_primer_nivel(self, cal):
        self._cena(cal)
        r = cal.search_events("cena de Navidad de BNP")
        assert self._titulos(r) == ["Cena de Navidad BNP - TBC"]
        assert 'coincidencia' not in r[0]

    def test_una_sola_palabra(self, cal):
        self._cena(cal)
        assert self._titulos(cal.search_events("BNP")) == ["Cena de Navidad BNP - TBC"]

    def test_mayusculas_y_acentos(self, cal):
        self._cena(cal)
        assert self._titulos(cal.search_events("CENA navidad")) == ["Cena de Navidad BNP - TBC"]
        assert self._titulos(cal.search_events("navidád")) == ["Cena de Navidad BNP - TBC"]

    def test_sin_acento_encuentra_con_acento(self, cal):
        cal.add_event(title="Revisión dental", event_date=date(2026, 12, 1), event_time="10:00")
        assert self._titulos(cal.search_events("revision")) == ["Revisión dental"]

    def test_segundo_nivel_marca_parcial_si_no_hay_primero(self, cal):
        self._cena(cal)
        r = cal.search_events("cena con Ana")
        assert self._titulos(r) == ["Cena de Navidad BNP - TBC"]
        assert r[0]['coincidencia'] == "parcial"

    def test_si_hay_primer_nivel_no_se_mezclan_parciales(self, cal):
        self._cena(cal)
        cal.add_event(title="Cena con Ana", event_date=date(2026, 11, 28), event_time="21:00")
        r = cal.search_events("cena con Ana")
        assert self._titulos(r) == ["Cena con Ana"]
        assert 'coincidencia' not in r[0]

    def test_parciales_ordenados_por_coincidencias_y_luego_por_fecha(self, cal):
        cal.add_event(title="Cena", event_date=date(2026, 11, 20), event_time="21:00")
        cal.add_event(title="Cena Navidad", event_date=date(2026, 12, 20), event_time="21:00")
        cal.add_event(title="Navidad", event_date=date(2026, 11, 25), event_time="21:00")
        r = cal.search_events("cena navidad empresa")
        assert self._titulos(r) == ["Cena Navidad", "Cena", "Navidad"]
        assert all(e['coincidencia'] == "parcial" for e in r)

    def test_nada_que_ver_devuelve_vacio(self, cal):
        self._cena(cal)
        assert cal.search_events("xyz inexistente") == []

    def test_consulta_vacia_devuelve_todos(self, cal):
        self._cena(cal)
        cal.add_event(title="Dentista", event_date=date(2026, 12, 1), event_time="10:00")
        assert len(cal.search_events("")) == 2

    def test_solo_palabras_vacias_mantiene_el_comportamiento_de_antes(self, cal):
        """«de»: sin palabras útiles se busca el texto tal cual (subcadena), como hasta ahora."""
        cal.add_event(title="Cena de Navidad", event_date=date(2026, 12, 1), event_time="10:00")
        cal.add_event(title="Pilates", event_date=date(2026, 12, 2), event_time="10:00")
        assert self._titulos(cal.search_events("de")) == ["Cena de Navidad"]

    def test_palabras_de_una_letra_se_ignoran(self, cal):
        cal.add_event(title="Dentista", event_date=date(2026, 12, 2), event_time="10:00")
        assert self._titulos(cal.search_events("x dentista")) == ["Dentista"]

    def test_no_mezcla_eventos_de_otros_usuarios(self, cal, db_conn):
        CalendarModule(db_conn, "test_user_calendar_otro").add_event(
            title="Cena de Navidad BNP", event_date=date(2026, 11, 27), event_time="20:30")
        try:
            assert cal.search_events("navidad") == []
        finally:
            c = db_conn.cursor()
            c.execute("DELETE FROM events WHERE user_id = %s", ("test_user_calendar_otro",))
            db_conn.commit()

    def test_recurrente_en_primer_nivel_sigue_dando_su_proxima_ocurrencia(self, cal):
        cal.add_event(title="Clase de inglés", event_date=date.today(), event_time="19:00", recurrence_rule="daily")
        r = cal.search_events("clase ingles")
        assert len(r) == 1 and r[0]['recurring'] is True and r[0]['date'] >= date.today()

    def test_el_texto_de_la_consulta_no_va_a_ningun_log(self, cal):
        from loguru import logger as loguru_logger
        mensajes = []
        ident = loguru_logger.add(lambda m: mensajes.append(str(m)), level="DEBUG")
        try:
            self._cena(cal)
            cal.search_events("cena de Navidad de BNP secretisimo")
        finally:
            loguru_logger.remove(ident)
        volcado = " ".join(mensajes)
        assert "secretisimo" not in volcado and "cena de Navidad de BNP" not in volcado
        assert "query_chars=" in volcado and "palabras=" in volcado
