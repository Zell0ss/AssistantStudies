# modules/vigilancias/ronda.py
"""La ronda diaria de las vigilancias (D63, D65, D66, D67, plan §2.6).

Una tarea cada 15 min (`bot/scheduler.py`) llama a `pasada_vigilancias`. A cada vigilancia le toca una ronda al día, en la
ventana `[hora, hora + 2 h)`, y es idempotente con el patrón de D48/D51: lo que se escribe en la BD (los vistos y `ultima_ronda`)
se escribe DESPUÉS de enviar el mensaje, y todo junto. Si algo falla antes (todas las consultas, el juez, el envío) no se escribe
nada y la pasada siguiente lo reintenta, hasta que se cierra la ventana: entonces se avisa una vez.

La ronda es de solo lectura: no llama al orquestador y el juez no tiene tools. El mensaje lo escribe el código con los datos
del anuncio; del juez solo salen el semáforo, el texto de apoyo y el id del mejor (D66); la frase del cierre también la escribe el código.

Los logs llevan id, usuario y recuentos, nunca consultas, reglas, títulos ni texto de anuncios (D42); las excepciones, solo su clase.
"""
from datetime import datetime, timedelta
from typing import Optional

from db.connection import init_pool
from logcentral_client import get_logger
from modules.vigilancias import repositorio
from modules.vigilancias.anuncio import FuenteError
from modules.vigilancias.filtro import seleccionar
from modules.vigilancias.fuentes import FUENTES
from modules.vigilancias.juez import MODELO_JUEZ, Informe, JuezError, juzgar

logger = get_logger("sebastian")

VENTANA = timedelta(hours=2)
MAX_CANDIDATOS = 40
RETENCION_VISTOS = timedelta(days=90)
MAX_MENSAJE = 4000
_MARCA = {"COMPRAR": "🟢", "MIRAR": "🟡", "DUDOSO": "🟠"}
_NADA = "Nada nuevo que merezca la pena."


# ── Mensaje ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def _precio(p) -> str:
    if p is None:
        return "sin precio"
    return f"{p:.0f} €" if p == p.to_integral_value() else f"{p:.2f}".replace(".", ",") + " €"


def _bloque(elegido: dict, anuncio) -> str:
    """Título, precio, ciudad y enlace salen del anuncio; del juez, solo el semáforo y el texto (D66)."""
    cabecera = f"{_MARCA[elegido['semaforo']]} {elegido['semaforo']} · {anuncio.titulo.strip()[:120]} · {_precio(anuncio.precio)}"
    if anuncio.ciudad:
        cabecera += f" · {anuncio.ciudad}"
    return f"{cabecera}\n{elegido['texto']}\n{anuncio.url}"


def _cierre(informe: Informe, por_id: dict) -> str:
    """El cierre lo escribe el código (D66, H1-revision R4): el juez solo dice el id del mejor, y el título y el precio salen de
    su anuncio. Sin `mejor_id` válido (entre los elegidos), «Ninguno urgente.»."""
    mejor = por_id.get(informe.mejor_id) if informe.mejor_id in {e["id"] for e in informe.elegidos} else None
    if mejor is None:
        return "Ninguno urgente."
    return f"Mejor de esta ronda: {mejor.titulo.strip()[:120]} · {_precio(mejor.precio)}"


def armar_mensaje(vigilancia: dict, ahora: datetime, informe: Informe, candidatos: list, fallidas: int, total: int) -> str:
    """El mensaje de la ronda, en texto plano. Pasado de 4000 caracteres, se recorta por anuncios enteros."""
    por_id = {a.id: a for a in candidatos}
    cabecera = f"🔎 {vigilancia['nombre']} · {ahora:%d/%m}"
    pie = ""
    if fallidas:
        pie = f"({fallidas} de {total} búsquedas fallaron)"
    bloques = [_bloque(e, por_id[e["id"]]) for e in informe.elegidos if e["id"] in por_id]
    if not bloques:
        return "\n".join(x for x in (cabecera, _NADA, pie) if x)

    cierre = _cierre(informe, por_id)

    def montar(n: int) -> str:
        partes = [cabecera, "\n\n".join(bloques[:n]), cierre]
        if pie:
            partes.append(pie)
        return "\n\n".join(partes)

    n = len(bloques)
    while n > 1 and len(montar(n)) > MAX_MENSAJE:
        n -= 1
    return montar(n)


