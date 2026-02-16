"""Packing module with recurring items support."""
from typing import Dict, Any, Optional
from modules.item_list import ItemListModule
from loguru import logger


class PackingModule(ItemListModule):
    """Packing lists module with recurring items support."""

    def add(self, item_name: str, quantity: float = 1, unit: str = 'unidades',
            recurring: bool = False, notes: Optional[str] = None) -> None:
        """Add item to packing list with optional recurring flag.

        Args:
            item_name: Name of the item
            quantity: Quantity to add (default: 1)
            unit: Unit of measurement (default: 'unidades')
            recurring: Whether item should persist after being checked (default: False)
            notes: Additional notes (optional)
        """
        list_id = self._ensure_list_exists()
        cursor = self.db.cursor()

        # Check if item already exists (case-insensitive)
        cursor.execute(
            """
            SELECT id, quantity FROM list_items
            WHERE list_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (list_id, item_name)
        )
        row = cursor.fetchone()

        if row:
            # Update existing item - add to quantity and update recurring flag
            item_id, current_quantity = row
            new_quantity = current_quantity + quantity
            cursor.execute(
                """
                UPDATE list_items
                SET quantity = %s, recurring = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (new_quantity, recurring, item_id)
            )
        else:
            # Insert new item with recurring flag
            cursor.execute(
                """
                INSERT INTO list_items (list_id, name, quantity, unit, notes, recurring)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (list_id, item_name, quantity, unit, notes, recurring)
            )

        self.db.commit()
        cursor.close()

    def get(self, item_name: str) -> Optional[Dict[str, Any]]:
        """
        Get item from list (override to include recurring field).

        Args:
            item_name: Name of item to retrieve

        Returns:
            Item dict with recurring field, or None if not found
        """
        list_id = self._get_list_id()
        if not list_id:
            return None

        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT id, name, quantity, unit, notes, checked, recurring, created_at, updated_at
            FROM list_items
            WHERE list_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (list_id, item_name)
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return {
            'id': row[0],
            'item_name': row[1],
            'quantity': row[2],
            'unit': row[3],
            'notes': row[4],
            'checked': row[5],
            'recurring': bool(row[6]),
            'created_at': row[7],
            'updated_at': row[8]
        }

    def check_item(self, item_name: str) -> Dict[str, Any]:
        """
        Mark item as checked (packed).

        - Non-recurring items: removed from list
        - Recurring items: kept in list for next trip

        Args:
            item_name: Name of item to check

        Returns:
            Dict with status and message
        """
        item = self.get(item_name)

        if not item:
            return {
                'status': 'error',
                'message': f'{item_name} no está en la lista'
            }

        if item['recurring']:
            # Keep recurring items
            logger.info(f"Checked recurring item {item_name} in packing list")
            return {
                'status': 'checked',
                'message': f'✅ {item_name} marcado (se mantiene en lista)'
            }
        else:
            # Remove non-recurring items
            self.remove(item_name)
            logger.info(f"Checked and removed {item_name} from packing list")
            return {
                'status': 'checked',
                'message': f'✅ {item_name} empacado y eliminado de lista'
            }
