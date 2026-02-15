"""
Shopping List Module for Sebastian 2.0

Manages a shopping list where items automatically disappear when marked as bought.
Auto-creates 'compra' list on first use.
"""

from typing import List, Dict, Any, Optional


class ShoppingListModule:
    """Manage shopping list items"""

    def __init__(self, conn, user_id: str):
        """Initialize shopping list module

        Args:
            conn: Database connection
            user_id: Telegram user ID
        """
        self.conn = conn
        self.user_id = user_id
        self.list_id: Optional[int] = None

    def _ensure_shopping_list(self) -> int:
        """Ensure shopping list exists, create if not

        Returns:
            List ID
        """
        cursor = self.conn.cursor()

        # Check if list exists
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND name = 'compra'",
            (self.user_id,)
        )
        result = cursor.fetchone()

        if result:
            self.list_id = result['id']
        else:
            # Create list
            cursor.execute(
                "INSERT INTO lists (user_id, name) VALUES (%s, 'compra')",
                (self.user_id,)
            )
            self.conn.commit()
            # Get the created list ID
            self.list_id = cursor.lastrowid

        return self.list_id

    def add(self, item_name: str) -> Dict[str, Any]:
        """Add item to shopping list

        Args:
            item_name: Item name

        Returns:
            Result with status and item details
        """
        list_id = self._ensure_shopping_list()
        cursor = self.conn.cursor()

        # Check if item already exists (unchecked)
        cursor.execute(
            """
            SELECT id FROM list_items
            WHERE list_id = %s AND name = %s AND NOT checked
            """,
            (list_id, item_name)
        )
        if cursor.fetchone():
            return {
                'status': 'exists',
                'message': f'"{item_name}" ya está en la lista de compra'
            }

        # Add item
        cursor.execute(
            """
            INSERT INTO list_items (list_id, name, checked)
            VALUES (%s, %s, false)
            """,
            (list_id, item_name)
        )
        self.conn.commit()
        item_id = cursor.lastrowid

        return {
            'status': 'added',
            'item_id': item_id,
            'name': item_name,
            'message': f'"{item_name}" añadido a la lista de compra'
        }

    def remove(self, item_name: str) -> Dict[str, Any]:
        """Remove item from shopping list

        Args:
            item_name: Item name

        Returns:
            Result with status and message
        """
        list_id = self._ensure_shopping_list()
        cursor = self.conn.cursor()

        # Delete item (whether checked or not)
        cursor.execute(
            """
            DELETE FROM list_items
            WHERE list_id = %s AND name = %s
            RETURNING id
            """,
            (list_id, item_name)
        )
        deleted = cursor.fetchone()
        self.conn.commit()

        if deleted:
            return {
                'status': 'removed',
                'message': f'"{item_name}" eliminado de la lista de compra'
            }
        else:
            return {
                'status': 'not_found',
                'message': f'"{item_name}" no está en la lista de compra'
            }

    def mark_bought(self, item_name: str) -> Dict[str, Any]:
        """Mark item as bought (removes it from list)

        Args:
            item_name: Item name

        Returns:
            Result with status and message
        """
        # Simply remove the item - items disappear when bought
        return self.remove(item_name)

    def list_all(self) -> List[Dict[str, Any]]:
        """List all unchecked items in shopping list

        Returns:
            List of unchecked items with name and id
        """
        list_id = self._ensure_shopping_list()
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, name
            FROM list_items
            WHERE list_id = %s AND NOT checked
            ORDER BY created_at ASC
            """,
            (list_id,)
        )

        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row['id'],
                'name': row['name']
            })

        return items
