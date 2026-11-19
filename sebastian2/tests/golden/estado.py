"""Estado sembrado de los goldens (fase 3 H3b, H3-revision §4): un golden puede traer `estado:` con los eventos y
compromisos que su `historia` da por hechos. Sin eso, «Apuntado en tu calendario…» es solo texto, la BD de test no
tiene la cita y buscar antes de actuar (lo correcto) hace fallar el golden por ruido.

    estado:
      eventos:
        - {titulo: "Endoscopia", fecha: "2027-01-28", hora: "09:30"}     # fecha: YYYY-MM-DD, «hoy» o «manana»
      compromisos:                                                     # opcional; atados al primer evento sembrado
        - {texto: "Primera toma del preparado", dias_inicio: -1, hora: "21:00"}

Se siembra en `sebastian_test` después de `_historial_limpio` y antes de la frase, con el mismo usuario, y se
limpia al terminar cada golden. Todo pasa por los módulos reales, y nada escribe fuera de `sebastian_test`
(`exigir_bd_de_test`). Se prueba sin API en tests/test_golden_estado.py.
"""
from datetime import date, timedelta
from typing import Optional

from modules.calendar import CalendarModule
from modules.compromisos import CompromisosModule
from tests.golden.memoria_base import exigir_bd_de_test


def _fecha(valor, hoy: date) -> date:
    if valor == "hoy":
        return hoy
    if valor == "manana":
        return hoy + timedelta(days=1)
    return date.fromisoformat(str(valor))


# Lo que ha sembrado `sembrar_estado` y aún no se ha limpiado. El usuario de goldens comparte eventos con la fixture de
# sesión `golden_fixtures` («teatro» y su entrada, que usan los goldens antiguos): se borra solo lo sembrado aquí, por id.
_SEMBRADO = {"eventos": [], "compromisos": []}


def sembrar_estado(db, user_id: str, estado: Optional[dict], hoy: Optional[date] = None) -> dict:
    """Crea los eventos y compromisos de `estado` para `user_id`. Devuelve {'eventos': [ids], 'compromisos': [ids]}.

    Apunta los ids en `_SEMBRADO` (también los de una siembra a medias) para que `limpiar_sembrado` los borre."""
    exigir_bd_de_test(db)
    sembrado = {"eventos": [], "compromisos": []}
    if not estado:
        return sembrado
    try:
        return _sembrar(db, user_id, estado, hoy, sembrado)
    finally:
        _SEMBRADO["eventos"] += sembrado["eventos"]
        _SEMBRADO["compromisos"] += sembrado["compromisos"]


def _sembrar(db, user_id: str, estado: dict, hoy: Optional[date], sembrado: dict) -> dict:
    hoy = hoy or date.today()
    cal = CalendarModule(db, user_id)
    for ev in estado.get("eventos", []):
        r = cal.add_event(title=ev["titulo"], event_date=_fecha(ev["fecha"], hoy), event_time=ev.get("hora"),
                          all_day=ev.get("hora") is None)
        if r["status"] != "added":
            raise ValueError(f"el estado del golden no se pudo sembrar: {r}")
        sembrado["eventos"].append(r["event_id"])
    pasos = estado.get("compromisos", [])
    if pasos:
        if not sembrado["eventos"]:
            raise ValueError("`compromisos` en el estado necesita al menos un evento (van atados al primero)")
        items = [{**p, "evento_id": sembrado["eventos"][0]} for p in pasos]
        r = CompromisosModule(db, user_id).crear(items)
        if r.get("status") != "created":
            raise ValueError(f"el estado del golden no se pudo sembrar: {r}")
        sembrado["compromisos"] = [c["id"] for c in r["compromisos"]]
    return sembrado


def limpiar_sembrado(db) -> None:
    """Borra solo lo que sembró `sembrar_estado` (compromisos primero), y deja la lista vacía."""
    exigir_bd_de_test(db)
    cur = db.cursor()
    eventos, compromisos = _SEMBRADO["eventos"], _SEMBRADO["compromisos"]
    if compromisos:
        cur.execute(f"DELETE FROM compromisos WHERE id IN ({', '.join(['%s'] * len(compromisos))})", tuple(compromisos))
    if eventos:
        marcas = ', '.join(['%s'] * len(eventos))
        # Los compromisos que el propio golden creó sobre el evento sembrado también bloquean su borrado (FK sin ON DELETE).
        cur.execute(f"DELETE FROM compromisos WHERE evento_id IN ({marcas})", tuple(eventos))
        cur.execute(f"DELETE FROM events WHERE id IN ({marcas})", tuple(eventos))
    db.commit()
    _SEMBRADO["eventos"].clear()
    _SEMBRADO["compromisos"].clear()


def limpiar_agenda(db, *user_ids: str) -> None:
    """Borra los compromisos y eventos de esos usuarios (compromisos primero: la FK a events no lleva ON DELETE)."""
    exigir_bd_de_test(db)
    cur = db.cursor()
    for u in user_ids:
        cur.execute("DELETE FROM compromisos WHERE user_id = %s", (u,))
        cur.execute("DELETE FROM events WHERE user_id = %s", (u,))
    db.commit()


def ids_de_eventos(db, user_id: str) -> set:
    """Los ids de los eventos que tiene ahora `user_id` (para saber, después de un golden, cuáles son nuevos)."""
    exigir_bd_de_test(db)
    db.commit()                                                   # REPEATABLE READ: que vea lo último confirmado
    cur = db.cursor()
    cur.execute("SELECT id FROM events WHERE user_id = %s", (user_id,))
    return {fila["id"] for fila in cur.fetchall()}


def borrar_eventos_nuevos(db, user_id: str, antes: set) -> None:
    """H9: borra los eventos de `user_id` que no estaban en `antes` (los que el planner creó en el golden y los sembrados),
    con los compromisos atados a ellos. Sin esto, #81-#83 dejaban su evento y #84/#85 lo encontraban."""
    exigir_bd_de_test(db)
    nuevos = sorted(ids_de_eventos(db, user_id) - set(antes))
    if not nuevos:
        return
    marcas = ', '.join(['%s'] * len(nuevos))
    cur = db.cursor()
    cur.execute(f"DELETE FROM compromisos WHERE evento_id IN ({marcas})", tuple(nuevos))
    cur.execute(f"DELETE FROM events WHERE id IN ({marcas})", tuple(nuevos))
    db.commit()
