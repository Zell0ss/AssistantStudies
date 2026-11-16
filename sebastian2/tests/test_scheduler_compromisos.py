"""Fase 3, H2 (D47, D48, D51; plan §2.3 y §3-H2): el resumen de la mañana y los avisos a su hora.

Contra `sebastian_test`, sin API, con un reloj inyectado y un bot falso que registra los envíos. **Ninguna prueba manda
nada a Telegram de verdad**: una guarda (autouse) hace fallar el test si el bot real llega a construirse.
El caso es el de una endoscopia con datos INVENTADOS (prueba, dieta, nombres y centro; la fecha de la cita, 17/12/2026, es la del calendario del plan).
"""
from datetime import date, datetime, time
from unittest.mock import patch

import pytest

from bot.scheduler import _registrar_jobs, armar_resumen, enviar_avisos, _send_daily_reminder
from db.connection import close_connection, get_connection
from modules.calendar import CalendarModule
from modules.compromisos import CompromisosModule

USUARIO = "987650001"
OTRO = "987650002"
SECRETO = "texto-que-no-debe-ir-a-los-logs"


class BotFalso:
    """Registra los envíos. `fallos` = cuántos envíos lanzan una excepción antes de empezar a funcionar."""

    def __init__(self, fallos=0):
        self.enviados = []
        self.fallos = fallos

    def send_message(self, chat_id, text, **kwargs):
        if self.fallos > 0:
            self.fallos -= 1
            raise ConnectionError(f"Telegram caído ({text})")
        self.enviados.append((chat_id, text))


@pytest.fixture(autouse=True)
def _guarda_sin_telegram_real():
    """Si algo construye un `telebot.TeleBot` de verdad durante estas pruebas, fallan (plan §4)."""
    import telebot

    def _prohibido(*args, **kwargs):
        raise AssertionError("una prueba ha intentado construir el bot real de Telegram")

    with patch.object(telebot.TeleBot, "__init__", _prohibido):
        yield


def _limpiar(conn):
    cur = conn.cursor()
    for u in (USUARIO, OTRO):
        cur.execute("DELETE FROM compromisos WHERE user_id = %s", (u,))
        cur.execute("DELETE FROM events WHERE user_id = %s", (u,))
    conn.commit()


@pytest.fixture
def conn():
    c = get_connection()
    _limpiar(c)
    yield c
    _limpiar(c)
    close_connection()


@pytest.fixture
def bot():
    return BotFalso()


def _comp(conn, usuario=USUARIO):
    return CompromisosModule(conn, usuario, reloj=lambda: datetime(2026, 12, 1, 12, 0))


@pytest.fixture
def caso(conn):
    """El caso: la cita del 17/12 a las 9:30 y sus pasos (inventados, sin datos personales)."""
    cita = CalendarModule(conn, USUARIO).add_event("Endoscopia", date(2026, 12, 17), "09:30")["event_id"]
    ids = _comp(conn).crear([
        {"texto": "Dieta blanda", "evento_id": cita, "dias_inicio": -3, "dias_fin": -1},
        {"texto": "Solo líquidos claros", "evento_id": cita, "dias_inicio": -1},
        {"texto": "1.ª toma del preparado (sobre en ½ l)", "evento_id": cita, "dias_inicio": -1, "hora": "21:00"},
        {"texto": "2.ª toma del preparado (sobres A y B en ½ l)", "evento_id": cita, "dias_inicio": 0, "hora": "01:00"},
        {"texto": "Última hora para líquidos", "evento_id": cita, "minutos": -180},
        {"texto": "Llevar el parte de interconsulta", "evento_id": cita, "dias_inicio": 0},
    ])["compromisos"]
    return {"cita": cita, "ids": {c["texto"]: c["id"] for c in ids}}


def _a(dia, hora, minuto=0):
    return lambda: datetime(2026, 12, dia, hora, minuto)


