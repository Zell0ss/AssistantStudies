"""Fase 4, H1 (D63-D67; plan §2.6 y §3, pruebas 15-25): la ronda diaria y su tarea. Contra `sebastian_test`, sin red ni API, con
reloj, fuentes, cliente y bot inyectados. **Ninguna prueba manda nada a Telegram de verdad**: una guarda hace fallar el test si
el bot real llega a construirse. Todos los datos de los anuncios son inventados."""
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from bot.scheduler import _registrar_jobs
from db.connection import close_connection, get_connection
from modules.vigilancias import repositorio
from modules.vigilancias.anuncio import FuenteError
from modules.vigilancias.ronda import armar_mensaje, le_toca, pasada_vigilancias
from modules.vigilancias.juez import Informe
from tests.fakes_vigilancias import AHORA, BotFalso, ClienteFalso, FuenteFalsa, fuente_que_falla, hacer_anuncio

USUARIO = "987650101"
OTRO = "987650102"
HOY = date(2026, 11, 20)
CONSULTAS = ["mac mini m4", "mac mini m2 pro"]


@pytest.fixture(autouse=True)
def _guarda_sin_telegram_real():
    import telebot

    def _prohibido(*args, **kwargs):
        raise AssertionError("una prueba ha intentado construir el bot real de Telegram")

    with patch.object(telebot.TeleBot, "__init__", _prohibido):
        yield


