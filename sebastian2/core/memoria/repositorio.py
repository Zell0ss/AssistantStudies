"""SQL de la memoria (fase 2, D33, D38): entidades por usuario y catalogo de atributos comun.

H1 cubre el alta y la consulta de entidades, atributos y alias. Los hechos y las decisiones
llegan en H2. Cada escritura hace commit; `valid_to`/`superseded_by` (H2) irán en una transaccion.
"""
import json
from datetime import datetime

from logcentral_client import get_logger

from core.memoria.normalizar import normalizar

logger = get_logger("sebastian")

_FORMATO = "%Y-%m-%d %H:%M:%S"
_ALIAS_DEL_YO = ("yo", "mi", "me")


def _ahora() -> str:
    # Lo pone Python, no la BD: mismo reloj que el resto de repositorios (conversation_repo).
    return datetime.now().strftime(_FORMATO)


class RepositorioMemoria:
    def __init__(self, db):
        self._db = db

    # --- Entidades (por usuario, D33) ---------------------------------------------------

    def crear_entidad(self, user_id: str, nombre: str, tipo: str, *, estado: str = "pending",
                      origen: str = "conversacion", descripcion: str | None = None,
                      es_usuario: bool = False) -> int:
        """Crea la entidad y su alias canonico (el nombre normalizado). Devuelve el id."""
        cur = self._db.cursor()
        cur.execute(
            "INSERT INTO mem_entidades (user_id, nombre, tipo, estado, es_usuario, origen, descripcion,"
            " created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, nombre, tipo, estado, es_usuario, origen, descripcion, _ahora()),
        )
        entidad_id = cur.lastrowid
        self._insertar_alias("mem_entidad_alias", "entidad_id", entidad_id, normalizar(nombre))
        self._db.commit()
        return entidad_id

    def entidad(self, entidad_id: int) -> dict | None:
        cur = self._db.cursor()
        cur.execute("SELECT * FROM mem_entidades WHERE id = %s", (entidad_id,))
        return cur.fetchone()

    def entidades_por_alias(self, user_id: str, texto: str) -> list[dict]:
        """Entidades de ESE usuario cuyo alias normalizado coincide exactamente (D35, primer escalon)."""
        cur = self._db.cursor()
        cur.execute(
            "SELECT DISTINCT e.* FROM mem_entidades e JOIN mem_entidad_alias a ON a.entidad_id = e.id"
            " WHERE e.user_id = %s AND a.alias_norm = %s ORDER BY e.id",
            (user_id, normalizar(texto)),
        )
        return list(cur.fetchall())

    def listar_entidades(self, user_id: str) -> list[dict]:
        cur = self._db.cursor()
        cur.execute("SELECT * FROM mem_entidades WHERE user_id = %s ORDER BY id", (user_id,))
        return list(cur.fetchall())

    def anadir_alias_entidad(self, entidad_id: int, texto: str) -> None:
        self._insertar_alias("mem_entidad_alias", "entidad_id", entidad_id, normalizar(texto))
        self._db.commit()

    def entidad_usuario(self, user_id: str, username: str | None = None) -> int:
        """Id de la entidad «yo» de ese usuario; la crea la primera vez (alias yo, mi, me y su username)."""
        cur = self._db.cursor()
        cur.execute("SELECT id FROM mem_entidades WHERE user_id = %s AND es_usuario = TRUE", (user_id,))
        fila = cur.fetchone()
        if fila:
            return fila["id"]
        nombre = username or "yo"   # sin username, un nombre neutro (no el id de Telegram)
        try:
            entidad_id = self.crear_entidad(user_id, nombre, "persona", estado="activo",
                                            origen="conversacion", es_usuario=True)
        except Exception:
            # Dos hilos creando el «yo» a la vez: el segundo choca con uq_entidad; se queda con el primero.
            self._db.rollback()
            cur = self._db.cursor()
            cur.execute("SELECT id FROM mem_entidades WHERE user_id = %s AND es_usuario = TRUE", (user_id,))
            fila = cur.fetchone()
            if fila:
                return fila["id"]
            raise
        for alias in _ALIAS_DEL_YO:
            self._insertar_alias("mem_entidad_alias", "entidad_id", entidad_id, alias)
        self._db.commit()
        return entidad_id

    # --- Atributos (catalogo comun) -----------------------------------------------------

    def crear_atributo(self, nombre: str, descripcion: str, *, tipo_valor: str = "texto",
                       tipos_entidad: str = "*", cardinalidad: str = "uno", estado: str = "pending",
                       fuente: str = "conversacion") -> int:
        cur = self._db.cursor()
        cur.execute(
            "INSERT INTO mem_atributos (nombre, tipo_valor, tipos_entidad, cardinalidad, estado, fuente,"
            " descripcion, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (nombre, tipo_valor, tipos_entidad, cardinalidad, estado, fuente, descripcion, _ahora()),
        )
        atributo_id = cur.lastrowid
        self._insertar_alias("mem_atributo_alias", "atributo_id", atributo_id, normalizar(nombre))
        self._db.commit()
        return atributo_id

    def atributo(self, atributo_id: int) -> dict | None:
        cur = self._db.cursor()
        cur.execute("SELECT * FROM mem_atributos WHERE id = %s", (atributo_id,))
        return cur.fetchone()

    def atributos_por_alias(self, texto: str) -> list[dict]:
        cur = self._db.cursor()
        cur.execute(
            "SELECT DISTINCT t.* FROM mem_atributos t JOIN mem_atributo_alias a ON a.atributo_id = t.id"
            " WHERE a.alias_norm = %s ORDER BY t.id",
            (normalizar(texto),),
        )
        return list(cur.fetchall())

    def listar_atributos(self, estado: str | None = None) -> list[dict]:
        cur = self._db.cursor()
        if estado:
            cur.execute("SELECT * FROM mem_atributos WHERE estado = %s ORDER BY id", (estado,))
        else:
            cur.execute("SELECT * FROM mem_atributos ORDER BY id")
        return list(cur.fetchall())

    def anadir_alias_atributo(self, atributo_id: int, texto: str) -> None:
        self._insertar_alias("mem_atributo_alias", "atributo_id", atributo_id, normalizar(texto))
        self._db.commit()

    def alias_de_entidades(self, user_id: str) -> dict:
        """{entidad_id: [alias_norm, ...]} de las entidades de ese usuario (para el prompt del extractor)."""
        cur = self._db.cursor()
        cur.execute(
            "SELECT a.entidad_id, a.alias_norm FROM mem_entidad_alias a JOIN mem_entidades e"
            " ON e.id = a.entidad_id WHERE e.user_id = %s ORDER BY a.id", (user_id,))
        return self._agrupar(cur.fetchall(), "entidad_id")

    def alias_de_atributos(self) -> dict:
        cur = self._db.cursor()
        cur.execute("SELECT atributo_id, alias_norm FROM mem_atributo_alias ORDER BY id")
        return self._agrupar(cur.fetchall(), "atributo_id")

    @staticmethod
    def _agrupar(filas, clave: str) -> dict:
        agrupado = {}
        for f in filas:
            agrupado.setdefault(f[clave], []).append(f["alias_norm"])
        return agrupado

    # --- Hechos con vigencia (D7: nada se borra) -----------------------------------------

    def anadir_hecho(self, user_id: str, entidad_id: int, atributo_id: int, valor: str, *,
                     origen: str = "conversacion", confianza: float | None = None) -> int:
        cur = self._db.cursor()
        try:
            hecho_id = self._insertar_hecho(cur, user_id, entidad_id, atributo_id, valor, origen, confianza)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return hecho_id

    def sustituir_hecho(self, user_id: str, viejo_id: int, entidad_id: int, atributo_id: int,
                        valor: str, *, origen: str = "conversacion",
                        confianza: float | None = None) -> int:
        """Cierra el hecho viejo y abre el nuevo en UNA transaccion: si el INSERT falla, el viejo sigue
        vigente (D7). `superseded_by` del viejo apunta al nuevo."""
        cur = self._db.cursor()
        ahora = _ahora()
        try:
            cur.execute("UPDATE mem_hechos SET valid_to = %s WHERE id = %s AND user_id = %s"
                        " AND valid_to IS NULL", (ahora, viejo_id, user_id))
            if cur.rowcount != 1:
                raise ValueError(f"el hecho {viejo_id} no esta vigente para ese usuario")
            nuevo_id = self._insertar_hecho(cur, user_id, entidad_id, atributo_id, valor, origen,
                                            confianza, valid_from=ahora)
            cur.execute("UPDATE mem_hechos SET superseded_by = %s WHERE id = %s", (nuevo_id, viejo_id))
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return nuevo_id

    def retirar_hecho(self, hecho_id: int) -> None:
        """Retirar = poner `valid_to`. La fila se queda."""
        cur = self._db.cursor()
        cur.execute("UPDATE mem_hechos SET valid_to = %s WHERE id = %s AND valid_to IS NULL",
                    (_ahora(), hecho_id))
        self._db.commit()

    def hecho(self, hecho_id: int) -> dict | None:
        cur = self._db.cursor()
        cur.execute("SELECT * FROM mem_hechos WHERE id = %s", (hecho_id,))
        return cur.fetchone()

    def hechos_vigentes(self, user_id: str, entidad_id: int, atributo_id: int) -> list[dict]:
        cur = self._db.cursor()
        cur.execute("SELECT * FROM mem_hechos WHERE user_id = %s AND entidad_id = %s AND atributo_id = %s"
                    " AND valid_to IS NULL ORDER BY id", (user_id, entidad_id, atributo_id))
        return list(cur.fetchall())

    def hechos_historial(self, user_id: str, entidad_id: int, atributo_id: int) -> list[dict]:
        cur = self._db.cursor()
        cur.execute("SELECT * FROM mem_hechos WHERE user_id = %s AND entidad_id = %s AND atributo_id = %s"
                    " ORDER BY id", (user_id, entidad_id, atributo_id))
        return list(cur.fetchall())

    def hechos_con_nombres(self, user_id: str, entidad_id: int | None = None, atributo_id: int | None = None,
                           *, solo_vigentes: bool = True) -> list[dict]:
        """Hechos del usuario con el nombre de su entidad y de su atributo, y el valor de quien los sustituyo.
        La consulta se arma con ids y marcadores (`search_memory` no admite SQL libre, plan §2.3)."""
        sql = ("SELECT h.*, e.nombre AS entidad, a.nombre AS atributo, s.valor AS sustituido_por_valor"
               " FROM mem_hechos h JOIN mem_entidades e ON e.id = h.entidad_id"
               " JOIN mem_atributos a ON a.id = h.atributo_id"
               " LEFT JOIN mem_hechos s ON s.id = h.superseded_by AND s.user_id = h.user_id"
               " WHERE h.user_id = %s")
        params = [user_id]
        if entidad_id is not None:
            sql += " AND h.entidad_id = %s"
            params.append(entidad_id)
        if atributo_id is not None:
            sql += " AND h.atributo_id = %s"
            params.append(atributo_id)
        if solo_vigentes:
            sql += " AND h.valid_to IS NULL"
        cur = self._db.cursor()
        cur.execute(sql + " ORDER BY h.id", params)
        return list(cur.fetchall())

    def atributos_vigentes_por_entidad(self, user_id: str) -> list[dict]:
        """Una fila por (entidad, atributo) con algun hecho vigente, y el id de su ultimo hecho (los ids
        crecen con el tiempo). Solo nombres: para el indice del planner (D36), que nunca lleva valores."""
        cur = self._db.cursor()
        cur.execute(
            "SELECT e.id AS entidad_id, e.nombre, e.tipo, e.es_usuario, a.nombre AS atributo,"
            " MAX(h.id) AS ultimo_id FROM mem_hechos h"
            " JOIN mem_entidades e ON e.id = h.entidad_id JOIN mem_atributos a ON a.id = h.atributo_id"
            " WHERE h.user_id = %s AND h.valid_to IS NULL"
            " GROUP BY e.id, e.nombre, e.tipo, e.es_usuario, a.nombre", (user_id,))
        return list(cur.fetchall())

    def _insertar_hecho(self, cur, user_id, entidad_id, atributo_id, valor, origen, confianza,
                        valid_from: str | None = None) -> int:
        ahora = _ahora()
        cur.execute(
            "INSERT INTO mem_hechos (user_id, entidad_id, atributo_id, valor, valid_from, origen, confianza,"
            " created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, entidad_id, atributo_id, valor, valid_from or ahora, origen, confianza, ahora))
        return cur.lastrowid

    # --- Registro de decisiones (D8: por que se hizo lo que se hizo) ----------------------

    def registrar_decision(self, user_id: str, tipo: str, senales: dict, detalle: str, *,
                           hecho_id: int | None = None) -> int:
        """`detalle` lleva ids y nombres de regla, nunca el valor ni el texto del usuario."""
        cur = self._db.cursor()
        cur.execute(
            "INSERT INTO mem_decisiones (user_id, tipo, hecho_id, senales, detalle, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, tipo, hecho_id, json.dumps(senales, ensure_ascii=False), detalle[:255], _ahora()))
        self._db.commit()
        return cur.lastrowid

    def decisiones(self, user_id: str) -> list[dict]:
        cur = self._db.cursor()
        cur.execute("SELECT * FROM mem_decisiones WHERE user_id = %s ORDER BY id", (user_id,))
        filas = list(cur.fetchall())
        for f in filas:
            if isinstance(f["senales"], str):
                f["senales"] = json.loads(f["senales"])
        return filas

    # --- interno -------------------------------------------------------------------------

    def _insertar_alias(self, tabla: str, columna: str, dueno_id: int, alias_norm: str) -> None:
        if not alias_norm:
            return
        cur = self._db.cursor()
        # IGNORE: repetir un alias es un no-op (uq_alias), no un error.
        cur.execute(f"INSERT IGNORE INTO {tabla} ({columna}, alias_norm) VALUES (%s, %s)",
                    (dueno_id, alias_norm))
