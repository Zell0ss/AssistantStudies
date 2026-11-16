# bot/scheduler.py
"""
Planificador del bot (APScheduler). Tres tareas, sin unidades systemd (D48):

- `daily_calendar_reminder`: el resumen de la mañana. Agenda + compromisos del día + lo que cae antes del próximo
  resumen (D45, D47: si no hay nada, calla). Se arma con plantilla, sin LLM: sin coste y sin inventar nada.
- `avisos_compromisos`: cada minuto, manda por Telegram cada compromiso con hora cuando le llega el momento (D48),
  y una vez más nada más arrancar el bot, para recuperar los avisos que un reinicio se haya llevado.
- `cleanup_conversations`: el historial de más de 7 días (D23).

Los logs de los avisos llevan id, usuario, momento y resultado, nunca el texto del compromiso (lección de R12, D52).
"""
from datetime import datetime, time, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from db.connection import close_connection, get_connection, init_pool
from modules.calendar import CalendarModule
from modules.compromisos import CompromisosModule
from db.conversation_repo import ConversationRepository
from logcentral_client import get_logger

logger = get_logger("sebastian")

_HORA_RESUMEN_DEFECTO = time(8, 0)
_VENTANA_AVISO = timedelta(hours=2)        # D51: pasadas 2 h, un aviso tardío confunde más de lo que ayuda


def _conexion_propia():
    """Una conexión del pool solo para esta tarea. `get_connection()` es un singleton del proceso, y cerrarlo desde el
    hilo del planificador (cada minuto) le quitaría la conexión a un manejador de mensajes que esté en medio de una consulta."""
    return init_pool().connection()


# ── Resumen de la mañana ─────────────────────────────────────────────────────────────────────────────────────────────

def _linea_agenda(e: dict) -> str:
    recurring_icon = " 🔄" if e.get('recurring') else ""
    if e.get('all_day'):
        return f"• (todo el día) — {e['title']}{recurring_icon}"
    return f"• {e['time']} — {e['title']}{recurring_icon}"


def _orden(p: dict):
    m = p["momento"]
    return (m.cuando.time() if m.cuando else time.min, p["fila"]["id"])


def armar_resumen(usuario, ahora: datetime, conn=None, hora_resumen: time = _HORA_RESUMEN_DEFECTO) -> Optional[str]:
    """El resumen de las 08:00 de un usuario, o `None` si no hay nada que decir (D47). Función pura sobre la BD: no envía.

    Con `conn=None` usa el singleton `get_connection()` y lo cierra al terminar (`close_connection()`): vale para un script,
    pero NO desde un manejador de Telegram (cerraría la conexión del proceso en mitad de otra consulta). El planificador
    siempre pasa su conexión propia (`_conexion_propia()`); quien llame desde un manejador, que haga lo mismo.

    Tres bloques, y el vacío no se escribe:
    - agenda de hoy (como siempre);
    - «Para hoy»: los compromisos cuyo día o intervalo incluye hoy, y los que tienen hora entre ahora y las 23:59;
    - «Antes del próximo resumen»: los de mañana con hora anterior a `hora_resumen` (de madrugada solo llega el aviso, y
      el resumen del día siguiente llegaría tarde).
    """
    propia = conn is None
    conn = conn or get_connection()
    try:
        hoy, manana = ahora.date(), ahora.date() + timedelta(days=1)
        eventos = CalendarModule(conn, str(usuario)).list_events('today', hoy=hoy)
        para_hoy, antes = [], []
        for p in CompromisosModule(conn, str(usuario), reloj=lambda: ahora).pendientes():
            m = p["momento"]
            if m.problema is not None:
                continue                                                    # sin momento calculable: no se puede situar
            if m.fecha_inicio <= hoy <= m.fecha_fin and (m.cuando is None or m.cuando >= ahora):
                para_hoy.append(p)
            elif m.cuando is not None and m.cuando.date() == manana and m.cuando.time() < hora_resumen:
                antes.append(p)

        if not eventos and not para_hoy and not antes:
            return None

        lineas = ["📅 **Buenos días! Tu agenda de hoy:**\n" if eventos else "📅 **Buenos días!**\n"]
        lineas += [_linea_agenda(e) for e in eventos]
        if para_hoy:
            lineas.append(("\n" if eventos else "") + "✅ **Para hoy:**")
            for p in sorted(para_hoy, key=_orden):
                m, texto = p["momento"], p["fila"]["texto"]
                if m.cuando is not None:
                    lineas.append(f"• {m.cuando:%H:%M} — {texto}")
                elif m.fecha_fin > m.fecha_inicio:                          # un intervalo se escribe con su posición
                    dia = (hoy - m.fecha_inicio).days + 1
                    total = (m.fecha_fin - m.fecha_inicio).days + 1
                    lineas.append(f"• {texto} (día {dia} de {total})")
                else:
                    lineas.append(f"• {texto}")
        if antes:
            lineas.append("\n⏰ **Antes del próximo resumen:**")
            lineas += [f"• {p['momento'].cuando:%H:%M} — {p['fila']['texto']}" for p in sorted(antes, key=_orden)]
        lineas.append("\n¡Que tengas un buen día!")
        return '\n'.join(lineas)
    finally:
        if propia:
            close_connection()


