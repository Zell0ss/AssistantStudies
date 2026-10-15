"""SQL de la memoria (fase 2, D33, D38): entidades por usuario y catalogo de atributos comun.

H1 cubre el alta y la consulta de entidades, atributos y alias. Los hechos y las decisiones
llegan en H2. Cada escritura hace commit; `valid_to`/`superseded_by` (H2) irán en una transaccion.
"""
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
        nombre = username or user_id
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

    # --- interno -------------------------------------------------------------------------

    def _insertar_alias(self, tabla: str, columna: str, dueno_id: int, alias_norm: str) -> None:
        if not alias_norm:
            return
        cur = self._db.cursor()
        # IGNORE: repetir un alias es un no-op (uq_alias), no un error.
        cur.execute(f"INSERT IGNORE INTO {tabla} ({columna}, alias_norm) VALUES (%s, %s)",
                    (dueno_id, alias_norm))
