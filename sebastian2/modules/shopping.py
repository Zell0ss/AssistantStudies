"""
Shopping List Module for Sebastian 2.0

Manages multiple shopping lists where items automatically disappear when marked as bought.
Auto-creates 'compra' list if no list name specified.
"""

from typing import List, Dict, Any, Optional


class ShoppingListModule:
    """Manage shopping list items across multiple lists"""

    def __init__(self, conn, user_id: str):
        """Initialize shopping list module

        Args:
            conn: Database connection
            user_id: Telegram user ID
        """
        self.conn = conn
        self.user_id = user_id

    def _ensure_shopping_list(self, list_name: str = "compra") -> int:
        """Ensure shopping list exists, create if not

        Args:
            list_name: Name of the shopping list (default: "compra")

        Returns:
            List ID
        """
        cursor = self.conn.cursor()

        # Check if list exists
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND name = %s",
            (self.user_id, list_name)
        )
        result = cursor.fetchone()

        if result:
            return result['id']
        else:
            # Create list
            cursor.execute(
                "INSERT INTO lists (user_id, name, list_type) VALUES (%s, %s, 'shopping')",
                (self.user_id, list_name)
            )
            self.conn.commit()
            # Get the created list ID
            return cursor.lastrowid

    def add(self, item_name: str, list_name: str = "compra") -> Dict[str, Any]:
        """Add item to shopping list

        Args:
            item_name: Item name
            list_name: Shopping list name (default: "compra")

        Returns:
            Result with status and item details
        """
        list_id = self._ensure_shopping_list(list_name)
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
            list_display = f" de {list_name}" if list_name != "compra" else " de compra"
            return {
                'status': 'exists',
                'message': f'"{item_name}" ya está en la lista{list_display}'
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

        list_display = f" de {list_name}" if list_name != "compra" else " de compra"
        return {
            'status': 'added',
            'item_id': item_id,
            'name': item_name,
            'list_name': list_name,
            'message': f'"{item_name}" añadido a la lista{list_display}'
        }

    def remove(self, item_name: str, list_name: str = "compra") -> Dict[str, Any]:
        """Remove item from shopping list

        Args:
            item_name: Item name
            list_name: Shopping list name (default: "compra")

        Returns:
            Result with status and message
        """
        list_id = self._ensure_shopping_list(list_name)
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

        list_display = f" de {list_name}" if list_name != "compra" else " de compra"
        if deleted:
            return {
                'status': 'removed',
                'message': f'"{item_name}" eliminado de la lista{list_display}'
            }
        else:
            return {
                'status': 'not_found',
                'message': f'"{item_name}" no está en la lista{list_display}'
            }

    def mark_bought(self, item_name: str, list_name: str = "compra") -> Dict[str, Any]:
        """Mark item as bought (removes it from list)

        Args:
            item_name: Item name
            list_name: Shopping list name (default: "compra")

        Returns:
            Result with status and message
        """
        # Simply remove the item - items disappear when bought
        return self.remove(item_name, list_name)

    def list_all(self, list_name: str = "compra") -> List[Dict[str, Any]]:
        """List all unchecked items in shopping list

        Args:
            list_name: Shopping list name (default: "compra")

        Returns:
            List of unchecked items with name and id
        """
        list_id = self._ensure_shopping_list(list_name)
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

    def list_all_lists(self) -> List[Dict[str, Any]]:
        """List all shopping lists for this user

        Returns:
            List of shopping lists with name and item count
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT l.name, COUNT(li.id) as item_count
            FROM lists l
            LEFT JOIN list_items li ON l.id = li.list_id AND NOT li.checked
            WHERE l.user_id = %s AND l.list_type = 'shopping'
            GROUP BY l.id, l.name
            ORDER BY l.created_at ASC
            """,
            (self.user_id,)
        )

        lists = []
        for row in cursor.fetchall():
            lists.append({
                'name': row['name'],
                'item_count': row['item_count']
            })

        return lists
