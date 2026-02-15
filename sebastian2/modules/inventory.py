"""
InventoryModule: Manages items the user has at home (pantry/fridge)

Features:
- Add items (increment quantity)
- Set items (absolute quantity)
- Check stock levels
- Threshold warnings for low stock
"""

from typing import Optional, List, Dict, Any
from datetime import datetime


class InventoryModule:
    """Manages user's inventory (items at home)"""

    def __init__(self, connection, user_id: str):
        """
        Initialize InventoryModule

        Args:
            connection: Database connection
            user_id: User identifier
        """
        self.conn = connection
        self.user_id = user_id

    def add(self, item_name: str, quantity: float, unit: str) -> None:
        """
        Add to inventory (increments if exists, creates if new)

        Args:
            item_name: Name of the item
            quantity: Quantity to add
            unit: Unit of measurement (e.g., "unidades", "litros", "kg")
        """
        cursor = self.conn.cursor()

        # Check if item exists
        cursor.execute(
            """
            SELECT quantity FROM inventory
            WHERE user_id = %s AND item_name = %s
            """,
            (self.user_id, item_name)
        )
        result = cursor.fetchone()

        if result:
            # Item exists, increment quantity
            new_quantity = result['quantity'] + quantity
            cursor.execute(
                """
                UPDATE inventory
                SET quantity = %s, unit = %s, updated_at = %s
                WHERE user_id = %s AND item_name = %s
                """,
                (new_quantity, unit, datetime.now(), self.user_id, item_name)
            )
        else:
            # Item doesn't exist, create new entry with default threshold
            cursor.execute(
                """
                INSERT INTO inventory (user_id, item_name, quantity, unit, low_threshold, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (self.user_id, item_name, quantity, unit, 2, datetime.now(), datetime.now())
            )

        self.conn.commit()

    def set(self, item_name: str, quantity: float, unit: str) -> None:
        """
        Set absolute quantity for an item

        Args:
            item_name: Name of the item
            quantity: New absolute quantity
            unit: Unit of measurement
        """
        cursor = self.conn.cursor()

        # Check if item exists
        cursor.execute(
            """
            SELECT id FROM inventory
            WHERE user_id = %s AND item_name = %s
            """,
            (self.user_id, item_name)
        )
        result = cursor.fetchone()

        if result:
            # Update existing item
            cursor.execute(
                """
                UPDATE inventory
                SET quantity = %s, unit = %s, updated_at = %s
                WHERE user_id = %s AND item_name = %s
                """,
                (quantity, unit, datetime.now(), self.user_id, item_name)
            )
        else:
            # Create new item with default threshold
            cursor.execute(
                """
                INSERT INTO inventory (user_id, item_name, quantity, unit, low_threshold, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (self.user_id, item_name, quantity, unit, 2, datetime.now(), datetime.now())
            )

        self.conn.commit()

    def get(self, item_name: str) -> Optional[Dict[str, Any]]:
        """
        Get inventory item details

        Args:
            item_name: Name of the item

        Returns:
            Dictionary with item details or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT item_name, quantity, unit, low_threshold, created_at, updated_at
            FROM inventory
            WHERE user_id = %s AND item_name = %s
            """,
            (self.user_id, item_name)
        )
        result = cursor.fetchone()

        if result:
            return {
                'item_name': result['item_name'],
                'quantity': result['quantity'],
                'unit': result['unit'],
                'threshold': result['low_threshold'],
                'created_at': result['created_at'],
                'updated_at': result['updated_at']
            }
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        """
        List all inventory items for the user

        Returns:
            List of dictionaries containing item details
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT item_name, quantity, unit, low_threshold, created_at, updated_at
            FROM inventory
            WHERE user_id = %s
            ORDER BY item_name
            """,
            (self.user_id,)
        )
        results = cursor.fetchall()

        return [
            {
                'item_name': row['item_name'],
                'quantity': row['quantity'],
                'unit': row['unit'],
                'threshold': row['low_threshold'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
            for row in results
        ]

    def check_threshold(self, item_name: str) -> bool:
        """
        Check if item quantity is at or below threshold

        Args:
            item_name: Name of the item

        Returns:
            True if quantity <= threshold, False otherwise
        """
        item = self.get(item_name)
        if item is None:
            return False

        return item['quantity'] <= item['threshold']

    def set_threshold(self, item_name: str, threshold: float) -> None:
        """
        Set threshold for an item

        Args:
            item_name: Name of the item
            threshold: New threshold value
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE inventory
            SET low_threshold = %s, updated_at = %s
            WHERE user_id = %s AND item_name = %s
            """,
            (threshold, datetime.now(), self.user_id, item_name)
        )
        self.conn.commit()