def _send_daily_reminder(bot, user_ids: list, reloj=None, hora_resumen: time = _HORA_RESUMEN_DEFECTO):
    """
    Arma y manda el resumen de la mañana a cada usuario. Si no hay nada, no manda nada (D47).

    Args:
        bot: TeleBot instance
        user_ids: List of Telegram user IDs (strings or ints)
        reloj: callable sin argumentos que da la hora local (inyectable en las pruebas)
        hora_resumen: la hora a la que corre esta tarea, para «antes del próximo resumen»
    """
    ahora = (reloj or datetime.now)()
    conn = _conexion_propia()
    try:
        for user_id in user_ids:
            try:
                mensaje = armar_resumen(str(user_id), ahora, conn=conn, hora_resumen=hora_resumen)
                if mensaje is None:
                    continue  # nada que decir → no se manda nada (no spam)
                bot.send_message(chat_id=int(user_id), text=mensaje)
                logger.info(f"Daily reminder sent to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending daily reminder to {user_id}: {type(e).__name__}")
    finally:
        conn.close()


# ── Avisos a su hora ─────────────────────────────────────────────────────────────────────────────────────────────────

def _log_aviso(resultado: str, compromiso_id, usuario, momento: datetime, nivel: str = "info"):
    getattr(logger, nivel)(
        f"Aviso compromiso id={compromiso_id} user={usuario} momento={momento:%Y-%m-%d %H:%M} resultado={resultado}")


