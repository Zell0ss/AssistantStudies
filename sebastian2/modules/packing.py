# modules/packing.py
"""
Packing list module - items to bring (recurring or one-time).
"""
from modules.base import BaseModule
from loguru import logger

class PackingListModule(BaseModule):
    """
    Manage packing lists (e.g., items to bring to Gijón).

    Operations:
    - add(list_name, item, recurring) - Add item to packing list
    - check(list_name, item) - Check off item (stays if recurring, disappears if not)
    - uncheck_recurring(list_name) - Reset recurring items for next trip
    - list_items(list_name, include_checked) - Get items in packing list
    """

    def _ensure_list(self, list_name):
        """Ensure packing list exists for this user"""
        query = """
            SELECT id FROM lists
            WHERE user_id = %s AND name = %s
        """
        cursor = self.execute_query(query, (self.user_id, list_name))
        existing = cursor.fetchone()

        if not existing:
            query = """
                INSERT INTO lists (user_id, name, list_type)
                VALUES (%s, %s, 'packing')
            """
            self.execute_query(query, (self.user_id, list_name))
            self.commit()
            logger.info(f"Created packing list '{list_name}' for user {self.user_id}")

    def _get_list_id(self, list_name):
        """Get the packing list ID"""
        query = """
            SELECT id FROM lists
            WHERE user_id = %s AND name = %s
        """
        cursor = self.execute_query(query, (self.user_id, list_name))
        result = cursor.fetchone()
        return result['id'] if result else None

    def add(self, list_name, item_name, recurring=False):
        """
        Add item to packing list.

        Args:
            list_name: Name of the packing list (e.g., "gijón_llevar")
            item_name: Name of the item
            recurring: If True, item stays when checked; if False, disappears
        """
        self._ensure_list(list_name)
        list_id = self._get_list_id(list_name)

        # Check if item already in list
        query = """
            SELECT id FROM list_items
            WHERE list_id = %s AND name = %s
        """
        cursor = self.execute_query(query, (list_id, item_name))
        existing = cursor.fetchone()

        if not existing:
            query = """
                INSERT INTO list_items (list_id, name, recurring, checked)
                VALUES (%s, %s, %s, FALSE)
            """
            self.execute_query(query, (list_id, item_name, recurring))
            self.commit()
            logger.info(f"Added to packing list '{list_name}': {item_name} (recurring={recurring})")

    def check(self, list_name, item_name):
        """
        Check off item in packing list.
        - If recurring: mark as checked (stays in list)
        - If not recurring: delete item (disappears)

        Args:
            list_name: Name of the packing list
            item_name: Name of the item to check off
        """
        list_id = self._get_list_id(list_name)
        if not list_id:
            return

        # Get item to check if recurring
        query = """
            SELECT recurring FROM list_items
            WHERE list_id = %s AND name = %s
        """
        cursor = self.execute_query(query, (list_id, item_name))
        item = cursor.fetchone()

        if not item:
            return

        if item['recurring']:
            # Mark as checked (stays in list)
            query = """
                UPDATE list_items
                SET checked = TRUE
                WHERE list_id = %s AND name = %s
            """
            self.execute_query(query, (list_id, item_name))
            self.commit()
            logger.info(f"Checked recurring item in '{list_name}': {item_name}")
        else:
            # Delete item (disappears)
            query = """
                DELETE FROM list_items
                WHERE list_id = %s AND name = %s
            """
            self.execute_query(query, (list_id, item_name))
            self.commit()
            logger.info(f"Checked and removed one-time item from '{list_name}': {item_name}")

    def uncheck_recurring(self, list_name):
        """
        Uncheck all recurring items in packing list (for next trip).

        Args:
            list_name: Name of the packing list
        """
        list_id = self._get_list_id(list_name)
        if not list_id:
            return

        query = """
            UPDATE list_items
            SET checked = FALSE
            WHERE list_id = %s AND recurring = TRUE
        """
        self.execute_query(query, (list_id,))
        self.commit()
        logger.info(f"Unchecked recurring items in '{list_name}'")

    def list_items(self, list_name, include_checked=False):
        """
        Get items in packing list.

        Args:
            list_name: Name of the packing list
            include_checked: If True, include checked items; if False, only unchecked

        Returns:
            List of dicts with item data
        """
        list_id = self._get_list_id(list_name)
        if not list_id:
            return []

        if include_checked:
            query = """
                SELECT * FROM list_items
                WHERE list_id = %s
                ORDER BY created_at
            """
            cursor = self.execute_query(query, (list_id,))
        else:
            query = """
                SELECT * FROM list_items
                WHERE list_id = %s AND checked = FALSE
                ORDER BY created_at
            """
            cursor = self.execute_query(query, (list_id,))

        return cursor.fetchall()
