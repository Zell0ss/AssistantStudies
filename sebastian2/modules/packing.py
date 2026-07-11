"""Packing module with recurring items support."""
from typing import Dict, Any, Optional
from modules.item_list import ItemListModule
from logcentral_client import get_logger

logger = get_logger("sebastian")


class PackingModule(ItemListModule):
    """Packing lists module with recurring items support."""

    def add(self, item_name: str, quantity: float = 1, unit: str = 'unidades',
            recurring: bool = False, **kwargs) -> Dict[str, Any]:
        """Add item to packing list with optional recurring flag."""
        return super().add(item_name, quantity, unit, recurring=recurring, **kwargs)

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
            'id': row['id'],
            'item_name': row['name'],
            'quantity': row['quantity'],
            'unit': row['unit'],
            'notes': row['notes'],
            'checked': row['checked'],
            'recurring': bool(row['recurring']),
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }

    def list_all(self) -> list:
        """
        List all items in packing list (override to include recurring field).

        Returns:
            List of item dicts with recurring field included
        """
        list_id = self._get_list_id()
        if not list_id:
            return []

        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT id, name, quantity, unit, notes, checked, recurring, created_at, updated_at
            FROM list_items
            WHERE list_id = %s
            ORDER BY name
            """,
            (list_id,)
        )

        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row['id'],
                'item_name': row['name'],
                'quantity': row['quantity'],
                'unit': row['unit'],
                'notes': row['notes'],
                'checked': row['checked'],
                'recurring': bool(row['recurring']),
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })

        return items

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
                'message': f'{item_name} no está en {self.list_name}'
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