# ── Una ronda ────────────────────────────────────────────────────────────────────────────────────────────────────────

def _cliente(config: Optional[dict]):
    from anthropic import Anthropic
    return Anthropic(api_key=config["anthropic_apikey"], timeout=60.0)


def _log(v: dict, resultado: str, nivel: str = "info", **cifras):
    detalle = " ".join(f"{k}={val}" for k, val in cifras.items())
    getattr(logger, nivel)(f"Vigilancia id={v['id']} user={v['user_id']} resultado={resultado} {detalle}".rstrip())


def _hacer_ronda(conn, v: dict, ahora: datetime, bot, fuentes: dict, cliente, config, modelo: str) -> str:
    """La ronda de una vigilancia dentro de su ventana. Devuelve el resultado (el del log)."""
    fuente = fuentes.get(v["fuente"])
    consultas = v["consultas"]
    anuncios, fallidas = [], 0
    for consulta in consultas:
        try:
            if fuente is None:
                raise FuenteError("fuente desconocida")
            anuncios += fuente.buscar(consulta)
        except Exception as e:                                                  # el texto de la excepción puede llevar la consulta
            fallidas += 1
            logger.warning(f"Vigilancia id={v['id']} consulta fallida: {type(e).__name__}")
    ok = len(consultas) - fallidas
    cifras = {"consultas_ok": f"{ok}/{len(consultas)}"}
    if ok == 0:
        _log(v, "reintento(consultas)", "error", **cifras)
        return "reintento(consultas)"

    vistos = repositorio.vistos_de(conn, v["id"], sorted({a.id for a in anuncios}))
    seleccion = seleccionar(anuncios, vistos, v["filtros"], ahora)
    candidatos = seleccion.candidatos
    sin_juzgar = set()                                  # D65 (H1-revision R1): los que el tope deja fuera NO se guardan como vistos
    if len(candidatos) > MAX_CANDIDATOS:
        logger.warning(f"Vigilancia id={v['id']} candidatos={len(candidatos)}: solo los {MAX_CANDIDATOS} más recientes van al juez")
        sin_juzgar = {a.id for a in candidatos[MAX_CANDIDATOS:]}
        candidatos = candidatos[:MAX_CANDIDATOS]
    cifras |= {"anuncios": len(anuncios), "nuevos": len(seleccion.nuevos), "candidatos": len(candidatos)}

    informe = Informe(modelo=modelo)
    if candidatos:
        try:
            informe = juzgar(cliente or _cliente(config), v["reglas"], candidatos, modelo)
        except JuezError as e:                                                  # JuezError ya viene sin texto de terceros
            _log(v, "reintento(juez)", "error", **cifras)
            logger.error(f"Vigilancia id={v['id']} fallo del juez: {e}")
            return "reintento(juez)"
        except Exception as e:                                                  # p. ej. no hay clave en la config
            _log(v, "reintento(juez)", "error", **cifras)
            logger.error(f"Vigilancia id={v['id']} fallo del juez: {type(e).__name__}")
            return "reintento(juez)"
    cifras |= {"elegidos": len(informe.elegidos), "tokens_in": informe.tokens_in, "tokens_out": informe.tokens_out,
               "coste_usd": f"{informe.coste_usd:.4f}"}

    mensaje = armar_mensaje(v, ahora, informe, candidatos, fallidas, len(consultas))
    try:
        bot.send_message(chat_id=int(v["user_id"]), text=mensaje)
    except Exception as e:
        _log(v, f"reintento(envio:{type(e).__name__})", "error", **cifras)
        return "reintento(envio)"

    # Solo con el envío hecho: los vistos (también los que el filtro o el juez descartaron, pero no los que el tope de
    # candidatos dejó sin juzgar: vuelven mañana si siguen dentro de las 48 h) y `ultima_ronda`, juntos.
    try:
        repositorio.marcar_vistos(conn, v["id"], [a for a in seleccion.nuevos if a.id not in sin_juzgar], ahora)
        cur = conn.cursor()
        cur.execute("UPDATE vigilancias SET ultima_ronda = %s WHERE id = %s", (ahora.date(), v["id"]))
        cur.execute("DELETE FROM vigilancia_vistos WHERE vigilancia_id = %s AND visto_en < %s",
                    (v["id"], ahora - RETENCION_VISTOS))
        cur.close()
        conn.commit()
    except Exception as e:
        conn.rollback()
        # El mensaje ya salió: la pasada siguiente lo repetiría. Se deja dicho en el log para que se vea.
        _log(v, f"enviada_sin_registrar({type(e).__name__})", "error", **cifras)
        return "enviada_sin_registrar"
    resultado = "enviada" if informe.elegidos else "sin_novedad"
    _log(v, resultado, **cifras)
    return resultado


