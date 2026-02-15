# modules/base.py
"""
Base class for all domain modules.
Provides database connection and common utilities.
"""
from loguru import logger

class BaseModule:
    """
    Base class for domain modules (Inventory, Shopping, Packing, Notes).

    Args:
        db: Database connection
        user_id: Telegram user ID (for multi-user support)
    """

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id
        logger.debug(f"{self.__class__.__name__} initialized for user {user_id}")

    def execute_query(self, query, params):
        """
        Execute a SQL query and return cursor.

        Args:
            query: SQL query string (use %s placeholders)
            params: Tuple of parameters

        Returns:
            Cursor with results
        """
        cursor = self.db.cursor()
        cursor.execute(query, params)
        return cursor

    def commit(self):
        """Commit the current transaction"""
        self.db.commit()
        logger.debug("Transaction committed")
