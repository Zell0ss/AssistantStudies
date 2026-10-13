"""Repository for the conversation history shared between turns (fase 1, D21–D24)."""
from datetime import datetime, timedelta
from logcentral_client import get_logger

logger = get_logger("sebastian")

_FORMATO = '%Y-%m-%d %H:%M:%S'


class ConversationRepository:
    """Guarda y lee los últimos intercambios usuario/bot de cada usuario."""

    def __init__(self, db):
        self._db = db

    def recientes(self, user_id: str, limite: int = 6, ventana_min: int = 120) -> list[dict]:
        """Últimos `limite` intercambios dentro de la ventana, del más antiguo al más nuevo.

        El corte se calcula en Python y va como parámetro (sin NOW()/DATE_SUB) para que la
        misma consulta sirva con MariaDB y con sqlite en los tests.
        """
        corte = (datetime.now() - timedelta(minutes=ventana_min)).strftime(_FORMATO)
        cur = self._db.cursor()
        cur.execute(
            "SELECT user_msg, bot_reply FROM conversations"
            " WHERE user_id = %s AND created_at >= %s"
            " ORDER BY created_at DESC, id DESC LIMIT %s",
            (user_id, corte, limite),
        )
        filas = cur.fetchall()
        return [{"user_msg": f["user_msg"], "bot_reply": f["bot_reply"]} for f in reversed(filas)]

    def guardar(self, user_id: str, user_msg: str, bot_reply: str) -> None:
        # created_at lo pone Python, no el DEFAULT de la BD, para comparar con el mismo reloj
        # que usa `recientes`.
        cur = self._db.cursor()
        cur.execute(
            "INSERT INTO conversations (user_id, user_msg, bot_reply, created_at)"
            " VALUES (%s, %s, %s, %s)",
            (user_id, user_msg, bot_reply, datetime.now().strftime(_FORMATO)),
        )
        self._db.commit()

    def limpiar(self, dias: int = 7) -> int:
        """Borra lo anterior a `dias` días y devuelve cuántas filas. Solo borra por fecha."""
        corte = (datetime.now() - timedelta(days=dias)).strftime(_FORMATO)
        cur = self._db.cursor()
        cur.execute("DELETE FROM conversations WHERE created_at < %s", (corte,))
        self._db.commit()
        borradas = cur.rowcount
        logger.info(f"Cleaned up {borradas} old conversation records (> {dias} days)")
        return borradas
