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
        conn: Database connection (MySQL/MariaDB)
        user_id: Telegram user ID
        list_name: Name of the list
        list_category: Category ('inventory', 'shopping', 'packing')

    Note:
        SQL queries use %s placeholders for MySQL/MariaDB compatibility.
    """

    def __init__(self, conn: Any, user_id: int, list_name: str, list_category: str):
        """
        Initialize the ItemListModule.

        Args:
            conn: Database connection (MySQL/MariaDB)
            user_id: Telegram user ID
            list_name: Name of the list
            list_category: Category ('inventory', 'shopping', 'packing')
        """
        self.conn = conn
        self.db = conn  # Alias for backward compatibility
        self.user_id = user_id
        self._list_name = list_name
        self.list_category = list_category
        self.list_type = list_name  # Alias for backward compatibility

    @property
    def list_name(self) -> str:
        """Get a human-readable name for the list."""
        return self._list_name

    def _ensure_list_exists(self) -> int:
        """
        Ensure a list exists for this user and name, create if needed.

        Returns:
            The list ID
        """
        cursor = self.db.cursor()

        # Check if list exists
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND name = %s",
            (self.user_id, self._list_name)
        )
        row = cursor.fetchone()

        if row:
            return row['id']

        # Create new list
        cursor.execute(
            """
            INSERT INTO lists (user_id, name, list_category)
            VALUES (%s, %s, %s)
            """,
            (self.user_id, self._list_name, self.list_category)
        )
        self.db.commit()
        return cursor.lastrowid

    def _get_list_id(self) -> Optional[int]:
        """
        Get the list ID for this user and name.

        Returns:
            The list ID if it exists, None otherwise
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND name = %s",
            (self.user_id, self._list_name)
        )
        row = cursor.fetchone()
        return row['id'] if row else None

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
            item_id = row['id']
            current_quantity = row['quantity']
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

    def clear_all(self) -> int:
        """
        Remove all items from the list.

        Returns:
            Number of items removed
        """
        list_id = self._get_list_id()
        if not list_id:
            return 0

        cursor = self.db.cursor()
        cursor.execute(
            "DELETE FROM list_items WHERE list_id = %s",
            (list_id,)
        )
        self.db.commit()
        return cursor.rowcount

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
            'id': row['id'],
            'item_name': row['name'],
            'quantity': row['quantity'],
            'unit': row['unit'],
            'notes': row['notes'],
            'checked': row['checked'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
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
                'id': row['id'],
                'item_name': row['name'],
                'quantity': row['quantity'],
                'unit': row['unit'],
                'notes': row['notes'],
                'checked': row['checked'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
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
    def change_category(db: Any, user_id: int, list_name: str, new_category: str) -> bool:
        """
        Move a list to a different category.

        Args:
            db: Database connection
            user_id: Telegram user ID
            list_name: Name of the list to move
            new_category: New category ('inventory', 'shopping', 'packing')

        Returns:
            True if the list was found and updated, False otherwise
        """
        cursor = db.cursor()
        cursor.execute(
            """
            UPDATE lists SET list_category = %s
            WHERE user_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (new_category, user_id, list_name)
        )
        db.commit()
        return cursor.rowcount > 0

    @staticmethod
    def list_all_lists(db: Any, user_id: int, category: Optional[str] = None) -> List[Dict]:
        """
        List all lists for a user, optionally filtered by category.

        Args:
            db: Database connection (MySQL/MariaDB)
            user_id: Telegram user ID
            category: Optional category filter ('inventory', 'shopping', 'packing')

        Returns:
            List of dictionaries with list data
        """
        cursor = db.cursor()

        if category:
            cursor.execute(
                """
                SELECT l.id, l.list_category, l.name, l.created_at,
                       COUNT(li.id) as item_count
                FROM lists l
                LEFT JOIN list_items li ON l.id = li.list_id
                WHERE l.user_id = %s AND l.list_category = %s
                GROUP BY l.id, l.list_category, l.name, l.created_at
                ORDER BY l.name
                """,
                (user_id, category)
            )
        else:
            cursor.execute(
                """
                SELECT l.id, l.list_category, l.name, l.created_at,
                       COUNT(li.id) as item_count
                FROM lists l
                LEFT JOIN list_items li ON l.id = li.list_id
                WHERE l.user_id = %s
                GROUP BY l.id, l.list_category, l.name, l.created_at
                ORDER BY l.list_category, l.name
                """,
                (user_id,)
            )

        lists = []
        for row in cursor.fetchall():
            lists.append({
                'id': row['id'],
                'list_category': row['list_category'],
                'name': row['name'],
                'created_at': row['created_at'],
                'item_count': row['item_count']
            })

        return lists

    @staticmethod
    def create_list(db: Any, user_id: int, name: str, category: str) -> Dict[str, Any]:
        """
        Create a new empty list.

        Args:
            db: Database connection (MySQL/MariaDB)
            user_id: Telegram user ID
            name: List name
            category: Category ('inventory', 'shopping', 'packing')

        Returns:
            Dict with status and message
        """
        cursor = db.cursor()

        # Check if list already exists
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND name = %s",
            (user_id, name)
        )
        if cursor.fetchone():
            return {
                'status': 'exists',
                'message': f"La lista '{name}' ya existe"
            }

        # Create list
        cursor.execute(
            "INSERT INTO lists (user_id, name, list_category) VALUES (%s, %s, %s)",
            (user_id, name, category)
        )
        db.commit()
        return {
            'status': 'created',
            'message': f"Lista '{name}' creada",
            'list_id': cursor.lastrowid
        }

    @staticmethod
    def list_items(db: Any, user_id: int, list_name: str) -> List[Dict[str, Any]]:
        """
        List all items in a specific list by name.

        Args:
            db: Database connection (MySQL/MariaDB)
            user_id: Telegram user ID
            list_name: Name of the list

        Returns:
            List of dictionaries with item data
        """
        cursor = db.cursor()

        # Get list ID
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND name = %s",
            (user_id, list_name)
        )
        row = cursor.fetchone()

        if not row:
            return []

        list_id = row['id']

        # Get all items in list
        cursor.execute(
            """
            SELECT id, name, quantity, unit, notes, checked, recurring, created_at, updated_at
            FROM list_items
            WHERE list_id = %s
            ORDER BY created_at DESC
            """,
            (list_id,)
        )

        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row['id'],
                'name': row['name'],
                'quantity': row['quantity'],
                'unit': row['unit'],
                'notes': row['notes'],
                'checked': row['checked'],
                'recurring': row['recurring'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })

        return items