def _aviso_para(conn, compromiso_id):
    conn.commit()                                   # termina la instantánea de la lectura anterior (REPEATABLE READ)
    cur = conn.cursor()
    cur.execute("SELECT aviso_para FROM compromisos WHERE id = %s", (compromiso_id,))
    return cur.fetchone()["aviso_para"]


# ── Resumen de la mañana ─────────────────────────────────────────────────────────────────────────────────────────────

def test_resumen_14_dieta_dia_1(conn, caso):
    texto = armar_resumen(USUARIO, datetime(2026, 12, 14, 8, 0), conn=conn)
    assert "Dieta blanda (día 1 de 3)" in texto
    assert "Para hoy" in texto


def test_resumen_15_dieta_dia_2(conn, caso):
    assert "Dieta blanda (día 2 de 3)" in armar_resumen(USUARIO, datetime(2026, 12, 15, 8, 0), conn=conn)


def test_resumen_16_mira_a_manana(conn, caso):
    texto = armar_resumen(USUARIO, datetime(2026, 12, 16, 8, 0), conn=conn)
    para_hoy, antes = texto.index("Para hoy"), texto.index("Antes del próximo resumen")
    assert para_hoy < antes
    hoy, manana = texto[para_hoy:antes], texto[antes:]
    assert "Solo líquidos claros" in hoy and "21:00" in hoy and "1.ª toma del preparado" in hoy
    assert "Dieta blanda (día 3 de 3)" in hoy
    assert "01:00" in manana and "2.ª toma del preparado" in manana
    assert "06:30" in manana and "Última hora para líquidos" in manana
    assert "1.ª toma" not in manana and "Solo líquidos claros" not in manana
    assert manana.index("01:00") < manana.index("06:30")                       # en orden


def test_resumen_17_el_dia_de_la_prueba(conn, caso):
    texto = armar_resumen(USUARIO, datetime(2026, 12, 17, 8, 0), conn=conn)
    assert "09:30 — Endoscopia" in texto                                     # la agenda de siempre
    assert "Llevar el parte de interconsulta" in texto                         # sin hora: «Para hoy»
    assert "06:30" not in texto and "01:00" not in texto                       # ya pasaron: nadie avisa tarde
    assert "Antes del próximo resumen" not in texto                            # y no hay nada antes del siguiente


def test_resumen_dia_vacio_calla(conn, caso, bot):
    """D47: si no hay nada, no se manda nada."""
    assert armar_resumen(USUARIO, datetime(2026, 12, 10, 8, 0), conn=conn) is None
    _send_daily_reminder(bot, [USUARIO], reloj=_a(10, 8))
    assert bot.enviados == []


def test_resumen_una_seccion_vacia_no_se_escribe(conn, caso):
    texto = armar_resumen(USUARIO, datetime(2026, 12, 14, 8, 0), conn=conn)
    assert "Antes del próximo resumen" not in texto                            # el 15 a las 01:00 no hay nada
    assert "(nada)" not in texto


def test_resumen_agenda_sin_compromisos_igual_que_hoy(conn):
    """No se rompe lo existente: el texto de un día con solo agenda es literalmente el de antes."""
    cal = CalendarModule(conn, USUARIO)
    cal.add_event("Dentista", date(2026, 12, 5), "17:00")
    cal.add_event("Revisión", date(2026, 12, 5), all_day=True)
    cal.add_event("Yoga", date(2026, 12, 5), "19:00", recurrence_rule="daily")
    esperado = (
        "📅 **Buenos días! Tu agenda de hoy:**\n"
        "\n"
        "• (todo el día) — Revisión\n"
        "• 17:00 — Dentista\n"
        "• 19:00 — Yoga 🔄\n"
        "\n¡Que tengas un buen día!"
    )
    assert armar_resumen(USUARIO, datetime(2026, 12, 5, 8, 0), conn=conn) == esperado