def enviar_avisos(bot, user_ids: list, reloj=None, arranque: bool = False):
    """La tarea de cada minuto (D48, D51): avisa de los compromisos con hora cuyo momento `m` cumple
    `ahora − 2 h < m ≤ ahora` y para los que aún no se avisó (`aviso_para` distinto de `m`).

    Escribe `aviso_para = m` DESPUÉS de enviar: si el envío falla, queda sin escribir y se reintenta al minuto siguiente.
    Es idempotente: corre dos veces o tras un reinicio sin repetir el aviso. Si el evento se mueve, `m` cambia y el aviso
    vuelve a quedar pendiente.

    Un aviso que ya pasó de las 2 h no se manda: deja una línea «caducado». Para no repetirla cada minuto, se escribe una
    vez, en el minuto en que cruza las 2 h, o —con `arranque`— para todos los que un reinicio haya dejado atrás.
    """
    ahora = (reloj or datetime.now)().replace(second=0, microsecond=0)
    limite = ahora - _VENTANA_AVISO
    conn = _conexion_propia()
    try:
        for user_id in user_ids:
            try:
                modulo = CompromisosModule(conn, str(user_id), reloj=lambda: ahora)
                for p in modulo.pendientes():
                    m = p["momento"].cuando
                    fila = p["fila"]
                    if m is None or p["aviso_para"] == m or m > ahora:
                        continue
                    if m <= limite:
                        if arranque or m > limite - timedelta(minutes=1):
                            _log_aviso("caducado", fila["id"], user_id, m, "warning")
                        continue
                    texto = f"⏰ {m:%H:%M} · {fila['texto']}"
                    if p["evento_titulo"]:
                        texto += f" — {p['evento_titulo']}"
                    try:
                        bot.send_message(chat_id=int(user_id), text=texto)
                    except Exception as e:                                  # el texto va en la excepción: solo su clase
                        _log_aviso(f"fallo({type(e).__name__}), se reintenta", fila["id"], user_id, m, "error")
                        continue
                    modulo.registrar_aviso(fila["id"], m)
                    _log_aviso("enviado", fila["id"], user_id, m)
            except Exception as e:
                logger.error(f"Error en los avisos de compromisos user={user_id}: {type(e).__name__}")
    finally:
        conn.close()


# ── Mantenimiento y arranque ─────────────────────────────────────────────────────────────────────────────────────────

def _cleanup_conversations():
    """Delete chat history older than 7 days (D23)."""
    conn = get_connection()
    try:
        ConversationRepository(conn).limpiar(dias=7)
    except Exception as e:
        logger.error(f"Error cleaning up conversations: {e}")
    finally:
        close_connection()


def _registrar_jobs(scheduler: BackgroundScheduler, bot, config: dict) -> None:
    """Registra las tareas en `scheduler` (sin arrancarlo)."""
    reminder_time = config.get('calendar', {}).get('daily_reminder_time', '08:00')
    hour, minute = map(int, reminder_time.split(':'))

    user_ids = config.get('authorized_ids', [])
    if not user_ids:
        logger.warning("No authorized_ids in config — daily reminder will have no recipients")

    scheduler.add_job(
        _send_daily_reminder,
        trigger='cron',
        hour=hour,
        minute=minute,
        args=[bot, user_ids],
        kwargs={'hora_resumen': time(hour, minute)},
        id='daily_calendar_reminder',
        replace_existing=True
    )
    scheduler.add_job(
        enviar_avisos,
        trigger='interval',
        minutes=1,
        args=[bot, user_ids],
        max_instances=1,
        coalesce=True,
        id='avisos_compromisos',
        replace_existing=True
    )
    # D48: nada más arrancar, una pasada con `arranque`, para recuperar lo que un reinicio se haya llevado (ventana de 2 h).
    scheduler.add_job(
        enviar_avisos,
        trigger='date',
        run_date=datetime.now() + timedelta(seconds=2),
        args=[bot, user_ids],
        kwargs={'arranque': True},
        max_instances=1,
        misfire_grace_time=60,
        id='avisos_compromisos_arranque',
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


def start_daily_reminder(bot, config: dict) -> BackgroundScheduler:
    """
    Arranca el planificador del bot: resumen de la mañana, avisos de compromisos y limpieza del historial.

    Reads reminder time from config['calendar']['daily_reminder_time'] (default '08:00').
    Sends to all authorized_ids in config.

    Args:
        bot: TeleBot instance
        config: Full config dict

    Returns:
        Running BackgroundScheduler instance
    """
    scheduler = BackgroundScheduler()
    _registrar_jobs(scheduler, bot, config)
    scheduler.start()
    reminder_time = config.get('calendar', {}).get('daily_reminder_time', '08:00')
    logger.info(f"Planificador arrancado: resumen a las {reminder_time}, avisos cada minuto, "
                f"{len(config.get('authorized_ids', []))} usuario(s)")
    return scheduler
