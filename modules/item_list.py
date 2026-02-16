"""
ItemListModule - Base class for list-based features.

This module provides the core functionality for managing lists and their items,
serving as the foundation for inventory, shopping lists, and packing lists.
"""
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime


class ItemListModule:
    """
    Base class for managing item lists.

    This class provides CRUD operations for lists and their items,
    with support for quantities, units, and notes.

    Attributes:
        db: SQLite database connection
        list_type: Type of list (e.g., 'inventory', 'shopping', 'packing')
        user_id: Telegram user ID
    """

    def __init__(self, db: sqlite3.Connection, list_type: str, user_id: int):
        """
        Initialize the ItemListModule.

        Args:
            db: SQLite database connection
            list_type: Type of list (e.g., 'inventory', 'shopping', 'packing')
            user_id: Telegram user ID
        """
        self.db = db
        self.list_type = list_type
        self.user_id = user_id

    def _ensure_list_exists(self) -> int:
        """
        Ensure a list exists for this user and type, create if needed.

        Returns:
            The list ID
        """
        cursor = self.db.cursor()

        # Check if list exists
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = ? AND list_type = ?",
            (self.user_id, self.list_type)
        )
        row = cursor.fetchone()

        if row:
            return row[0]

        # Create new list
        cursor.execute(
            """
            INSERT INTO lists (user_id, list_type)
            VALUES (?, ?)
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
            "SELECT id FROM lists WHERE user_id = ? AND list_type = ?",
            (self.user_id, self.list_type)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def add(self, item_name: str, quantity: int = 1, unit: Optional[str] = None,
            notes: Optional[str] = None) -> None:
        """
        Add an item to the list or update quantity if it exists.

        Args:
            item_name: Name of the item
            quantity: Quantity to add (default: 1)
            unit: Unit of measurement (optional)
            notes: Additional notes (optional)
        """
        list_id = self._ensure_list_exists()
        cursor = self.db.cursor()

        # Check if item already exists (case-insensitive)
        cursor.execute(
            """
            SELECT id, quantity FROM list_items
            WHERE list_id = ? AND LOWER(item_name) = LOWER(?)
            """,
            (list_id, item_name)
        )
        row = cursor.fetchone()

        if row:
            # Update existing item
            item_id, current_quantity = row
            new_quantity = current_quantity + quantity
            cursor.execute(
                """
                UPDATE list_items
                SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_quantity, item_id)
            )
        else:
            # Insert new item
            cursor.execute(
                """
                INSERT INTO list_items (list_id, item_name, quantity, unit, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (list_id, item_name, quantity, unit, notes)
            )

        self.db.commit()

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
            WHERE list_id = ? AND LOWER(item_name) = LOWER(?)
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
            SELECT id, item_name, quantity, unit, notes, checked, created_at, updated_at
            FROM list_items
            WHERE list_id = ? AND LOWER(item_name) = LOWER(?)
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
            SELECT id, item_name, quantity, unit, notes, checked, created_at, updated_at
            FROM list_items
            WHERE list_id = ?
            ORDER BY item_name
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
            True if item was updated, False if not found
        """
        list_id = self._get_list_id()
        if not list_id:
            return False

        cursor = self.db.cursor()
        cursor.execute(
            """
            UPDATE list_items
            SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP
            WHERE list_id = ? AND LOWER(item_name) = LOWER(?)
            """,
            (delta, list_id, item_name)
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
            True if item was updated, False if not found
        """
        list_id = self._get_list_id()
        if not list_id:
            return False

        cursor = self.db.cursor()
        cursor.execute(
            """
            UPDATE list_items
            SET quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE list_id = ? AND LOWER(item_name) = LOWER(?)
            """,
            (quantity, list_id, item_name)
        )
        self.db.commit()

        return cursor.rowcount > 0

    @staticmethod
    def list_all_lists(db: sqlite3.Connection, user_id: int) -> List[Dict]:
        """
        List all lists for a user.

        Args:
            db: SQLite database connection
            user_id: Telegram user ID

        Returns:
            List of dictionaries with list data
        """
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT id, list_type, name, created_at, updated_at
            FROM lists
            WHERE user_id = ?
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
    def create_list(db: sqlite3.Connection, user_id: int, list_type: str,
                   name: Optional[str] = None) -> int:
        """
        Explicitly create a new list.

        Args:
            db: SQLite database connection
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
            VALUES (?, ?, ?)
            """,
            (user_id, list_type, name)
        )
        db.commit()
        return cursor.lastrowid