def test_resumen_sin_agenda_pero_con_compromisos_no_dice_agenda_vacia(conn, caso):
    texto = armar_resumen(USUARIO, datetime(2026, 12, 14, 8, 0), conn=conn)
    assert "Tu agenda de hoy" not in texto and texto.startswith("📅")


def test_resumen_hoy_es_el_de_ahora_inyectado_no_el_del_sistema(conn):
    CalendarModule(conn, USUARIO).add_event("Dentista", date(2026, 12, 5), "17:00")
    assert armar_resumen(USUARIO, datetime(2026, 12, 4, 8, 0), conn=conn) is None
    assert "Dentista" in armar_resumen(USUARIO, datetime(2026, 12, 5, 8, 0), conn=conn)


def test_resumen_un_compromiso_con_hora_ya_pasada_no_sale_en_para_hoy(conn):
    _comp(conn).crear([{"texto": "Pasado", "fecha_inicio": "2026-12-10", "hora": "07:00"},
                       {"texto": "Futuro", "fecha_inicio": "2026-12-10", "hora": "20:00"}])
    texto = armar_resumen(USUARIO, datetime(2026, 12, 10, 8, 0), conn=conn)
    assert "Futuro" in texto and "Pasado" not in texto


def test_resumen_respeta_la_hora_del_resumen_configurada(conn):
    _comp(conn).crear([{"texto": "Madrugón", "fecha_inicio": "2026-12-11", "hora": "08:30"}])
    ahora = datetime(2026, 12, 10, 8, 0)
    assert armar_resumen(USUARIO, ahora, conn=conn, hora_resumen=time(8, 0)) is None          # lo cubre el de mañana
    assert "Madrugón" in armar_resumen(USUARIO, ahora, conn=conn, hora_resumen=time(9, 0))    # resumen a las 9: va antes


def test_resumen_no_mezcla_usuarios(conn, caso):
    assert armar_resumen(OTRO, datetime(2026, 12, 16, 8, 0), conn=conn) is None


def test_resumen_manda_a_cada_usuario_a_su_chat_y_un_fallo_no_para_a_los_demas(conn, caso):
    _comp(conn, OTRO).crear([{"texto": "Del otro", "fecha_inicio": "2026-12-16"}])
    bot = BotFalso(fallos=1)                                                   # el primer envío falla
    _send_daily_reminder(bot, [USUARIO, OTRO], reloj=_a(16, 8))
    assert [c for c, _ in bot.enviados] == [int(OTRO)]
    assert "Del otro" in bot.enviados[0][1]


def test_resumen_se_envia_al_chat_del_usuario(conn, caso, bot):
    _send_daily_reminder(bot, [USUARIO], reloj=_a(14, 8))
    assert len(bot.enviados) == 1 and bot.enviados[0][0] == int(USUARIO)
    assert "Dieta blanda (día 1 de 3)" in bot.enviados[0][1]


# ── Avisos a su hora ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_aviso_a_su_hora(conn, caso, bot):
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 0))
    assert len(bot.enviados) == 1
    chat, texto = bot.enviados[0]
    assert chat == int(USUARIO)
    assert texto == "⏰ 01:00 · 2.ª toma del preparado (sobres A y B en ½ l) — Endoscopia"
    assert _aviso_para(conn, caso["ids"]["2.ª toma del preparado (sobres A y B en ½ l)"]) == datetime(2026, 12, 17, 1, 0)
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 1))
    assert len(bot.enviados) == 1                                              # a las 01:01 no se repite


def test_aviso_no_se_repite_si_la_tarea_corre_dos_veces_en_el_mismo_minuto(conn, caso, bot):
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 0))
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 0))
    assert len(bot.enviados) == 1


def test_aviso_no_sale_antes_de_su_hora(conn, caso, bot):
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 0, 59))
    assert bot.enviados == []


def test_aviso_tras_reinicio_dentro_de_ventana(conn, caso, bot):
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 2, 30), arranque=True)
    assert [t for _, t in bot.enviados] == ["⏰ 01:00 · 2.ª toma del preparado (sobres A y B en ½ l) — Endoscopia"]