def _limpiar(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM vigilancias WHERE user_id IN (%s, %s)", (USUARIO, OTRO))       # los vistos caen por CASCADE
    conn.commit()
    cur.close()


@pytest.fixture
def conn():
    c = get_connection()
    _limpiar(c)
    yield c
    _limpiar(c)
    close_connection()


def _crear(conn, usuario=USUARIO, **cambios):
    datos = {"nombre": "Mac mini", "fuente": "wallapop", "consultas": CONSULTAS, "reglas": "Apple Silicon con 24 GB o más.",
             "filtros": {"precio_min": 300, "precio_max": 2000, "excluir": ["8gb", "intel"]}, "hora": "07:30", **cambios}
    return repositorio.guardar(conn, usuario, datos)["id"]


def _fila(conn, id_):
    cur = conn.cursor()
    cur.execute("SELECT * FROM vigilancias WHERE id = %s", (id_,))
    fila = cur.fetchone()
    cur.close()
    return fila


def _vistos(conn, id_):
    cur = conn.cursor()
    cur.execute("SELECT anuncio_id FROM vigilancia_vistos WHERE vigilancia_id = %s ORDER BY anuncio_id", (id_,))
    ids = [f["anuncio_id"] for f in cur.fetchall()]
    cur.close()
    return ids


def _a(hora, minuto):
    return lambda: datetime(2026, 11, 20, hora, minuto)


def _pasada(bot, conn, reloj=None, fuente=None, cliente=None, **kw):
    pasada_vigilancias(bot, [USUARIO], reloj=reloj or (lambda: AHORA), fuentes={"wallapop": fuente or FuenteFalsa()},
                       cliente=cliente or ClienteFalso(), conn=conn, **kw)


def _dos_anuncios():
    return [hacer_anuncio(id="m4", titulo="Mac mini M4 Pro 24 GB", precio="1150", ciudad="Valencia", modificado=datetime(2026, 11, 20, 6, 30)),
            hacer_anuncio(id="m2", titulo="Mac mini M2 16 GB", precio="380", ciudad="Sevilla", modificado=datetime(2026, 11, 20, 5, 0))]


# ── Una ronda buena ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_15_es_la_hora_dos_candidatos_un_elegido_se_envia_y_quedan_los_dos_vistos(conn):
    vid = _crear(conn)
    bot = BotFalso()
    cliente = ClienteFalso(elegidos=[{"id": "m4", "semaforo": "COMPRAR", "texto": "M4 Pro, 24 GB, 512 GB. Entra por RAM."}],
                           cierre="Mejor de esta ronda: el M4 Pro.")
    _pasada(bot, conn, fuente=FuenteFalsa(por_defecto=_dos_anuncios()), cliente=cliente)
    (chat, texto), = bot.enviados
    assert chat == int(USUARIO)
    assert texto.startswith("🔎 Mac mini · 20/11")
    assert "🟢 COMPRAR · Mac mini M4 Pro 24 GB · 1150 € · Valencia" in texto
    assert "M4 Pro, 24 GB, 512 GB. Entra por RAM." in texto and "https://es.wallapop.com/item/m4-slug" in texto
    assert "Mejor de esta ronda: el M4 Pro." in texto
    assert "M2 16 GB" not in texto and "Sevilla" not in texto and "m2-slug" not in texto            # el no elegido no sale
    assert _vistos(conn, vid) == ["m2", "m4"]                                                         # ¡los dos, también el que el juez descartó!
    assert _fila(conn, vid)["ultima_ronda"] == HOY
    assert len(cliente.llamadas) == 1                                                                 # una llamada, con los 2 candidatos
    assert cliente.llamadas[0]["messages"][0]["content"].count('"id"') == 2


def test_15b_el_titulo_el_precio_la_ciudad_y_el_enlace_salen_del_anuncio_aunque_el_juez_invente(conn):
    _crear(conn)
    bot = BotFalso()
    cliente = ClienteFalso(elegidos=[{"id": "m4", "semaforo": "MIRAR", "texto": "Vale 1 € en Narnia: https://trampa.example"}])
    _pasada(bot, conn, fuente=FuenteFalsa(por_defecto=_dos_anuncios()), cliente=cliente)
    texto = bot.enviados[0][1]
    assert "🟡 MIRAR · Mac mini M4 Pro 24 GB · 1150 € · Valencia" in texto and "https://es.wallapop.com/item/m4-slug" in texto


def test_15c_el_filtro_solo_deja_pasar_al_juez_lo_que_cumple(conn):
    vid = _crear(conn)
    anuncios = _dos_anuncios() + [hacer_anuncio(id="ba", titulo="Mac mini 8 GB", precio="400"), hacer_anuncio(id="ca", precio="9000"),
                                  hacer_anuncio(id="re", reservado=True), hacer_anuncio(id="vi", modificado=AHORA - timedelta(hours=60))]
    cliente = ClienteFalso()
    _pasada(BotFalso(), conn, fuente=FuenteFalsa(por_defecto=anuncios), cliente=cliente)
    contenido = cliente.llamadas[0]["messages"][0]["content"]
    assert '"id": "m4"' in contenido and '"id": "m2"' in contenido
    assert not any(f'"id": "{x}"' in contenido for x in ("ba", "ca", "re", "vi"))
    assert _vistos(conn, vid) == ["ba", "ca", "m2", "m4", "re"]          # nuevos descartados por el filtro también se guardan; «vi» no es nuevo


def test_16_si_se_repite_la_pasada_quince_minutos_despues_no_se_envia_nada(conn):
    _crear(conn)
    bot, cliente = BotFalso(), ClienteFalso()
    fuente = FuenteFalsa(por_defecto=_dos_anuncios())
    _pasada(bot, conn, fuente=fuente, cliente=cliente)
    _pasada(bot, conn, reloj=_a(7, 45), fuente=fuente, cliente=cliente)
    _pasada(bot, conn, reloj=_a(9, 31), fuente=fuente, cliente=cliente)                               # ya hubo ronda hoy: ni aviso de fallo
    assert len(bot.enviados) == 1 and len(cliente.llamadas) == 1 and fuente.consultas == CONSULTAS


def test_20_sin_candidatos_se_envia_nada_nuevo_y_ultima_ronda_es_hoy_sin_llamar_al_juez(conn):
    vid = _crear(conn)
    bot, cliente = BotFalso(), ClienteFalso()
    _pasada(bot, conn, fuente=FuenteFalsa(), cliente=cliente)
    (_, texto), = bot.enviados
    assert texto == "🔎 Mac mini · 20/11\nNada nuevo que merezca la pena."
    assert cliente.llamadas == [] and _fila(conn, vid)["ultima_ronda"] == HOY


def test_20b_si_el_juez_no_elige_ninguno_el_mensaje_es_el_de_nada_nuevo_pero_los_vistos_se_guardan(conn):
    vid = _crear(conn)
    bot = BotFalso()
    _pasada(bot, conn, fuente=FuenteFalsa(por_defecto=_dos_anuncios()), cliente=ClienteFalso(elegidos=[], cierre="Ninguno urgente."))
    assert bot.enviados[0][1].endswith("Nada nuevo que merezca la pena.")
    assert _vistos(conn, vid) == ["m2", "m4"] and _fila(conn, vid)["ultima_ronda"] == HOY


def test_el_dia_siguiente_un_anuncio_ya_visto_y_sin_cambios_no_vuelve(conn):
    vid = _crear(conn)
    fuente = FuenteFalsa(por_defecto=_dos_anuncios())
    _pasada(BotFalso(), conn, fuente=fuente)
    manana = lambda: datetime(2026, 11, 21, 7, 30)
    cliente = ClienteFalso()
    bot = BotFalso()
    _pasada(bot, conn, reloj=manana, fuente=fuente, cliente=cliente)
    assert cliente.llamadas == [] and "Nada nuevo" in bot.enviados[0][1] and _fila(conn, vid)["ultima_ronda"] == date(2026, 11, 21)


def test_la_ronda_borra_los_vistos_de_mas_de_90_dias(conn):
    vid = _crear(conn)
    cur = conn.cursor()
    cur.execute("INSERT INTO vigilancia_vistos (vigilancia_id, anuncio_id, precio, firma, modificado, visto_en) VALUES"
                " (%s,'viejo',100,%s,%s,%s), (%s,'reciente',100,%s,%s,%s)",
                (vid, "0" * 40, AHORA - timedelta(days=100), AHORA - timedelta(days=91),
                 vid, "1" * 40, AHORA - timedelta(days=100), AHORA - timedelta(days=89)))
    conn.commit()
    cur.close()
    _pasada(BotFalso(), conn)
    assert _vistos(conn, vid) == ["reciente"]


# ── Fallos y reintentos ──────────────────────────────────────────────────────────────────────────────────────────────

def test_17_si_el_juez_falla_no_se_envia_ni_se_escribe_y_la_pasada_siguiente_lo_arregla(conn):
    vid = _crear(conn)
    bot = BotFalso()
    fuente = FuenteFalsa(por_defecto=_dos_anuncios())
    _pasada(bot, conn, fuente=fuente, cliente=ClienteFalso(error=RuntimeError("API caída")))
    assert bot.enviados == [] and _vistos(conn, vid) == [] and _fila(conn, vid)["ultima_ronda"] is None
    _pasada(bot, conn, reloj=_a(7, 45), fuente=fuente, cliente=ClienteFalso(elegidos=[{"id": "m4", "semaforo": "COMPRAR", "texto": "bien"}]))
    assert len(bot.enviados) == 1 and "COMPRAR" in bot.enviados[0][1]
    assert _vistos(conn, vid) == ["m2", "m4"] and _fila(conn, vid)["ultima_ronda"] == HOY


def test_17b_una_respuesta_del_juez_sin_la_tool_tambien_se_reintenta(conn):
    vid = _crear(conn)
    bot = BotFalso()
    _pasada(bot, conn, fuente=FuenteFalsa(por_defecto=_dos_anuncios()), cliente=ClienteFalso(sin_tool=True))
    assert bot.enviados == [] and _fila(conn, vid)["ultima_ronda"] is None


def test_18_si_send_message_lanza_no_se_escriben_vistos_ni_ultima_ronda_y_se_reintenta(conn):
    vid = _crear(conn)
    bot = BotFalso(fallos=1)
    fuente, cliente = FuenteFalsa(por_defecto=_dos_anuncios()), ClienteFalso()
    _pasada(bot, conn, fuente=fuente, cliente=cliente)
    assert bot.enviados == [] and _vistos(conn, vid) == [] and _fila(conn, vid)["ultima_ronda"] is None
    _pasada(bot, conn, reloj=_a(7, 45), fuente=fuente, cliente=cliente)
    assert len(bot.enviados) == 1 and _vistos(conn, vid) == ["m2", "m4"] and _fila(conn, vid)["ultima_ronda"] == HOY


def test_19_si_fallan_2_de_8_consultas_la_ronda_sale_y_lo_dice(conn):
    vid = _crear(conn, consultas=[f"consulta {i}" for i in range(8)])
    bot = BotFalso()
    _pasada(bot, conn, fuente=fuente_que_falla(fallan=2))
    (_, texto), = bot.enviados
    assert "2 de 8 búsquedas fallaron" in texto and "Nada nuevo que merezca la pena." in texto
    assert _fila(conn, vid)["ultima_ronda"] == HOY


def test_19b_si_fallan_todas_no_sale_y_queda_para_reintento(conn):
    vid = _crear(conn, consultas=[f"consulta {i}" for i in range(8)])
    bot = BotFalso()
    fuente = fuente_que_falla(fallan=8)
    _pasada(bot, conn, fuente=fuente)
    assert bot.enviados == [] and _fila(conn, vid)["ultima_ronda"] is None and len(fuente.consultas) == 8
    _pasada(bot, conn, reloj=_a(7, 45), fuente=FuenteFalsa())                                         # la fuente vuelve
    assert len(bot.enviados) == 1 and _fila(conn, vid)["ultima_ronda"] == HOY


def test_19c_una_excepcion_que_no_es_fuente_error_cuenta_como_consulta_fallida(conn):
    _crear(conn)
    bot = BotFalso()
    _pasada(bot, conn, fuente=FuenteFalsa(respuestas={"mac mini m4": KeyError("x")}))
    assert "1 de 2 búsquedas fallaron" in bot.enviados[0][1]


# ── La ventana ───────────────────────────────────────────────────────────────────────────────────────────────────────

def test_21_antes_de_la_hora_no_corre_y_cerrada_la_ventana_avisa_una_sola_vez(conn):
    vid = _crear(conn)
    bot, cliente = BotFalso(), ClienteFalso()
    fuente = FuenteFalsa(por_defecto=_dos_anuncios())
    _pasada(bot, conn, reloj=_a(7, 15), fuente=fuente, cliente=cliente)
    assert bot.enviados == [] and fuente.consultas == []
    _pasada(bot, conn, reloj=_a(9, 31), fuente=fuente, cliente=cliente)                               # ventana cerrada, sin ronda hoy
    assert fuente.consultas == [] and cliente.llamadas == []                                         # no corre la ronda
    assert bot.enviados == [(int(USUARIO), "⚠️ Hoy no pude hacer la vigilancia «Mac mini».")]
    assert _fila(conn, vid)["aviso_fallo"] == HOY and _fila(conn, vid)["ultima_ronda"] is None
    _pasada(bot, conn, reloj=_a(9, 46), fuente=fuente, cliente=cliente)
    assert len(bot.enviados) == 1                                                                    # no lo repite


def test_21b_si_el_aviso_no_sale_se_reintenta_en_la_pasada_siguiente(conn):
    vid = _crear(conn)
    bot = BotFalso(fallos=1)
    _pasada(bot, conn, reloj=_a(9, 31))
    assert bot.enviados == [] and _fila(conn, vid)["aviso_fallo"] is None
    _pasada(bot, conn, reloj=_a(9, 46))
    assert len(bot.enviados) == 1 and _fila(conn, vid)["aviso_fallo"] == HOY


def test_21c_un_reinicio_pasado_el_mediodia_no_avisa_de_dias_pasados(conn):
    vid = _crear(conn)
    cur = conn.cursor()
    cur.execute("UPDATE vigilancias SET ultima_ronda = %s, aviso_fallo = NULL WHERE id = %s", (date(2026, 11, 17), vid))   # llevaba 3 días sin ronda
    conn.commit()
    cur.close()
    bot = BotFalso()
    _pasada(bot, conn, reloj=_a(6, 0))                                       # arranca de madrugada: ni ronda ni aviso
    assert bot.enviados == []
    _pasada(bot, conn, reloj=_a(9, 31))
    assert [t for _, t in bot.enviados] == ["⚠️ Hoy no pude hacer la vigilancia «Mac mini»."]         # un aviso, el de hoy


def test_le_toca_en_los_bordes_de_la_ventana():
    v = {"hora": datetime(2026, 1, 1, 7, 30).time(), "ultima_ronda": None, "aviso_fallo": None}
    assert le_toca(v, datetime(2026, 11, 20, 7, 29)) == ""
    assert le_toca(v, datetime(2026, 11, 20, 7, 30)) == "ronda"
    assert le_toca(v, datetime(2026, 11, 20, 9, 29)) == "ronda"
    assert le_toca(v, datetime(2026, 11, 20, 9, 30)) == "aviso"
    assert le_toca({**v, "ultima_ronda": HOY}, datetime(2026, 11, 20, 8, 0)) == ""
    assert le_toca({**v, "aviso_fallo": HOY}, datetime(2026, 11, 20, 12, 0)) == ""
    assert le_toca({**v, "ultima_ronda": date(2026, 11, 19)}, datetime(2026, 11, 20, 8, 0)) == "ronda"


def test_22_una_vigilancia_inactiva_no_corre(conn):
    vid = _crear(conn, activa=False)
    bot = BotFalso()
    fuente = FuenteFalsa(por_defecto=_dos_anuncios())
    _pasada(bot, conn, fuente=fuente)
    _pasada(bot, conn, reloj=_a(9, 31), fuente=fuente)
    assert bot.enviados == [] and fuente.consultas == [] and _fila(conn, vid)["ultima_ronda"] is None


def test_solo_corren_las_vigilancias_de_los_usuarios_autorizados(conn):
    _crear(conn, usuario=OTRO)
    bot = BotFalso()
    _pasada(bot, conn)                                                       # `_pasada` solo avisa a USUARIO
    assert bot.enviados == []


def test_una_vigilancia_rota_no_frena_a_las_demas(conn):
    from modules.vigilancias import ronda
    rota = _crear(conn, nombre="Rota")
    buena = _crear(conn, nombre="Buena")
    real = ronda._hacer_ronda

    def _una_explota(conn_, v, *args, **kwargs):
        if v["id"] == rota:
            raise RuntimeError("fallo inesperado ZZTITULO")
        return real(conn_, v, *args, **kwargs)

    bot = BotFalso()
    with patch.object(ronda, "_hacer_ronda", _una_explota), patch("modules.vigilancias.ronda.logger") as log:
        _pasada(bot, conn)
    assert len(bot.enviados) == 1 and _fila(conn, buena)["ultima_ronda"] == HOY and _fila(conn, rota)["ultima_ronda"] is None
    volcado = " ".join(str(c) for c in log.mock_calls)
    assert "RuntimeError" in volcado and "ZZTITULO" not in volcado


# ── Mensaje ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def _grandes(n):
    return [hacer_anuncio(id=f"g{i}", titulo=f"Mac mini grande {i}", ciudad="Valencia") for i in range(n)]


def test_el_mensaje_pasado_de_4000_caracteres_se_recorta_por_anuncios_enteros():
    anuncios = [hacer_anuncio(id=f"g{i}", titulo=f"Mac mini grande {i}" + "x" * 100, ciudad="V" * 300) for i in range(6)]   # un bloque ≈ 900
    informe = Informe(elegidos=[{"id": a.id, "semaforo": "MIRAR", "texto": "t" * 390} for a in anuncios], cierre="Mejor de esta ronda: g0.")
    texto = armar_mensaje({"nombre": "Mac mini"}, AHORA, informe, anuncios, fallidas=2, total=8)
    assert len(texto) <= 4000
    assert texto.count("🟡 MIRAR") < 6 and texto.count("🟡 MIRAR") >= 3
    assert all(f"/item/g{i}-slug" in texto for i in range(texto.count("🟡 MIRAR")))                    # los que salen, enteros (con su enlace)
    assert texto.endswith("(2 de 8 búsquedas fallaron)") and "Mejor de esta ronda: g0." in texto


def test_el_mensaje_ordena_por_lo_que_dice_el_juez_y_usa_una_marca_por_semaforo():
    a, b, c = _grandes(3)
    informe = Informe(elegidos=[{"id": b.id, "semaforo": "DUDOSO", "texto": "raro"}, {"id": a.id, "semaforo": "COMPRAR", "texto": "bien"}],
                      cierre="Ninguno urgente.")
    texto = armar_mensaje({"nombre": "Mac mini"}, AHORA, informe, [a, b, c], 0, 2)
    assert texto.index("🟠 DUDOSO") < texto.index("🟢 COMPRAR") and "búsquedas fallaron" not in texto
    assert "grande 2" not in texto


def test_r1_los_candidatos_fuera_del_tope_de_40_no_se_guardan_como_vistos_y_vuelven_al_dia_siguiente(conn):
    """H1-revision R1: con 42 candidatos al juez llegan los 40 más recientes; los 2 más antiguos no quedan en `vistos`
    (un nuevo que solo el filtro descartó, sí)."""
    vid = _crear(conn, filtros={"precio_min": 300, "precio_max": 2000, "excluir": []})
    candidatos = [hacer_anuncio(id=f"t{i:02d}", titulo=f"Mac mini M4 variante {i}", modificado=AHORA - timedelta(hours=1, minutes=i))
                  for i in range(42)]                                                             # t00 el más reciente, t41 el más antiguo
    barato = hacer_anuncio(id="barato", titulo="Cable para Mac mini", precio="40", modificado=AHORA - timedelta(hours=1))
    fuente = FuenteFalsa(por_defecto=candidatos + [barato])
    cliente = ClienteFalso()
    _pasada(BotFalso(), conn, fuente=fuente, cliente=cliente)
    contenido = cliente.llamadas[0]["messages"][0]["content"]
    assert contenido.count('"id"') == 40 and '"id": "t00"' in contenido and '"id": "t39"' in contenido
    assert '"id": "t40"' not in contenido and '"id": "t41"' not in contenido
    vistos = _vistos(conn, vid)
    assert "t40" not in vistos and "t41" not in vistos and "barato" in vistos and len(vistos) == 41
    assert _fila(conn, vid)["ultima_ronda"] == HOY

    cliente_manana = ClienteFalso()                                                              # al día siguiente, siguen dentro de las 48 h
    _pasada(BotFalso(), conn, reloj=lambda: datetime(2026, 11, 21, 7, 30), fuente=fuente, cliente=cliente_manana)
    contenido = cliente_manana.llamadas[0]["messages"][0]["content"]
    assert contenido.count('"id"') == 2 and '"id": "t40"' in contenido and '"id": "t41"' in contenido


def test_el_precio_con_decimales_se_escribe_a_la_espanola():
    a = hacer_anuncio(id="p", precio="749.5")
    informe = Informe(elegidos=[{"id": "p", "semaforo": "MIRAR", "texto": "ok"}], cierre="x")
    assert "749,50 €" in armar_mensaje({"nombre": "n"}, AHORA, informe, [a], 0, 1)


# ── Logs ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_24_ni_las_consultas_ni_las_reglas_ni_titulos_ni_descripciones_van_a_ningun_log(conn):
    marcada = _crear(conn, consultas=["ZZCONSULTA uno", "ZZCONSULTA dos"], reglas="ZZREGLA: busca un Mac mini")
    anuncio = hacer_anuncio(id="z1", titulo="ZZTITULO Mac mini M4", descripcion="ZZTITULO descripción larga", precio="900")
    eleg = [{"id": "z1", "semaforo": "COMPRAR", "texto": "ok"}]
    with patch("modules.vigilancias.ronda.logger") as l_ronda, patch("modules.vigilancias.juez.logger") as l_juez:
        # 1) ronda buena; 2) el juez falla con el texto en la excepción; 3) el envío falla con el texto en la excepción;
        # 4) las consultas fallan con la consulta en la excepción; 5) la ventana se cierra
        _pasada(BotFalso(), conn, fuente=FuenteFalsa(por_defecto=[anuncio]), cliente=ClienteFalso(elegidos=eleg))
        for texto in ("juez", "envio", "consultas"):
            cur = conn.cursor()
            cur.execute("UPDATE vigilancias SET ultima_ronda = NULL, aviso_fallo = NULL WHERE id = %s", (marcada,))
            cur.execute("DELETE FROM vigilancia_vistos WHERE vigilancia_id = %s", (marcada,))
            conn.commit()
            cur.close()
            if texto == "juez":
                _pasada(BotFalso(), conn, fuente=FuenteFalsa(por_defecto=[anuncio]), cliente=ClienteFalso(error=RuntimeError("ZZREGLA ZZTITULO ZZCONSULTA")))
            elif texto == "envio":
                _pasada(BotFalso(fallos=1), conn, fuente=FuenteFalsa(por_defecto=[anuncio]), cliente=ClienteFalso(elegidos=eleg))
            else:
                _pasada(BotFalso(), conn, fuente=FuenteFalsa(respuestas={"ZZCONSULTA uno": RuntimeError("ZZCONSULTA"), "ZZCONSULTA dos": FuenteError("ZZCONSULTA")}))
        _pasada(BotFalso(), conn, reloj=_a(9, 31))
    volcado = " ".join(str(c) for c in l_ronda.mock_calls + l_juez.mock_calls)
    assert volcado, "las rondas tienen que dejar log"
    assert not any(marca in volcado for marca in ("ZZCONSULTA", "ZZREGLA", "ZZTITULO"))
    assert "Vigilancia id=" in volcado and f"user={USUARIO}" in volcado and "consultas_ok=" in volcado and "coste_usd=" in volcado


def test_24b_el_log_de_la_ronda_lleva_resultado_y_cifras(conn):
    vid = _crear(conn)
    with patch("modules.vigilancias.ronda.logger") as log:
        _pasada(BotFalso(), conn, fuente=FuenteFalsa(por_defecto=_dos_anuncios()),
                cliente=ClienteFalso(elegidos=[{"id": "m4", "semaforo": "COMPRAR", "texto": "ok"}], tokens_in=8000, tokens_out=500))
    linea = next(str(c) for c in log.info.mock_calls if "resultado=enviada" in str(c))
    for esperado in (f"id={vid}", f"user={USUARIO}", "consultas_ok=2/2", "anuncios=4", "nuevos=2", "candidatos=2", "elegidos=1",
                     "tokens_in=8000", "tokens_out=500", "coste_usd=0.0105"):
        assert esperado in linea, esperado


# ── El planificador ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_23_y_25_registrar_jobs_deja_la_tarea_de_vigilancias_y_las_que_ya_existian():
    s = BackgroundScheduler()
    _registrar_jobs(s, BotFalso(), {"authorized_ids": [111], "calendar": {"daily_reminder_time": "08:30"}})
    jobs = {j.id: j for j in s.get_jobs()}
    assert {"daily_calendar_reminder", "avisos_compromisos", "avisos_compromisos_arranque", "cleanup_conversations",
            "vigilancias", "vigilancias_arranque"} == set(jobs)
    v = jobs["vigilancias"]
    assert v.trigger.interval.total_seconds() == 15 * 60
    assert v.max_instances == 1 and v.coalesce is True                       # una pasada colgada en un `send_message` no se solapa consigo misma
    assert jobs["vigilancias_arranque"].max_instances == 1 and jobs["vigilancias_arranque"].trigger.__class__.__name__ == "DateTrigger"
    assert v.args[1] == [111]
    # lo que ya había, igual que antes
    assert jobs["avisos_compromisos"].trigger.interval.total_seconds() == 60 and jobs["avisos_compromisos"].max_instances == 1
    assert str(jobs["daily_calendar_reminder"].trigger) == "cron[hour='8', minute='30']"
    assert jobs["avisos_compromisos_arranque"].kwargs["arranque"] is True

