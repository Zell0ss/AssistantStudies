# modules/compromisos.py
"""
Compromisos (fase 3, H1; D45, D50, D51): cosas que el usuario tiene que hacer, con día, hora o intervalo de días.

Dos formas, y exactamente una (plan §2.1; lo comprueba `validar_forma`, no la BD):
  a) suelto:  `fecha_inicio` [, `fecha_fin`] [, `hora`]
  b) atado a un evento del calendario (D50): `dias_inicio` [, `dias_fin`] [, `hora`]  ó  `minutos`
Un compromiso atado NO guarda fecha, solo un desfase: el momento se calcula al leerlo desde `events`, así que si el
evento se mueve, sus compromisos se mueven solos. Todo es hora local (naive), igual que `events`: los días se suman
como fechas del calendario, no como 24 h, para que el cambio de hora no desplace una toma.

Los registros de salud no se guardan aquí (D52): este módulo no sabe de qué va un texto.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from logcentral_client import get_logger
from modules.base import BaseModule

logger = get_logger("sebastian")

MAX_ITEMS = 20
MAX_TEXTO = 500
_DIAS_DEFECTO = 14                    # `listar` sin ventana: de hoy a 14 días
_MOTIVOS = ("olvidar", "cancelar")
_DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_CAMPOS_SUELTO = ("fecha_inicio", "fecha_fin")
_CAMPOS_ATADO = ("dias_inicio", "dias_fin", "minutos")


class FormaInvalida(ValueError):
    """El compromiso no cumple las reglas de forma del plan §2.1. El mensaje está escrito para Alfred."""


@dataclass(frozen=True)
class Momento:
    """El momento efectivo de un compromiso. `cuando` solo existe si hay hora; un intervalo no la lleva."""
    fecha_inicio: Optional[date]
    fecha_fin: Optional[date]
    hora: Optional[time] = None
    cuando: Optional[datetime] = None
    problema: Optional[str] = None


# ── Forma ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def _presente(item: dict, campo: str) -> bool:
    return item.get(campo) is not None


def _fecha(valor, campo: str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise FormaInvalida(f"{campo}: «{valor}» no es una fecha YYYY-MM-DD") from None


def _hora(valor, campo: str = "hora") -> time:
    if isinstance(valor, time):
        return valor.replace(second=0, microsecond=0)
    if isinstance(valor, timedelta):                         # PyMySQL devuelve TIME como timedelta
        segundos = int(valor.total_seconds())
        return time(segundos // 3600, (segundos % 3600) // 60)
    try:
        return datetime.strptime(str(valor), "%H:%M").time()
    except ValueError:
        raise FormaInvalida(f"{campo}: «{valor}» no es una hora HH:MM (24 h)") from None


def _entero(item: dict, campo: str, limite: int) -> Optional[int]:
    valor = item.get(campo)
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise FormaInvalida(f"{campo}: tiene que ser un número entero")
    if abs(valor) > limite:
        raise FormaInvalida(f"{campo}: {valor} se sale de lo razonable")
    return valor


def validar_forma(item: Dict[str, Any]) -> None:
    """Las reglas de forma del plan §2.1. Lanza `FormaInvalida`; no mira la BD (eso lo hace `crear`)."""
    texto = (item.get("texto") or "").strip()
    if not texto:
        raise FormaInvalida("texto: falta el texto del compromiso")
    if len(texto) > MAX_TEXTO:
        raise FormaInvalida(f"texto: pasa de {MAX_TEXTO} caracteres")

    hora = _hora(item["hora"]) if _presente(item, "hora") else None
    atado = _presente(item, "evento_id")
    fi = _fecha(item["fecha_inicio"], "fecha_inicio") if _presente(item, "fecha_inicio") else None
    ff = _fecha(item["fecha_fin"], "fecha_fin") if _presente(item, "fecha_fin") else None
    di = _entero(item, "dias_inicio", 3650)
    df = _entero(item, "dias_fin", 3650)
    minutos = _entero(item, "minutos", 525600)

    if not atado:
        if any(v is not None for v in (di, df, minutos)):
            raise FormaInvalida("un desfase (dias_inicio, dias_fin, minutos) solo vale con evento_id; "
                                "sin evento usa fecha_inicio")
        if fi is None:
            raise FormaInvalida("un compromiso suelto necesita fecha_inicio")
        if ff is not None and ff < fi:
            raise FormaInvalida("fecha_fin no puede ser anterior a fecha_inicio")
        if ff is not None and hora is not None:
            raise FormaInvalida("un intervalo de días no lleva hora")
        return

    if fi is not None or ff is not None:
        raise FormaInvalida("un compromiso atado a un evento no lleva fechas: usa dias_inicio o minutos")
    if di is not None and minutos is not None:
        raise FormaInvalida("usa dias_inicio o minutos, no los dos")
    if di is None and minutos is None:
        raise FormaInvalida("un compromiso atado necesita dias_inicio o minutos")
    if minutos is not None:
        if hora is not None:
            raise FormaInvalida("minutos ya fija la hora (relativa al evento): no se combina con hora")
        if df is not None:
            raise FormaInvalida("dias_fin no va con minutos")
        return
    if df is not None:
        if df < di:
            raise FormaInvalida("dias_fin no puede ser anterior a dias_inicio")
        if hora is not None:
            raise FormaInvalida("un intervalo de días no lleva hora")


# ── Momento efectivo ────────────────────────────────────────────────────────────────────────────────────────────────

def _dia_del_evento(evento: dict) -> Optional[date]:
    inicio = evento.get("start_datetime")
    if inicio is not None:
        return inicio.date()
    return evento.get("event_date")


def momento_efectivo(fila: dict, evento: Optional[dict]) -> Momento:
    """El momento de un compromiso (plan §2.1). `fila` es la fila de `compromisos`; `evento`, la de `events` o None."""
    hora = _hora(fila["hora"]) if fila.get("hora") is not None else None

    if fila.get("evento_id") is None:                                     # suelto: lo que dice la fila
        fi = _fecha(fila["fecha_inicio"], "fecha_inicio")
        ff = _fecha(fila["fecha_fin"], "fecha_fin") if fila.get("fecha_fin") is not None else fi
        return Momento(fi, ff, hora, datetime.combine(fi, hora) if hora and ff == fi else None)

    if evento is None:
        return Momento(None, None, problema="el evento ya no existe")

    if fila.get("minutos") is not None:                                   # atado a la hora del evento
        inicio = evento.get("start_datetime")
        if inicio is None:
            return Momento(None, None, problema="el evento ya no tiene hora, y este paso es relativo a ella")
        cuando = inicio + timedelta(minutes=fila["minutos"])
        return Momento(cuando.date(), cuando.date(), cuando.time(), cuando)

    dia = _dia_del_evento(evento)                                         # atado al día del evento
    if dia is None:
        return Momento(None, None, problema="el evento ya no tiene fecha")
    fi = dia + timedelta(days=fila["dias_inicio"])
    ff = dia + timedelta(days=fila["dias_fin"]) if fila.get("dias_fin") is not None else fi
    return Momento(fi, ff, hora, datetime.combine(fi, hora) if hora and ff == fi else None)


def _dia_texto(d: date) -> str:
    return f"{_DIAS_SEMANA[d.weekday()]} {d.day}/{d.month}"


def describir(m: Momento) -> Optional[str]:
    """El momento en llano y con el día de la semana, para que Alfred repita fechas reales."""
    if m.fecha_inicio is None:
        return None
    if m.fecha_fin != m.fecha_inicio:
        return f"del {_dia_texto(m.fecha_inicio)} al {_dia_texto(m.fecha_fin)}"
    if m.cuando is not None:
        return f"{_dia_texto(m.fecha_inicio)} a las {m.cuando:%H:%M}"
    return _dia_texto(m.fecha_inicio)


def _serializar(fila: dict, m: Momento, evento_titulo: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": fila["id"],
        "texto": fila["texto"],
        "estado": fila["estado"],
        "evento_id": fila.get("evento_id"),
        "evento": evento_titulo,
        "fecha_inicio": m.fecha_inicio.isoformat() if m.fecha_inicio else None,
        "fecha_fin": m.fecha_fin.isoformat() if m.fecha_fin else None,
        "hora": f"{m.hora:%H:%M}" if m.hora else None,
        "cuando": f"{m.cuando:%Y-%m-%dT%H:%M}" if m.cuando else None,
        "cuando_texto": describir(m),
        "problema": m.problema,
    }


# ── Repositorio ─────────────────────────────────────────────────────────────────────────────────────────────────────

class CompromisosModule(BaseModule):
    """Compromisos de un usuario. `reloj` (un callable sin argumentos) sustituye a `datetime.now()` en las pruebas."""

    def __init__(self, db, user_id, reloj=None):
        super().__init__(db, user_id)
        self._reloj = reloj or datetime.now

    def _ahora(self) -> datetime:
        return self._reloj().replace(microsecond=0)

    def _evento(self, evento_id: int) -> Optional[dict]:
        cursor = self.execute_query(
            "SELECT id, title, start_datetime, event_date, all_day, recurrence_rule FROM events"
            " WHERE id = %s AND user_id = %s", (evento_id, self.user_id))
        return cursor.fetchone()

    def _comprobar_evento(self, item: dict) -> Optional[dict]:
        """Lo que depende de la fila del evento (D50): existe, es del usuario y admite este desfase."""
        if not _presente(item, "evento_id"):
            return None
        evento = self._evento(item["evento_id"])
        if evento is None:
            raise FormaInvalida(f"evento_id {item['evento_id']}: no existe ningún evento tuyo con ese id")
        if evento["recurrence_rule"]:
            raise FormaInvalida(f"«{evento['title']}» es un evento recurrente: no admite compromisos atados "
                                "(¿a qué ocurrencia?). Crea el compromiso suelto, con fecha")
        if _presente(item, "minutos") and (evento["all_day"] or evento["start_datetime"] is None):
            raise FormaInvalida(f"«{evento['title']}» no tiene hora: usa dias_inicio (y hora) en vez de minutos")
        if _dia_del_evento(evento) is None:
            raise FormaInvalida(f"«{evento['title']}» no tiene fecha")
        return evento

    def crear(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Crea de 1 a 20 compromisos, todos o ninguno. Devuelve cada uno con su momento efectivo ya calculado."""
        if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
            return {"status": "invalid", "indice": None,
                    "message": f"hay que dar de 1 a {MAX_ITEMS} compromisos"}
        validados = []
        for i, item in enumerate(items):
            try:
                if not isinstance(item, dict):
                    raise FormaInvalida("cada compromiso es un objeto con texto y cuándo")
                validar_forma(item)
                evento = self._comprobar_evento(item)
            except FormaInvalida as e:
                return {"status": "invalid", "indice": i, "message": f"compromiso {i + 1}: {e}"}
            validados.append((item, evento))

        ahora = self._ahora()
        creados = []
        try:
            for item, evento in validados:
                fila = self._fila_nueva(item, ahora)
                cursor = self.execute_query(
                    "INSERT INTO compromisos (user_id, texto, evento_id, fecha_inicio, fecha_fin, dias_inicio,"
                    " dias_fin, hora, minutos, estado, created_at, updated_at)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', %s, %s)",
                    (self.user_id, fila["texto"], fila["evento_id"], fila["fecha_inicio"], fila["fecha_fin"],
                     fila["dias_inicio"], fila["dias_fin"], fila["hora"], fila["minutos"], ahora, ahora))
                fila.update(id=cursor.lastrowid, estado="pendiente")
                creados.append(_serializar(fila, momento_efectivo(fila, evento), evento["title"] if evento else None))
            self.commit()
        except Exception:
            self.db.rollback()
            raise
        logger.info(f"Compromisos creados user={self.user_id} ids={[c['id'] for c in creados]}")
        return {"status": "created", "compromisos": creados}

    @staticmethod
    def _fila_nueva(item: dict, ahora: datetime) -> dict:
        hora = _hora(item["hora"]) if _presente(item, "hora") else None
        return {
            "texto": item["texto"].strip(),
            "evento_id": item.get("evento_id"),
            "fecha_inicio": _fecha(item["fecha_inicio"], "fecha_inicio") if _presente(item, "fecha_inicio") else None,
            "fecha_fin": _fecha(item["fecha_fin"], "fecha_fin") if _presente(item, "fecha_fin") else None,
            "dias_inicio": item.get("dias_inicio"),
            "dias_fin": item.get("dias_fin"),
            "hora": hora,
            "minutos": item.get("minutos"),
        }

    def pendientes(self, evento_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Los pendientes del usuario con su `Momento` (y los datos de su evento), sin filtrar por ventana.

        Es lo que usa el planificador (H2). Cada elemento: {fila, momento, evento_titulo, aviso_para}.
        """
        sql = ("SELECT c.id, c.texto, c.evento_id, c.fecha_inicio, c.fecha_fin, c.dias_inicio, c.dias_fin, c.hora,"
               " c.minutos, c.estado, c.aviso_para, e.title AS e_title, e.start_datetime AS e_start,"
               " e.event_date AS e_date, e.all_day AS e_all_day"
               " FROM compromisos c LEFT JOIN events e ON e.id = c.evento_id"
               " WHERE c.user_id = %s AND c.estado = 'pendiente'")
        params: list = [self.user_id]
        if evento_id is not None:
            sql += " AND c.evento_id = %s"
            params.append(evento_id)
        filas = self.execute_query(sql, tuple(params)).fetchall()
        salida = []
        for f in filas:
            evento = None if f["evento_id"] is None or f["e_title"] is None else {
                "title": f["e_title"], "start_datetime": f["e_start"], "event_date": f["e_date"],
                "all_day": f["e_all_day"]}
            salida.append({"fila": f, "momento": momento_efectivo(f, evento), "evento_titulo": f["e_title"],
                           "aviso_para": f["aviso_para"]})
        return salida

    def listar(self, desde=None, hasta=None, evento_id: Optional[int] = None) -> Dict[str, Any]:
        """Los pendientes cuyo día o intervalo toca la ventana [desde, hasta] (por defecto, hoy + 14 días), en orden."""
        try:
            d = _fecha(desde, "desde") if desde else self._ahora().date()
            h = _fecha(hasta, "hasta") if hasta else d + timedelta(days=_DIAS_DEFECTO)
        except FormaInvalida as e:
            return {"status": "invalid", "message": str(e)}
        elegidos = []
        for p in self.pendientes(evento_id):
            m = p["momento"]
            if m.problema is None and not (m.fecha_fin >= d and m.fecha_inicio <= h):
                continue                                                  # los que no se pueden calcular salen siempre
            elegidos.append(p)
        elegidos.sort(key=lambda p: (p["momento"].fecha_inicio or date.max,
                                     p["momento"].cuando.time() if p["momento"].cuando else time.min,
                                     p["fila"]["id"]))
        return {"status": "ok", "desde": d.isoformat(), "hasta": h.isoformat(),
                "compromisos": [_serializar(p["fila"], p["momento"], p["evento_titulo"]) for p in elegidos]}

    def _estado(self, compromiso_id: int) -> Optional[str]:
        fila = self.execute_query("SELECT estado FROM compromisos WHERE id = %s AND user_id = %s",
                                  (compromiso_id, self.user_id)).fetchone()
        return fila["estado"] if fila else None

    def completar(self, compromiso_id: int) -> Dict[str, Any]:
        estado = self._estado(compromiso_id)
        if estado is None:
            return {"status": "not_found", "message": f"No hay ningún compromiso {compromiso_id}"}
        if estado != "pendiente":
            return {"status": "no_pendiente", "estado": estado, "message": f"El compromiso ya estaba {estado}"}
        self.execute_query("UPDATE compromisos SET estado = 'hecho', updated_at = %s WHERE id = %s AND user_id = %s",
                           (self._ahora(), compromiso_id, self.user_id))
        self.commit()
        return {"status": "completed", "id": compromiso_id}

    def borrar(self, compromiso_id: int, motivo: Optional[str]) -> Dict[str, Any]:
        """`olvidar` hace DELETE (D42: borrar es borrar); `cancelar` lo deja en estado `cancelado`."""
        if motivo not in _MOTIVOS:
            return {"status": "invalid", "message": f"motivo tiene que ser uno de: {', '.join(_MOTIVOS)}"}
        if self._estado(compromiso_id) is None:
            return {"status": "not_found", "message": f"No hay ningún compromiso {compromiso_id}"}
        if motivo == "olvidar":
            self.execute_query("DELETE FROM compromisos WHERE id = %s AND user_id = %s",
                               (compromiso_id, self.user_id))
            self.commit()
            return {"status": "deleted", "id": compromiso_id}
        self.execute_query("UPDATE compromisos SET estado = 'cancelado', updated_at = %s WHERE id = %s AND user_id = %s",
                           (self._ahora(), compromiso_id, self.user_id))
        self.commit()
        return {"status": "cancelled", "id": compromiso_id}

    def cancelar_por_eventos_borrados(self, evento_ids: List[int]) -> int:
        """Al borrar eventos (D50): sus compromisos pendientes pasan a `cancelado` y todos se desvinculan.

        **No hace commit**: lo llama `CalendarModule` en la misma transacción que el DELETE del evento. La FK no lleva
        ON DELETE (plan §2.1) y además se aplica a las filas ya canceladas o hechas, así que hay que soltar el
        `evento_id` de todas, no solo de las pendientes. Lo hecho sigue hecho; solo pierde el enlace.
        """
        if not evento_ids:
            return 0
        marcas = ", ".join(["%s"] * len(evento_ids))
        cursor = self.execute_query(
            f"UPDATE compromisos SET estado = IF(estado = 'pendiente', 'cancelado', estado), evento_id = NULL,"
            f" updated_at = %s WHERE user_id = %s AND evento_id IN ({marcas})",
            (self._ahora(), self.user_id, *evento_ids))
        return cursor.rowcount