def test_aviso_caducado_no_sale(conn, caso, bot):
    with patch("bot.scheduler.logger") as log:
        enviar_avisos(bot, [USUARIO], reloj=_a(17, 3, 30), arranque=True)
    assert bot.enviados == []
    volcado = " ".join(str(c) for c in log.mock_calls)
    assert "caducado" in volcado
    assert str(caso["ids"]["2.ª toma del preparado (sobres A y B en ½ l)"]) in volcado


def test_aviso_justo_a_las_dos_horas_ya_esta_caducado(conn, caso, bot):
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 3, 0))
    assert bot.enviados == []


def test_aviso_caducado_se_loguea_una_vez_y_no_cada_minuto(conn, caso, bot):
    """El bot estuvo parado de la 01:00 a las 03:00: el minuto en que el aviso cruza las 2 h deja una línea, y ya está."""
    cid = str(caso["ids"]["2.ª toma del preparado (sobres A y B en ½ l)"])
    with patch("bot.scheduler.logger") as log:
        for minuto in (0, 1, 2, 3):                                            # 03:00 cruza las 2 h; después, silencio
            enviar_avisos(bot, [USUARIO], reloj=_a(17, 3, minuto))
    caducados = [c for c in log.mock_calls if "caducado" in str(c) and f"id={cid} " in str(c)]
    assert bot.enviados == [] and len(caducados) == 1


def test_aviso_fallo_envio_reintenta(conn, caso):
    bot = BotFalso(fallos=1)
    cid = caso["ids"]["2.ª toma del preparado (sobres A y B en ½ l)"]
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 0))                          # no debe propagar la excepción
    assert bot.enviados == [] and _aviso_para(conn, cid) is None               # aviso_para sigue a NULL
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 1))                          # al minuto siguiente sale
    assert len(bot.enviados) == 1 and _aviso_para(conn, cid) == datetime(2026, 12, 17, 1, 0)


def test_aviso_fallo_de_un_usuario_no_para_a_los_demas(conn, caso):
    _comp(conn, OTRO).crear([{"texto": "Del otro", "fecha_inicio": "2026-12-17", "hora": "01:00"}])
    bot = BotFalso(fallos=1)
    enviar_avisos(bot, [USUARIO, OTRO], reloj=_a(17, 1, 0))
    assert [c for c, _ in bot.enviados] == [int(OTRO)]


def test_aviso_evento_movido_vuelve_a_avisar(conn, caso, bot):
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 0))
    assert len(bot.enviados) == 1
    CalendarModule(conn, USUARIO).update_event("Endoscopia", new_date=date(2026, 12, 18))
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 1))
    assert len(bot.enviados) == 1                                              # el momento nuevo aún no ha llegado
    enviar_avisos(bot, [USUARIO], reloj=_a(18, 1, 0))
    assert len(bot.enviados) == 2 and bot.enviados[1][1].startswith("⏰ 01:00 · 2.ª toma")


def test_aviso_solo_pendientes(conn, caso, bot):
    cid = caso["ids"]["2.ª toma del preparado (sobres A y B en ½ l)"]
    c = _comp(conn)
    c.completar(cid)
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 0))
    assert bot.enviados == []
    otro = _comp(conn).crear([{"texto": "Cancelado", "fecha_inicio": "2026-12-17", "hora": "01:00"}])["compromisos"][0]
    c.borrar(otro["id"], "cancelar")
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 0))
    assert bot.enviados == []


def test_aviso_solo_los_que_tienen_hora(conn, caso, bot):
    """La dieta y los líquidos claros no tienen hora: los cuenta el resumen, no un aviso."""
    for hora in range(0, 24):
        enviar_avisos(bot, [USUARIO], reloj=_a(16, hora, 0))
    textos = " ".join(t for _, t in bot.enviados)
    assert "Dieta" not in textos and "Solo líquidos" not in textos
    assert "1.ª toma del preparado" in textos