def _avisar_fallo(conn, v: dict, ahora: datetime, bot) -> str:
    """Cerrada la ventana sin ronda: un aviso, una sola vez al día (`aviso_fallo`)."""
    try:
        bot.send_message(chat_id=int(v["user_id"]), text=f"⚠️ Hoy no pude hacer la vigilancia «{v['nombre']}».")
    except Exception as e:
        _log(v, f"reintento(aviso:{type(e).__name__})", "error")
        return "reintento(aviso)"
    cur = conn.cursor()
    cur.execute("UPDATE vigilancias SET aviso_fallo = %s WHERE id = %s", (ahora.date(), v["id"]))
    cur.close()
    conn.commit()
    _log(v, "aviso_fallo", "warning")
    return "aviso_fallo"


def le_toca(v: dict, ahora: datetime) -> str:
    """'ronda' dentro de la ventana, 'aviso' si ya se cerró sin ronda ni aviso hoy, o '' si no hay nada que hacer.
    Una hora de salida pasadas las 22:00 deja una ventana más corta: acaba a medianoche, y al día siguiente ya es otro día."""
    hoy = ahora.date()
    if v["ultima_ronda"] == hoy:
        return ""
    inicio = datetime.combine(hoy, v["hora"])
    if ahora < inicio:
        return ""
    if ahora < inicio + VENTANA:
        return "ronda"
    return "" if v["aviso_fallo"] == hoy else "aviso"


def pasada_vigilancias(bot, user_ids: list, reloj=None, fuentes: Optional[dict] = None, cliente=None, conn=None,
                       config: Optional[dict] = None, modelo: str = MODELO_JUEZ) -> None:
    """La tarea de cada 15 min. Recorre las vigilancias activas de `user_ids` y hace la ronda (o el aviso) que toque.

    Inyectables para las pruebas: `reloj`, `fuentes`, `cliente` (Anthropic), `bot` y `conn`. Sin `conn`, usa una conexión
    propia del pool (como `enviar_avisos`): el singleton de `get_connection()` es del hilo de los manejadores de Telegram."""
    ahora = (reloj or datetime.now)().replace(second=0, microsecond=0)
    fuentes = FUENTES if fuentes is None else fuentes
    propia = conn is None
    conn = conn or init_pool().connection()
    try:
        for v in repositorio.listar_activas(conn, user_ids):
            try:
                accion = le_toca(v, ahora)
                if accion == "ronda":
                    _hacer_ronda(conn, v, ahora, bot, fuentes, cliente, config, modelo)
                elif accion == "aviso":
                    _avisar_fallo(conn, v, ahora, bot)
            except Exception as e:                                              # una vigilancia rota no frena a las demás
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.error(f"Vigilancia id={v['id']} user={v['user_id']} error inesperado: {type(e).__name__}")
    finally:
        if propia:
            conn.close()
