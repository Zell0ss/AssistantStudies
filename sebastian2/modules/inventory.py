"""Inventory module with threshold warning support."""
from typing import Dict, Any, List, Optional
from modules.item_list import ItemListModule
from loguru import logger


class InventoryModule(ItemListModule):
    """Extends ItemListModule with threshold warnings for low stock."""

    def get(self, item_name: str) -> Optional[Dict[str, Any]]:
        """Get item details including low_threshold.

        Args:
            item_name: Name of the item

        Returns:
            Dict with item details including low_threshold, or None if not found
        """
        list_id = self._get_list_id()
        if not list_id:
            return None

        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT id, name, quantity, unit, notes, checked, low_threshold, created_at, updated_at
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
            'name': row['name'],
            'quantity': row['quantity'],
            'unit': row['unit'],
            'notes': row['notes'],
            'checked': row['checked'],
            'low_threshold': row['low_threshold'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }

    def add(self, item_name: str, quantity: float = 1, unit: str = 'unidades',
            threshold: float = 2, notes: Optional[str] = None) -> Dict[str, Any]:
        """Add item to inventory with threshold.

        Args:
            item_name: Name of the item to add
            quantity: Initial quantity (default: 1)
            unit: Unit of measurement (default: 'unidades')
            threshold: Low stock threshold (default: 2)
            notes: Optional notes about the item

        Returns:
            Dict with status, message, and warning fields
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
            # Update existing item - add to quantity and update threshold
            item_id = row['id']
            current_quantity = row['quantity']
            new_quantity = current_quantity + quantity
            cursor.execute(
                """
                UPDATE list_items
                SET quantity = %s, low_threshold = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (new_quantity, threshold, item_id)
            )
            status = 'updated'
            message = f'Actualizado {item_name}: {new_quantity} {unit}'
        else:
            # Insert new item with threshold
            cursor.execute(
                """
                INSERT INTO list_items (list_id, name, quantity, unit, notes, low_threshold)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (list_id, item_name, quantity, unit, notes, threshold)
            )
            status = 'added'
            message = f'Añadido {item_name}: {quantity} {unit}'

        self.db.commit()
        cursor.close()

        result = {'status': status, 'message': message}

        # Check if we should warn
        warning = self._check_and_warn(item_name)
        result.update(warning)

        return result

    def update_quantity(self, item_name: str, delta: float) -> Dict[str, Any]:
        """Update item quantity by delta and check threshold.

        Args:
            item_name: Name of the item to update
            delta: Amount to add (positive) or remove (negative)

        Returns:
            Dict with status, message, and warning fields
        """
        item = self.get(item_name)
        if not item:
            return {
                'status': 'error',
                'message': f'Item {item_name} no existe',
                'warning': False
            }

        new_quantity = float(item['quantity']) + delta

        if new_quantity <= 0:
            # Remove item if quantity drops to zero or below
            self.remove(item_name)
            return {
                'status': 'removed',
                'message': f'Eliminado {item_name} (cantidad llegó a {new_quantity})',
                'warning': False
            }

        list_id = self._get_list_id()
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE list_items SET quantity = %s, updated_at = CURRENT_TIMESTAMP WHERE list_id = %s AND LOWER(name) = LOWER(%s)",
            (new_quantity, list_id, item_name)
        )
        self.db.commit()
        cursor.close()

        result = {
            'status': 'updated',
            'message': f'Actualizado {item_name}: {new_quantity} {item.get("unit", "unidades")}'
        }

        # Check threshold warning
        warning = self._check_and_warn(item_name)
        result.update(warning)

        return result

    def set_quantity(self, item_name: str, quantity: float) -> Dict[str, Any]:
        """Set item quantity to specific value and check threshold.

        Args:
            item_name: Name of the item to update
            quantity: New quantity value

        Returns:
            Dict with status, message, and warning fields
        """
        item = self.get(item_name)
        if not item:
            return self.add(item_name, quantity)

        if quantity <= 0:
            # Remove item if quantity set to zero or below
            self.remove(item_name)
            return {
                'status': 'removed',
                'message': f'Eliminado {item_name} (cantidad: {quantity})',
                'warning': False
            }

        list_id = self._get_list_id()
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE list_items SET quantity = %s, updated_at = CURRENT_TIMESTAMP WHERE list_id = %s AND LOWER(name) = LOWER(%s)",
            (quantity, list_id, item_name)
        )
        self.db.commit()
        cursor.close()

        result = {
            'status': 'updated',
            'message': f'Actualizado {item_name}: {quantity} {item.get("unit", "unidades")}'
        }

        # Check threshold warning
        warning = self._check_and_warn(item_name)
        result.update(warning)

        return result

    def _check_and_warn(self, item_name: str) -> Dict[str, Any]:
        """Check if item is below threshold and return warning.

        Args:
            item_name: Name of the item to check

        Returns:
            Dict with 'warning' (bool) and optional 'message' (str) fields
        """
        item = self.get(item_name)
        if not item:
            return {'warning': False}

        quantity = float(item['quantity'])
        threshold = item.get('low_threshold')

        if threshold is not None and quantity < threshold:
            unit = item.get('unit', 'unidades')
            warning_msg = f"⚠️ Te queda poco {item_name} ({quantity} {unit}). Piensa en comprar."
            logger.warning(f"Low stock: {item_name} = {quantity} (threshold: {threshold})")
            return {'warning': True, 'message': warning_msg}

        return {'warning': False}

    def check_low_stock(self) -> List[Dict[str, Any]]:
        """Get all items with quantity below threshold.

        Returns:
            List of items (as dicts) where quantity < low_threshold
        """
        list_id = self._get_list_id()
        if not list_id:
            return []

        cursor = self.db.cursor()
        cursor.execute("""
            SELECT id, name, quantity, unit, low_threshold
            FROM list_items
            WHERE list_id = %s
            AND low_threshold IS NOT NULL
            AND quantity < low_threshold
            ORDER BY name
        """, (list_id,))

        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row['id'],
                'name': row['name'],
                'quantity': row['quantity'],
                'unit': row['unit'],
                'low_threshold': row['low_threshold']
            })
        cursor.close()
        return items