def test_aviso_de_un_compromiso_suelto_no_lleva_evento(conn, bot):
    _comp(conn).crear([{"texto": "Llamar al médico", "fecha_inicio": "2026-12-10", "hora": "17:30"}])
    enviar_avisos(bot, [USUARIO], reloj=_a(10, 17, 30))
    assert bot.enviados == [(int(USUARIO), "⏰ 17:30 · Llamar al médico")]


def test_aviso_un_compromiso_que_no_se_puede_calcular_no_avisa_ni_rompe(conn, caso, bot):
    CalendarModule(conn, USUARIO).update_event("Endoscopia", new_date=date(2026, 12, 17), new_all_day=True)
    enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 0))                          # los de minutos ya no tienen hora
    textos = [t for _, t in bot.enviados]
    assert not any("Última hora para líquidos" in t for t in textos)


def test_log_sin_texto(conn, bot):
    """Lección de R12: ni los envíos ni los fallos ni los caducados escriben el texto del compromiso en LogCentral."""
    c = _comp(conn)
    c.crear([{"texto": SECRETO, "fecha_inicio": "2026-12-17", "hora": "01:00"},
             {"texto": SECRETO + "-caducado", "fecha_inicio": "2026-12-17", "hora": "01:30"}])
    fallido = BotFalso(fallos=1)
    with patch("bot.scheduler.logger") as log:
        enviar_avisos(fallido, [USUARIO], reloj=_a(17, 1, 0))                  # un fallo, con el texto en la excepción
        enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 1))                      # el envío bueno
        enviar_avisos(bot, [USUARIO], reloj=_a(17, 3, 45), arranque=True)      # y el caducado (la 01:30)
        armar = armar_resumen(USUARIO, datetime(2026, 12, 17, 0, 5), conn=conn)
    assert SECRETO in armar                                                    # el resumen sí lo lleva (es el mensaje)
    volcado = " ".join(str(call) for call in log.mock_calls)
    assert SECRETO not in volcado
    assert "caducado" in volcado and "enviado" in volcado and "fallo" in volcado


def test_log_del_aviso_lleva_id_usuario_momento_y_resultado(conn, bot):
    cid = _comp(conn).crear([{"texto": "x", "fecha_inicio": "2026-12-17", "hora": "01:00"}])["compromisos"][0]["id"]
    with patch("bot.scheduler.logger") as log:
        enviar_avisos(bot, [USUARIO], reloj=_a(17, 1, 0))
    linea = next(str(c) for c in log.mock_calls if "enviado" in str(c))
    assert f"id={cid}" in linea and f"user={USUARIO}" in linea and "2026-12-17 01:00" in linea


# ── Registro de las tareas ───────────────────────────────────────────────────────────────────────────────────────────

def test_las_tareas_se_registran_en_el_planificador_del_bot():
    from apscheduler.schedulers.background import BackgroundScheduler
    s = BackgroundScheduler()
    _registrar_jobs(s, BotFalso(), {"authorized_ids": [111], "calendar": {"daily_reminder_time": "08:30"}})
    jobs = {j.id: j for j in s.get_jobs()}
    assert {"daily_calendar_reminder", "avisos_compromisos", "avisos_compromisos_arranque",
            "cleanup_conversations"} <= set(jobs)
    avisos = jobs["avisos_compromisos"]
    assert avisos.max_instances == 1 and avisos.coalesce is True
    assert avisos.trigger.interval.total_seconds() == 60
    resumen = jobs["daily_calendar_reminder"]
    assert str(resumen.trigger) == "cron[hour='8', minute='30']"
    assert jobs["avisos_compromisos_arranque"].kwargs["arranque"] is True        # corre una vez nada más arrancar


def test_la_guarda_impide_construir_el_bot_real():
    import telebot
    with pytest.raises(AssertionError):
        telebot.TeleBot("123:fake")
