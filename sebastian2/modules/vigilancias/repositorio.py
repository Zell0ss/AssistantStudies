# modules/vigilancias/repositorio.py
"""Las vigilancias en la BD (plan §2.1): validación con los límites del plan y guardado. Lo usan la ronda, el script de carga
y, en H2, las tools. Nada de esto va al log con texto de consultas o reglas (D42)."""
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from modules.vigilancias.filtro import firma, precio_2
from modules.vigilancias.fuentes import FUENTES

MAX_ACTIVAS = 5
MAX_CONSULTAS = 10
LARGO_CONSULTA = (2, 80)
MAX_REGLAS = 4000
MAX_NOMBRE = 100
VENTANA = timedelta(hours=2)        # D67: la ronda de cada día se hace entre `hora` y `hora + 2 h` (la usa `ronda.py`)


class VigilanciaInvalida(ValueError):
    """Los datos de una vigilancia no cumplen los límites del plan §2.1."""


def _hora(valor) -> time:
    if isinstance(valor, time):
        return valor.replace(second=0, microsecond=0)
    if isinstance(valor, timedelta):                       # así devuelve pymysql una columna TIME
        return (datetime.min + valor).time().replace(second=0, microsecond=0)
    try:
        h, m = str(valor).strip().split(":")[:2]
        return time(int(h), int(m))
    except (ValueError, TypeError):
        raise VigilanciaInvalida("hora: tiene que ser HH:MM") from None


def _precio(valor, campo: str) -> Optional[float]:
    if valor is None:
        return None
    try:
        numero = Decimal(str(valor))
    except InvalidOperation:
        raise VigilanciaInvalida(f"filtros.{campo}: tiene que ser un número o null") from None
    if isinstance(valor, bool) or not numero.is_finite() or numero < 0:
        raise VigilanciaInvalida(f"filtros.{campo}: tiene que ser un número no negativo o null")
    return float(numero)


def validar(datos: dict) -> dict:
    """Devuelve los datos normalizados (`nombre`, `fuente`, `consultas`, `filtros`, `reglas`, `hora`, `activa`) o lanza
    `VigilanciaInvalida`. Los mensajes dicen qué campo falla y nunca repiten el texto de las consultas ni de las reglas."""
    if not isinstance(datos, dict):
        raise VigilanciaInvalida("una vigilancia tiene que ser un mapa de campos")
    nombre = str(datos.get("nombre") or "").strip()
    if not 1 <= len(nombre) <= MAX_NOMBRE:
        raise VigilanciaInvalida(f"nombre: de 1 a {MAX_NOMBRE} caracteres")
    fuente = str(datos.get("fuente") or "").strip()
    if fuente not in FUENTES:
        raise VigilanciaInvalida(f"fuente: tiene que ser una de {sorted(FUENTES)}")

    consultas = datos.get("consultas")
    if not isinstance(consultas, list) or not 1 <= len(consultas) <= MAX_CONSULTAS:
        raise VigilanciaInvalida(f"consultas: una lista de 1 a {MAX_CONSULTAS}")
    limpias = []
    for c in consultas:
        c = c.strip() if isinstance(c, str) else None
        if c is None or not LARGO_CONSULTA[0] <= len(c) <= LARGO_CONSULTA[1]:
            raise VigilanciaInvalida(f"consultas: cada una es texto de {LARGO_CONSULTA[0]} a {LARGO_CONSULTA[1]} caracteres")
        limpias.append(c)

    filtros = datos.get("filtros") or {}
    if not isinstance(filtros, dict):
        raise VigilanciaInvalida("filtros: tiene que ser un mapa")
    excluir = filtros.get("excluir") or []
    if not isinstance(excluir, list) or not all(isinstance(x, str) for x in excluir):
        raise VigilanciaInvalida("filtros.excluir: una lista de textos")
    minimo, maximo = _precio(filtros.get("precio_min"), "precio_min"), _precio(filtros.get("precio_max"), "precio_max")
    if minimo is not None and maximo is not None and minimo > maximo:
        raise VigilanciaInvalida("filtros: precio_min no puede ser mayor que precio_max")

    reglas = str(datos.get("reglas") or "").strip()
    if not 1 <= len(reglas) <= MAX_REGLAS:
        raise VigilanciaInvalida(f"reglas: de 1 a {MAX_REGLAS} caracteres")
    activa = datos.get("activa", True)
    if not isinstance(activa, bool):
        raise VigilanciaInvalida("activa: verdadero o falso")
    return {
        "nombre": nombre, "fuente": fuente, "consultas": limpias, "reglas": reglas, "hora": _hora(datos.get("hora")),
        "filtros": {"precio_min": minimo, "precio_max": maximo, "excluir": [x.strip() for x in excluir if x.strip()]},
        "activa": activa,
    }


def _cursor(conn):
    return conn.cursor()


def contar_activas(conn, user_id: str, salvo_nombre: Optional[str] = None) -> int:
    cur = _cursor(conn)
    cur.execute("SELECT COUNT(*) AS n FROM vigilancias WHERE user_id = %s AND activa = 1 AND nombre <> %s",
                (user_id, salvo_nombre or ""))
    n = cur.fetchone()["n"]
    cur.close()
    return n


