"""
ItemListModule - Base class for list-based features.

This module provides the core functionality for managing lists and their items,
serving as the foundation for inventory, shopping lists, and packing lists.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime


class ItemListModule:
    """
    Base class for managing item lists.

    This class provides CRUD operations for lists and their items,
    with support for quantities, units, and notes.

    Attributes:
        db: Database connection (SQLite or MySQL/MariaDB)
        list_type: Type of list (e.g., 'inventory', 'shopping', 'packing')
        user_id: Telegram user ID

    Note:
        SQL queries use %s placeholders for MySQL/MariaDB compatibility.
    """

    def __init__(self, db: Any, list_type: str, user_id: int):
        """
        Initialize the ItemListModule.

        Args:
            db: Database connection (MySQL/MariaDB)
            list_type: Type of list (e.g., 'inventory', 'shopping', 'packing')
            user_id: Telegram user ID
        """
        self.db = db
        self.list_type = list_type
        self.user_id = user_id

    @property
    def list_name(self) -> str:
        """Get a human-readable name for the list."""
        return self.list_type

    def _ensure_list_exists(self) -> int:
        """
        Ensure a list exists for this user and type, create if needed.

        Returns:
            The list ID
        """
        cursor = self.db.cursor()

        # Check if list exists
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND list_type = %s",
            (self.user_id, self.list_type)
        )
        row = cursor.fetchone()

        if row:
            return row[0]

        # Create new list
        cursor.execute(
            """
            INSERT INTO lists (user_id, list_type)
            VALUES (%s, %s)
            """,
            (self.user_id, self.list_type)
        )
        self.db.commit()
        return cursor.lastrowid

    def _get_list_id(self) -> Optional[int]:
        """
        Get the list ID for this user and type.

        Returns:
            The list ID if it exists, None otherwise
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND list_type = %s",
            (self.user_id, self.list_type)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def add(self, item_name: str, quantity: float = 1, unit: str = 'unidades', **kwargs) -> Dict[str, Any]:
        """
        Add an item to the list or update quantity if it exists.

        Args:
            item_name: Name of the item
            quantity: Quantity to add (default: 1)
            unit: Unit of measurement (default: 'unidades')
            **kwargs: Additional fields (notes, low_threshold, recurring, etc.)

        Returns:
            Dict with status and message
        """
        if quantity <= 0:
            return {
                'status': 'error',
                'message': 'Cantidad debe ser positiva'
            }

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
            # Update existing item - add to quantity
            item_id, current_quantity = row
            new_quantity = current_quantity + quantity

            # Build UPDATE statement with dynamic fields from kwargs
            update_fields = ['quantity = %s', 'updated_at = CURRENT_TIMESTAMP']
            update_values = [new_quantity]

            # Handle optional fields that might be in kwargs
            if 'recurring' in kwargs:
                update_fields.append('recurring = %s')
                update_values.append(kwargs['recurring'])

            update_values.append(item_id)

            cursor.execute(
                f"""
                UPDATE list_items
                SET {', '.join(update_fields)}
                WHERE id = %s
                """,
                tuple(update_values)
            )
            self.db.commit()
            return {
                'status': 'updated',
                'message': f'Actualizado {item_name}: {new_quantity} {unit}'
            }
        else:
            # Insert new item - build column list based on kwargs
            columns = ['list_id', 'name', 'quantity', 'unit']
            values = [list_id, item_name, quantity, unit]

            # Add optional fields from kwargs
            if 'notes' in kwargs and kwargs['notes'] is not None:
                columns.append('notes')
                values.append(kwargs['notes'])

            if 'low_threshold' in kwargs and kwargs['low_threshold'] is not None:
                columns.append('low_threshold')
                values.append(kwargs['low_threshold'])

            if 'recurring' in kwargs:
                columns.append('recurring')
                values.append(kwargs['recurring'])

            placeholders = ', '.join(['%s'] * len(values))
            column_str = ', '.join(columns)

            cursor.execute(
                f"INSERT INTO list_items ({column_str}) VALUES ({placeholders})",
                tuple(values)
            )
            self.db.commit()
            return {
                'status': 'added',
                'message': f'Añadido {item_name}: {quantity} {unit}'
            }

    def remove(self, item_name: str) -> bool:
        """
        Remove an item from the list.

        Args:
            item_name: Name of the item to remove

        Returns:
            True if item was removed, False if not found
        """
        list_id = self._get_list_id()
        if not list_id:
            return False

        cursor = self.db.cursor()
        cursor.execute(
            """
            DELETE FROM list_items
            WHERE list_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (list_id, item_name)
        )
        self.db.commit()

        return cursor.rowcount > 0

    def get(self, item_name: str) -> Optional[Dict]:
        """
        Get a specific item from the list.

        Args:
            item_name: Name of the item

        Returns:
            Dictionary with item data or None if not found
        """
        list_id = self._get_list_id()
        if not list_id:
            return None

        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT id, name, quantity, unit, notes, checked, created_at, updated_at
            FROM list_items
            WHERE list_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (list_id, item_name)
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            'id': row[0],
            'item_name': row[1],
            'quantity': row[2],
            'unit': row[3],
            'notes': row[4],
            'checked': row[5],
            'created_at': row[6],
            'updated_at': row[7]
        }

    def list_all(self) -> List[Dict]:
        """
        List all items in the list.

        Returns:
            List of dictionaries with item data
        """
        list_id = self._get_list_id()
        if not list_id:
            return []

        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT id, name, quantity, unit, notes, checked, created_at, updated_at
            FROM list_items
            WHERE list_id = %s
            ORDER BY name
            """,
            (list_id,)
        )

        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row[0],
                'item_name': row[1],
                'quantity': row[2],
                'unit': row[3],
                'notes': row[4],
                'checked': row[5],
                'created_at': row[6],
                'updated_at': row[7]
            })

        return items

    def update_quantity(self, item_name: str, delta: int) -> bool:
        """
        Update item quantity by a delta value.

        Args:
            item_name: Name of the item
            delta: Amount to add (positive) or subtract (negative)

        Returns:
            True if item was updated, False if not found or if result would be negative
        """
        list_id = self._get_list_id()
        if not list_id:
            return False

        cursor = self.db.cursor()

        # Check current quantity to prevent negative values
        cursor.execute(
            """
            SELECT quantity FROM list_items
            WHERE list_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (list_id, item_name)
        )
        row = cursor.fetchone()

        if not row:
            return False

        current_quantity = row[0]
        new_quantity = current_quantity + delta

        # Prevent negative quantities
        if new_quantity < 0:
            return False

        cursor.execute(
            """
            UPDATE list_items
            SET quantity = %s, updated_at = CURRENT_TIMESTAMP
            WHERE list_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (new_quantity, list_id, item_name)
        )
        self.db.commit()

        return cursor.rowcount > 0

    def set_quantity(self, item_name: str, quantity: int) -> bool:
        """
        Set item quantity to an absolute value.

        Args:
            item_name: Name of the item
            quantity: New quantity value

        Returns:
            True if item was updated, False if not found or if quantity is negative
        """
        # Prevent negative quantities
        if quantity < 0:
            return False

        list_id = self._get_list_id()
        if not list_id:
            return False

        cursor = self.db.cursor()
        cursor.execute(
            """
            UPDATE list_items
            SET quantity = %s, updated_at = CURRENT_TIMESTAMP
            WHERE list_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (quantity, list_id, item_name)
        )
        self.db.commit()

        return cursor.rowcount > 0

    @staticmethod
    def list_all_lists(db: Any, user_id: int) -> List[Dict]:
        """
        List all lists for a user.

        Args:
            db: Database connection (MySQL/MariaDB)
            user_id: Telegram user ID

        Returns:
            List of dictionaries with list data
        """
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT id, list_type, name, created_at, updated_at
            FROM lists
            WHERE user_id = %s
            ORDER BY list_type
            """,
            (user_id,)
        )

        lists = []
        for row in cursor.fetchall():
            lists.append({
                'id': row[0],
                'list_type': row[1],
                'name': row[2],
                'created_at': row[3],
                'updated_at': row[4]
            })

        return lists

    @staticmethod
    def create_list(db: Any, user_id: int, list_type: str,
                   name: Optional[str] = None) -> int:
        """
        Explicitly create a new list.

        Args:
            db: Database connection (MySQL/MariaDB)
            user_id: Telegram user ID
            list_type: Type of list
            name: Optional list name

        Returns:
            The created list ID
        """
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO lists (user_id, list_type, name)
            VALUES (%s, %s, %s)
            """,
            (user_id, list_type, name)
        )
        db.commit()
        return cursor.lastrowid
