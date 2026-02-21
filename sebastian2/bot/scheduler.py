# bot/scheduler.py
"""
APScheduler-based daily reminder for calendar events.
Fires every morning and sends today's agenda to authorized users.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from db.connection import get_connection, close_connection
from modules.calendar import CalendarModule
from modules.chat import ChatModule
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
                    continue  # No events today → no message (no spam)

                lines = ["📅 **Buenos días! Tu agenda de hoy:**\n"]
                for e in events:
                    recurring_icon = " 🔄" if e.get('recurring') else ""
                    if e.get('all_day'):
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


def _cleanup_conversations():
    """Delete chat history from previous days."""
    conn = get_connection()
    try:
        ChatModule.cleanup_old_conversations(conn)
    except Exception as e:
        logger.error(f"Error cleaning up conversations: {e}")
    finally:
        close_connection()


def start_daily_reminder(bot, config: dict) -> BackgroundScheduler:
    """
    Start the APScheduler background scheduler for daily calendar reminders.

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
    scheduler.add_job(
        _cleanup_conversations,
        trigger='cron',
        hour=0,
        minute=5,
        id='cleanup_conversations',
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"Daily calendar reminder scheduled at {reminder_time} for {len(user_ids)} user(s)")
    return scheduler
