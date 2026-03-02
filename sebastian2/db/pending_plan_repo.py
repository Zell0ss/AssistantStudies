"""Repository for pending orchestrator plans."""
from datetime import datetime, timedelta
from loguru import logger

_TTL_HOURS = 24


class PendingPlanRepository:
    """Stores and retrieves pending Haiku loop state per user."""

    def __init__(self, db):
        self._db = db

    def save(self, user_id: str, original_message: str, messages_json: str,
             question: str, missing_field: str | None = None) -> None:
        """Insert or replace the open plan for this user."""
        expires_at = (datetime.now() + timedelta(hours=_TTL_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
        cur = self._db.cursor()
        cur.execute("DELETE FROM pending_plans WHERE user_id = ?", (user_id,))
        cur.execute(
            "INSERT INTO pending_plans"
            " (user_id, original_message, messages_json, question, missing_field, expires_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, original_message, messages_json, question, missing_field, expires_at)
        )
        self._db.commit()
        logger.debug(f"Saved pending plan for user {user_id!r}: {question!r}")

    def get_active(self, user_id: str) -> dict | None:
        """Return the active (non-expired) plan for user, or None."""
        cur = self._db.cursor()
        cur.execute(
            "SELECT * FROM pending_plans WHERE user_id = ? AND expires_at > ?",
            (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def delete(self, user_id: str) -> bool:
        """Delete the plan for user. Returns True if a row was deleted."""
        cur = self._db.cursor()
        cur.execute("DELETE FROM pending_plans WHERE user_id = ?", (user_id,))
        self._db.commit()
        deleted = cur.rowcount > 0
        if deleted:
            logger.debug(f"Deleted pending plan for user {user_id!r}")
        return deleted

    def delete_all(self) -> int:
        """Delete all plans (used at bot startup). Returns count deleted."""
        cur = self._db.cursor()
        cur.execute("DELETE FROM pending_plans")
        self._db.commit()
        count = cur.rowcount
        logger.info(f"Cleared {count} pending plans on startup")
        return count
