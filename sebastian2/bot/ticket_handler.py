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

_MONTHS_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
               'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


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


def _format_date(d) -> str:
    """Format a date as '3 de marzo'."""
    return f"{d.day} de {_MONTHS_ES[d.month - 1]}"


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
            conn = get_connection()
            cal = CalendarModule(conn, user_id)
            events = cal.search_events(caption)
            if events:
                event_id = events[0]['event_id']
                event_title = events[0]['title']
        except Exception as e:
            logger.warning(f"Caption event search failed, will ask user: {e}")

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
    lines = [f"Encontré {len(tickets)} código(s) ({types_str}). ¿A qué cita lo asocio?\n"]
    for i, e in enumerate(upcoming, 1):
        date_str = _format_date(e['date'])
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