def guardar(conn, user_id: str, datos: dict, ahora: Optional[datetime] = None, confirmar: bool = True) -> dict:
    """Upsert por `(user_id, nombre)`: crea la vigilancia o actualiza la que tenga ese nombre, sin tocar `ultima_ronda`. Valida
    antes de escribir y comprueba el tope de 5 activas por usuario. Devuelve {id, creada, nombre}.

    Guarda de D67 (H1-revision §5, R5): si la vigilancia queda activa con su ventana de hoy ya cerrada y sin ronda hoy, pone
    `aviso_fallo = hoy`. La vigilancia no existía (o no era esta) durante su ventana, así que «hoy no pude hacerla» sería un aviso
    falso. Dentro de la ventana no toca nada: la ronda sale en la pasada siguiente. Fuera de eso, `aviso_fallo` no se toca."""
    v = validar(datos)
    if v["activa"] and contar_activas(conn, str(user_id), v["nombre"]) >= MAX_ACTIVAS:
        raise VigilanciaInvalida(f"como mucho {MAX_ACTIVAS} vigilancias activas por usuario")
    ahora = ahora or datetime.now()
    cur = _cursor(conn)
    cur.execute("SELECT id, ultima_ronda FROM vigilancias WHERE user_id = %s AND nombre = %s", (str(user_id), v["nombre"]))
    fila = cur.fetchone()
    columnas = (v["fuente"], json.dumps(v["consultas"], ensure_ascii=False), json.dumps(v["filtros"], ensure_ascii=False),
                v["reglas"], v["hora"], v["activa"])
    if fila:
        cur.execute("UPDATE vigilancias SET fuente=%s, consultas=%s, filtros=%s, reglas=%s, hora=%s, activa=%s, updated_at=%s"
                    " WHERE id=%s", (*columnas, ahora, fila["id"]))
        id_, creada = fila["id"], False
    else:
        cur.execute("INSERT INTO vigilancias (user_id, nombre, fuente, consultas, filtros, reglas, hora, activa, created_at, updated_at)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (str(user_id), v["nombre"], *columnas, ahora, ahora))
        id_, creada = cur.lastrowid, True
    ultima_ronda = fila["ultima_ronda"] if fila else None
    ventana_cerrada = ahora >= datetime.combine(ahora.date(), v["hora"]) + VENTANA
    if v["activa"] and ventana_cerrada and ultima_ronda != ahora.date():
        cur.execute("UPDATE vigilancias SET aviso_fallo = %s WHERE id = %s", (ahora.date(), id_))
    cur.close()
    if confirmar:
        conn.commit()
    return {"id": id_, "creada": creada, "nombre": v["nombre"]}


def _de_fila(f: dict) -> dict:
    return {**f, "consultas": json.loads(f["consultas"]), "filtros": json.loads(f["filtros"]), "hora": _hora(f["hora"]),
            "activa": bool(f["activa"])}


def listar_activas(conn, user_ids: Optional[list] = None) -> list:
    """Las vigilancias activas, con sus JSON ya cargados y `hora` como `time`. Si `user_ids`, solo las de esos usuarios."""
    cur = _cursor(conn)
    cur.execute("SELECT * FROM vigilancias WHERE activa = 1 ORDER BY id")
    filas = [_de_fila(f) for f in cur.fetchall()]
    cur.close()
    if user_ids is not None:
        permitidos = {str(u) for u in user_ids}
        filas = [f for f in filas if f["user_id"] in permitidos]
    return filas


def vistos_de(conn, vigilancia_id: int, anuncio_ids: list) -> dict:
    """`{anuncio_id: {precio, firma, modificado}}` de los ids pedidos que ya se vieron en esa vigilancia."""
    if not anuncio_ids:
        return {}
    cur = _cursor(conn)
    cur.execute("SELECT anuncio_id, precio, firma, modificado FROM vigilancia_vistos WHERE vigilancia_id = %s"
                f" AND anuncio_id IN ({','.join(['%s'] * len(anuncio_ids))})", (vigilancia_id, *anuncio_ids))
    vistos = {f["anuncio_id"]: f for f in cur.fetchall()}
    cur.close()
    return vistos


def marcar_vistos(conn, vigilancia_id: int, anuncios: list, ahora: datetime) -> None:
    """Guarda (o actualiza) como vistos estos anuncios. No confirma: lo hace quien llama junto con `ultima_ronda`."""
    cur = _cursor(conn)
    for a in anuncios:
        cur.execute(
            "INSERT INTO vigilancia_vistos (vigilancia_id, anuncio_id, precio, firma, modificado, visto_en)"
            " VALUES (%s,%s,%s,%s,%s,%s)"
            " ON DUPLICATE KEY UPDATE precio=VALUES(precio), firma=VALUES(firma), modificado=VALUES(modificado), visto_en=VALUES(visto_en)",
            (vigilancia_id, a.id, precio_2(a.precio), firma(a), a.modificado, ahora))
    cur.close()
