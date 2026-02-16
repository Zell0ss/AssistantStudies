# List System Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify inventory/shopping/packing into a single ItemList base class, support multiple named inventories, add quantities to shopping lists, and eliminate auto-trigger complexity.

**Architecture:** Two fundamental types (NoteList unchanged, ItemList unifies inventory/shopping/packing). ItemListModule base class with specialized subclasses for behavior (InventoryModule adds threshold warnings, PackingModule handles recurring flags). Smart defaults for list name resolution without conversational state.

**Tech Stack:** Python 3.11, MySQL, pytest, Anthropic Claude Haiku 4.5 (parser)

**Related Skills:**
- @superpowers:test-driven-development for all code changes
- @superpowers:systematic-debugging if issues arise
- @superpowers:verification-before-completion before marking tasks complete

---

## Phase 1: Database Migration

### Task 1: Create Migration 003 SQL File

**Files:**
- Create: `db/migrations/003_unify_lists.sql`

**Step 1: Write migration SQL**

Create `db/migrations/003_unify_lists.sql`:

```sql
-- Migration 003: Unify list system
-- Adds list_category to lists table and quantity/unit to list_items
-- Migrates inventory table data to unified lists structure

-- Step 1: Add list_category to existing lists table
ALTER TABLE lists ADD COLUMN list_category
  ENUM('inventory', 'shopping', 'packing') DEFAULT 'shopping';

-- Update existing lists based on list_type (if it exists)
UPDATE lists SET list_category =
  CASE
    WHEN list_type = 'shopping' THEN 'shopping'
    WHEN list_type = 'packing' THEN 'packing'
    ELSE 'shopping'
  END;

-- Step 2: Add quantity/unit/threshold to existing list_items
ALTER TABLE list_items
  ADD COLUMN quantity DECIMAL(10,2) DEFAULT 1,
  ADD COLUMN unit VARCHAR(50) DEFAULT 'unidades',
  ADD COLUMN low_threshold DECIMAL(10,2) NULL;

-- Step 3: Migrate inventory table → lists + list_items
-- Create inventory lists (default name: "inventario")
INSERT INTO lists (user_id, name, list_category)
SELECT DISTINCT user_id, 'inventario', 'inventory'
FROM inventory
WHERE NOT EXISTS (
  SELECT 1 FROM lists l
  WHERE l.user_id = inventory.user_id
  AND l.name = 'inventario'
);

-- Migrate inventory items
INSERT INTO list_items (list_id, name, quantity, unit, low_threshold)
SELECT l.id, i.item_name, i.quantity, i.unit, i.low_threshold
FROM inventory i
JOIN lists l ON l.user_id = i.user_id
WHERE l.list_category = 'inventory' AND l.name = 'inventario';

-- Step 4: Rename old inventory table (don't drop yet - safety)
ALTER TABLE inventory RENAME TO inventory_backup;
```

**Step 2: Commit migration file**

```bash
git add db/migrations/003_unify_lists.sql
git commit -m "feat: add database migration 003 for unified list system"
```

---

### Task 2: Create Migration Test

**Files:**
- Create: `tests/test_migration_003.py`

**Step 1: Write failing migration test**

Create `tests/test_migration_003.py`:

```python
"""Tests for migration 003 - unified list system."""
import pytest
from db.connection import get_connection


@pytest.fixture
def db():
    """Get database connection for testing."""
    return get_connection()


def test_lists_table_has_list_category(db):
    """Test that lists table has list_category column after migration."""
    cursor = db.cursor()
    cursor.execute("SHOW COLUMNS FROM lists LIKE 'list_category'")
    result = cursor.fetchone()
    assert result is not None, "list_category column should exist"
    assert 'enum' in result[1].lower(), "list_category should be ENUM type"


def test_list_items_has_quantity_unit(db):
    """Test that list_items has quantity and unit columns."""
    cursor = db.cursor()

    # Check quantity column
    cursor.execute("SHOW COLUMNS FROM list_items LIKE 'quantity'")
    result = cursor.fetchone()
    assert result is not None, "quantity column should exist"

    # Check unit column
    cursor.execute("SHOW COLUMNS FROM list_items LIKE 'unit'")
    result = cursor.fetchone()
    assert result is not None, "unit column should exist"

    # Check low_threshold column
    cursor.execute("SHOW COLUMNS FROM list_items LIKE 'low_threshold'")
    result = cursor.fetchone()
    assert result is not None, "low_threshold column should exist"


def test_inventory_table_renamed(db):
    """Test that inventory table was renamed to inventory_backup."""
    cursor = db.cursor()
    cursor.execute("SHOW TABLES LIKE 'inventory_backup'")
    result = cursor.fetchone()
    assert result is not None, "inventory_backup table should exist"


def test_inventory_data_migrated(db):
    """Test that inventory data was migrated to lists structure."""
    cursor = db.cursor()

    # Check that inventory lists exist
    cursor.execute("""
        SELECT COUNT(*) FROM lists
        WHERE list_category = 'inventory' AND name = 'inventario'
    """)
    count = cursor.fetchone()[0]
    assert count > 0, "Should have at least one inventory list"

    # Check that items were migrated
    cursor.execute("""
        SELECT COUNT(*) FROM list_items li
        JOIN lists l ON li.list_id = l.id
        WHERE l.list_category = 'inventory'
    """)
    count = cursor.fetchone()[0]
    # Should have migrated items (or 0 if no data before)
    assert count >= 0, "Should have migrated inventory items"
```

**Step 2: Run test to verify it fails**

Run: `cd /data/AssistantStudies/sebastian2 && pytest tests/test_migration_003.py -v`

Expected: FAIL - columns don't exist yet, migration not applied

**Step 3: Apply migration manually**

```bash
mysql -u root sebastian_db < db/migrations/003_unify_lists.sql
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration_003.py -v`

Expected: PASS - all migration checks succeed

**Step 5: Commit test**

```bash
git add tests/test_migration_003.py
git commit -m "test: add migration 003 verification tests"
```

---

## Phase 2: Core Infrastructure - ItemListModule

### Task 3: Create ItemListModule Base Class - Part 1 (Basic Operations)

**Files:**
- Create: `modules/item_list.py`
- Create: `tests/test_item_list_module.py`

**Step 1: Write failing test for ItemListModule.add()**

Create `tests/test_item_list_module.py`:

```python
"""Tests for ItemListModule base class."""
import pytest
from db.connection import get_connection
from modules.item_list import ItemListModule


@pytest.fixture
def db():
    """Get test database connection."""
    conn = get_connection()
    yield conn
    # Cleanup test data
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = 'test_user')")
    cursor.execute("DELETE FROM lists WHERE user_id = 'test_user'")
    conn.commit()


def test_add_item_creates_list_and_item(db):
    """Test that add() creates list if it doesn't exist and adds item."""
    module = ItemListModule(db, 'test_user', 'test_list', 'shopping')

    result = module.add('aguacates', quantity=5, unit='unidades')

    assert result['status'] == 'added'
    assert 'aguacates' in result['message']

    # Verify list was created
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, name, list_category FROM lists WHERE user_id = %s AND name = %s",
        ('test_user', 'test_list')
    )
    list_row = cursor.fetchone()
    assert list_row is not None
    assert list_row[1] == 'test_list'
    assert list_row[2] == 'shopping'

    # Verify item was added
    cursor.execute(
        "SELECT name, quantity, unit FROM list_items WHERE list_id = %s",
        (list_row[0],)
    )
    item = cursor.fetchone()
    assert item is not None
    assert item[0] == 'aguacates'
    assert float(item[1]) == 5.0
    assert item[2] == 'unidades'


def test_add_duplicate_item_updates_quantity(db):
    """Test that adding duplicate item updates quantity instead of creating new."""
    module = ItemListModule(db, 'test_user', 'test_list', 'shopping')

    # Add first time
    module.add('leche', quantity=2, unit='litros')

    # Add again
    result = module.add('leche', quantity=1, unit='litros')

    assert result['status'] == 'updated'

    # Verify only one item exists with updated quantity
    cursor = db.cursor()
    cursor.execute("""
        SELECT COUNT(*), SUM(quantity)
        FROM list_items li
        JOIN lists l ON li.list_id = l.id
        WHERE l.user_id = %s AND l.name = %s AND li.name = %s
    """, ('test_user', 'test_list', 'leche'))
    count, total = cursor.fetchone()
    assert count == 1
    assert float(total) == 3.0  # 2 + 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_item_list_module.py::test_add_item_creates_list_and_item -v`

Expected: FAIL - ItemListModule doesn't exist yet

**Step 3: Write minimal ItemListModule implementation**

Create `modules/item_list.py`:

```python
"""Base module for item-based lists (inventory/shopping/packing)."""
from typing import Dict, Any, Optional, List
from loguru import logger


class ItemListModule:
    """Base class for all item-based lists."""

    def __init__(self, conn, user_id: str, list_name: str, list_category: str):
        """
        Initialize ItemListModule.

        Args:
            conn: Database connection
            user_id: User ID
            list_name: Name of the list
            list_category: 'inventory' | 'shopping' | 'packing'
        """
        self.conn = conn
        self.user_id = user_id
        self.list_name = list_name
        self.list_category = list_category
        self._ensure_list_exists()

    def _ensure_list_exists(self):
        """Create list if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND name = %s",
            (self.user_id, self.list_name)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO lists (user_id, name, list_category) VALUES (%s, %s, %s)",
                (self.user_id, self.list_name, self.list_category)
            )
            self.conn.commit()
            logger.info(f"Created {self.list_category} list '{self.list_name}' for user {self.user_id}")

    def _get_list_id(self) -> int:
        """Get the list ID for this user and list name."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM lists WHERE user_id = %s AND name = %s",
            (self.user_id, self.list_name)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def add(self, item_name: str, quantity: float = 1, unit: str = 'unidades', **kwargs) -> Dict[str, Any]:
        """
        Add item to list or update quantity if exists.

        Args:
            item_name: Name of the item
            quantity: Quantity to add
            unit: Unit of measurement
            **kwargs: Additional fields (low_threshold, recurring, etc.)

        Returns:
            Dict with status and message
        """
        if quantity <= 0:
            return {
                'status': 'error',
                'message': 'Cantidad debe ser positiva'
            }

        list_id = self._get_list_id()
        cursor = self.conn.cursor()

        # Check if item already exists
        cursor.execute(
            "SELECT quantity FROM list_items WHERE list_id = %s AND name = %s",
            (list_id, item_name)
        )
        existing = cursor.fetchone()

        if existing:
            # Update quantity (add to existing)
            new_quantity = float(existing[0]) + quantity
            cursor.execute(
                "UPDATE list_items SET quantity = %s, unit = %s WHERE list_id = %s AND name = %s",
                (new_quantity, unit, list_id, item_name)
            )
            self.conn.commit()
            logger.info(f"Updated {item_name}: {quantity} → {new_quantity} {unit}")
            return {
                'status': 'updated',
                'message': f'Actualizado {item_name}: {new_quantity} {unit}'
            }
        else:
            # Insert new item
            # Build column list and values based on kwargs
            columns = ['list_id', 'name', 'quantity', 'unit']
            values = [list_id, item_name, quantity, unit]

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
                values
            )
            self.conn.commit()
            logger.info(f"Added {item_name}: {quantity} {unit} to {self.list_name}")
            return {
                'status': 'added',
                'message': f'Añadido {item_name}: {quantity} {unit}'
            }

    def remove(self, item_name: str) -> bool:
        """
        Remove item from list.

        Args:
            item_name: Name of item to remove

        Returns:
            True if removed, False if not found
        """
        list_id = self._get_list_id()
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM list_items WHERE list_id = %s AND name = %s",
            (list_id, item_name)
        )
        self.conn.commit()
        removed = cursor.rowcount > 0
        if removed:
            logger.info(f"Removed {item_name} from {self.list_name}")
        return removed

    def get(self, item_name: str) -> Optional[Dict[str, Any]]:
        """
        Get item details.

        Args:
            item_name: Name of item

        Returns:
            Dict with item details or None if not found
        """
        list_id = self._get_list_id()
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM list_items WHERE list_id = %s AND name = %s",
            (list_id, item_name)
        )
        return cursor.fetchone()

    def list_all(self) -> List[Dict[str, Any]]:
        """
        List all items in this list.

        Returns:
            List of dicts with item details
        """
        list_id = self._get_list_id()
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM list_items WHERE list_id = %s ORDER BY created_at DESC",
            (list_id,)
        )
        return cursor.fetchall()

    def update_quantity(self, item_name: str, quantity: float) -> Dict[str, Any]:
        """
        Add to existing quantity (alias for add with existing item).

        Args:
            item_name: Name of item
            quantity: Quantity to add (can be negative to subtract)

        Returns:
            Dict with status and message
        """
        item = self.get(item_name)
        if not item:
            return {
                'status': 'error',
                'message': f'Item {item_name} no existe en {self.list_name}'
            }

        new_quantity = float(item['quantity']) + quantity

        if new_quantity <= 0:
            # Remove item if quantity drops to zero or below
            self.remove(item_name)
            return {
                'status': 'removed',
                'message': f'Eliminado {item_name} (cantidad llegó a {new_quantity})'
            }

        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE list_items SET quantity = %s WHERE list_id = %s AND name = %s",
            (new_quantity, self._get_list_id(), item_name)
        )
        self.conn.commit()
        logger.info(f"Updated {item_name} quantity: {item['quantity']} → {new_quantity}")
        return {
            'status': 'updated',
            'message': f'Actualizado {item_name}: {new_quantity} {item["unit"]}'
        }

    def set_quantity(self, item_name: str, quantity: float) -> Dict[str, Any]:
        """
        Set absolute quantity (replace, not add).

        Args:
            item_name: Name of item
            quantity: New absolute quantity

        Returns:
            Dict with status and message
        """
        if quantity <= 0:
            # Remove item if setting to zero or negative
            self.remove(item_name)
            return {
                'status': 'removed',
                'message': f'Eliminado {item_name}'
            }

        item = self.get(item_name)
        if not item:
            return {
                'status': 'error',
                'message': f'Item {item_name} no existe en {self.list_name}'
            }

        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE list_items SET quantity = %s WHERE list_id = %s AND name = %s",
            (quantity, self._get_list_id(), item_name)
        )
        self.conn.commit()
        logger.info(f"Set {item_name} quantity to {quantity} {item['unit']}")
        return {
            'status': 'updated',
            'message': f'{item_name}: {quantity} {item["unit"]}'
        }

    @staticmethod
    def list_all_lists(conn, user_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all lists for a user, optionally filtered by category.

        Args:
            conn: Database connection
            user_id: User ID
            category: Optional category filter

        Returns:
            List of dicts with list details
        """
        cursor = conn.cursor(dictionary=True)
        if category:
            cursor.execute(
                "SELECT * FROM lists WHERE user_id = %s AND list_category = %s ORDER BY name",
                (user_id, category)
            )
        else:
            cursor.execute(
                "SELECT * FROM lists WHERE user_id = %s ORDER BY list_category, name",
                (user_id,)
            )
        return cursor.fetchall()

    @staticmethod
    def create_list(conn, user_id: str, name: str, category: str) -> Dict[str, Any]:
        """
        Create a new empty list.

        Args:
            conn: Database connection
            user_id: User ID
            name: List name
            category: 'inventory' | 'shopping' | 'packing'

        Returns:
            Dict with status and message
        """
        cursor = conn.cursor()

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
        conn.commit()
        logger.info(f"Created {category} list '{name}' for user {user_id}")
        return {
            'status': 'created',
            'message': f"Lista '{name}' creada"
        }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_item_list_module.py -v`

Expected: PASS - both tests pass

**Step 5: Commit**

```bash
git add modules/item_list.py tests/test_item_list_module.py
git commit -m "feat: add ItemListModule base class with core operations"
```

---

### Task 4: Add More ItemListModule Tests

**Files:**
- Modify: `tests/test_item_list_module.py`

**Step 1: Write additional tests**

Add to `tests/test_item_list_module.py`:

```python
def test_remove_item(db):
    """Test that remove() deletes item from list."""
    module = ItemListModule(db, 'test_user', 'test_list', 'shopping')
    module.add('pan', quantity=1)

    removed = module.remove('pan')

    assert removed is True
    assert module.get('pan') is None


def test_remove_nonexistent_item(db):
    """Test that removing nonexistent item returns False."""
    module = ItemListModule(db, 'test_user', 'test_list', 'shopping')

    removed = module.remove('nonexistent')

    assert removed is False


def test_get_item(db):
    """Test that get() retrieves item details."""
    module = ItemListModule(db, 'test_user', 'test_list', 'shopping')
    module.add('tomates', quantity=3, unit='kg')

    item = module.get('tomates')

    assert item is not None
    assert item['name'] == 'tomates'
    assert float(item['quantity']) == 3.0
    assert item['unit'] == 'kg'


def test_list_all_items(db):
    """Test that list_all() returns all items in list."""
    module = ItemListModule(db, 'test_user', 'test_list', 'shopping')
    module.add('item1', quantity=1)
    module.add('item2', quantity=2)
    module.add('item3', quantity=3)

    items = module.list_all()

    assert len(items) == 3
    item_names = {item['name'] for item in items}
    assert item_names == {'item1', 'item2', 'item3'}


def test_update_quantity(db):
    """Test that update_quantity() adds to existing quantity."""
    module = ItemListModule(db, 'test_user', 'test_list', 'inventory')
    module.add('aguacates', quantity=5)

    result = module.update_quantity('aguacates', -2)  # Remove 2

    assert result['status'] == 'updated'
    item = module.get('aguacates')
    assert float(item['quantity']) == 3.0


def test_update_quantity_to_zero_removes_item(db):
    """Test that updating quantity to zero removes the item."""
    module = ItemListModule(db, 'test_user', 'test_list', 'inventory')
    module.add('aguacates', quantity=2)

    result = module.update_quantity('aguacates', -2)

    assert result['status'] == 'removed'
    assert module.get('aguacates') is None


def test_set_quantity(db):
    """Test that set_quantity() replaces quantity (not adds)."""
    module = ItemListModule(db, 'test_user', 'test_list', 'inventory')
    module.add('leche', quantity=5)

    result = module.set_quantity('leche', 2)

    assert result['status'] == 'updated'
    item = module.get('leche')
    assert float(item['quantity']) == 2.0  # Set to 2, not 5+2


def test_list_all_lists(db):
    """Test static method to list all user's lists."""
    # Create multiple lists
    ItemListModule(db, 'test_user', 'list1', 'shopping')
    ItemListModule(db, 'test_user', 'list2', 'inventory')
    ItemListModule(db, 'test_user', 'list3', 'packing')

    all_lists = ItemListModule.list_all_lists(db, 'test_user')

    assert len(all_lists) == 3
    list_names = {lst['name'] for lst in all_lists}
    assert list_names == {'list1', 'list2', 'list3'}


def test_list_all_lists_filtered_by_category(db):
    """Test listing lists filtered by category."""
    ItemListModule(db, 'test_user', 'mercadona', 'shopping')
    ItemListModule(db, 'test_user', 'despensa', 'inventory')
    ItemListModule(db, 'test_user', 'carrefour', 'shopping')

    shopping_lists = ItemListModule.list_all_lists(db, 'test_user', category='shopping')

    assert len(shopping_lists) == 2
    list_names = {lst['name'] for lst in shopping_lists}
    assert list_names == {'mercadona', 'carrefour'}


def test_create_list_static_method(db):
    """Test static create_list method."""
    result = ItemListModule.create_list(db, 'test_user', 'new_list', 'shopping')

    assert result['status'] == 'created'

    # Verify list exists
    cursor = db.cursor()
    cursor.execute(
        "SELECT name, list_category FROM lists WHERE user_id = %s AND name = %s",
        ('test_user', 'new_list')
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 'new_list'
    assert row[1] == 'shopping'
```

**Step 2: Run tests**

Run: `pytest tests/test_item_list_module.py -v`

Expected: PASS - all tests pass (implementation already supports these)

**Step 3: Commit**

```bash
git add tests/test_item_list_module.py
git commit -m "test: add comprehensive tests for ItemListModule"
```

---

## Phase 3: Specialized Modules

### Task 5: Create InventoryModule with Threshold Warnings

**Files:**
- Create: `modules/inventory_new.py` (will replace old inventory.py later)
- Create: `tests/test_inventory_new.py`

**Step 1: Write failing test for threshold warnings**

Create `tests/test_inventory_new.py`:

```python
"""Tests for new InventoryModule with threshold warnings."""
import pytest
from db.connection import get_connection
from modules.inventory_new import InventoryModule


@pytest.fixture
def db():
    """Get test database connection."""
    conn = get_connection()
    yield conn
    # Cleanup
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = 'test_user')")
    cursor.execute("DELETE FROM lists WHERE user_id = 'test_user'")
    conn.commit()


def test_add_with_threshold_no_warning(db):
    """Test that adding item above threshold doesn't warn."""
    inv = InventoryModule(db, 'test_user', 'despensa', 'inventory')

    result = inv.add('aguacates', quantity=5, threshold=2)

    assert result['status'] == 'added'
    assert 'warning' not in result or result['warning'] is False


def test_add_with_quantity_below_threshold_warns(db):
    """Test that adding item below threshold triggers warning."""
    inv = InventoryModule(db, 'test_user', 'despensa', 'inventory')

    result = inv.add('aguacates', quantity=1, threshold=2)

    assert result['status'] == 'added'
    assert result['warning'] is True
    assert '⚠️' in result['message']
    assert 'poco' in result['message'].lower()


def test_update_quantity_below_threshold_warns(db):
    """Test that updating to below threshold triggers warning."""
    inv = InventoryModule(db, 'test_user', 'despensa', 'inventory')
    inv.add('leche', quantity=5, threshold=2)

    result = inv.update_quantity('leche', -4)  # 5 - 4 = 1 (below threshold 2)

    assert result['warning'] is True
    assert '⚠️' in result['message']


def test_check_low_stock(db):
    """Test check_low_stock returns items below threshold."""
    inv = InventoryModule(db, 'test_user', 'despensa', 'inventory')
    inv.add('item1', quantity=1, threshold=2)  # Low
    inv.add('item2', quantity=5, threshold=2)  # OK
    inv.add('item3', quantity=1, threshold=3)  # Low

    low_items = inv.check_low_stock()

    assert len(low_items) == 2
    low_names = {item['name'] for item in low_items}
    assert low_names == {'item1', 'item3'}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_inventory_new.py -v`

Expected: FAIL - InventoryModule doesn't exist

**Step 3: Implement InventoryModule**

Create `modules/inventory_new.py`:

```python
"""Inventory module with threshold warning support."""
from typing import Dict, Any, List
from modules.item_list import ItemListModule
from loguru import logger


class InventoryModule(ItemListModule):
    """Extends ItemListModule with threshold warnings for low stock."""

    def add(self, item_name: str, quantity: float = 1, unit: str = 'unidades',
            threshold: float = 2, **kwargs) -> Dict[str, Any]:
        """
        Add item to inventory with threshold.

        Args:
            item_name: Name of item
            quantity: Quantity to add
            unit: Unit of measurement
            threshold: Low stock threshold (default 2)
            **kwargs: Additional fields

        Returns:
            Dict with status, message, and warning flag
        """
        # Call parent add() with threshold
        result = super().add(item_name, quantity, unit, low_threshold=threshold, **kwargs)

        # Check if we should warn
        warning = self._check_and_warn(item_name)
        result.update(warning)

        return result

    def update_quantity(self, item_name: str, quantity: float) -> Dict[str, Any]:
        """
        Update quantity and check threshold.

        Args:
            item_name: Name of item
            quantity: Quantity to add (can be negative)

        Returns:
            Dict with status, message, and warning flag
        """
        result = super().update_quantity(item_name, quantity)

        # Only check warning if item still exists (wasn't removed)
        if result['status'] != 'removed':
            warning = self._check_and_warn(item_name)
            result.update(warning)

        return result

    def set_quantity(self, item_name: str, quantity: float) -> Dict[str, Any]:
        """
        Set absolute quantity and check threshold.

        Args:
            item_name: Name of item
            quantity: New absolute quantity

        Returns:
            Dict with status, message, and warning flag
        """
        result = super().set_quantity(item_name, quantity)

        # Only check warning if item still exists
        if result['status'] != 'removed':
            warning = self._check_and_warn(item_name)
            result.update(warning)

        return result

    def _check_and_warn(self, item_name: str) -> Dict[str, Any]:
        """
        Check if item is below threshold and return warning.

        Args:
            item_name: Name of item to check

        Returns:
            Dict with warning flag and updated message
        """
        item = self.get(item_name)

        if not item:
            return {'warning': False}

        quantity = float(item['quantity'])
        threshold = item.get('low_threshold')

        if threshold is not None and quantity < threshold:
            warning_msg = f"⚠️ Te queda poco {item_name} ({quantity} {item['unit']}). Piensa en comprar."
            logger.warning(f"Low stock: {item_name} = {quantity} (threshold: {threshold})")
            return {
                'warning': True,
                'message': warning_msg
            }

        return {'warning': False}

    def check_low_stock(self) -> List[Dict[str, Any]]:
        """
        Get all items with quantity below threshold.

        Returns:
            List of items with low stock
        """
        list_id = self._get_list_id()
        cursor = self.conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM list_items
            WHERE list_id = %s
            AND low_threshold IS NOT NULL
            AND quantity < low_threshold
            ORDER BY name
        """, (list_id,))

        return cursor.fetchall()
```

**Step 4: Run tests**

Run: `pytest tests/test_inventory_new.py -v`

Expected: PASS - all tests pass

**Step 5: Commit**

```bash
git add modules/inventory_new.py tests/test_inventory_new.py
git commit -m "feat: add InventoryModule with threshold warnings"
```

---

### Task 6: Create ShoppingModule and PackingModule

**Files:**
- Create: `modules/shopping_new.py`
- Create: `modules/packing_new.py`
- Create: `tests/test_shopping_new.py`
- Create: `tests/test_packing_new.py`

**Step 1: Write test for ShoppingModule**

Create `tests/test_shopping_new.py`:

```python
"""Tests for new ShoppingModule."""
import pytest
from db.connection import get_connection
from modules.shopping_new import ShoppingModule


@pytest.fixture
def db():
    """Get test database connection."""
    conn = get_connection()
    yield conn
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = 'test_user')")
    cursor.execute("DELETE FROM lists WHERE user_id = 'test_user'")
    conn.commit()


def test_shopping_module_inherits_itemlist(db):
    """Test that ShoppingModule has all ItemListModule functionality."""
    shop = ShoppingModule(db, 'test_user', 'mercadona', 'shopping')

    # Should be able to add with quantity
    result = shop.add('pan', quantity=2, unit='unidades')
    assert result['status'] == 'added'

    item = shop.get('pan')
    assert item is not None
    assert float(item['quantity']) == 2.0
```

**Step 2: Implement ShoppingModule**

Create `modules/shopping_new.py`:

```python
"""Shopping module - inherits from ItemListModule."""
from modules.item_list import ItemListModule


class ShoppingModule(ItemListModule):
    """
    Shopping lists module.

    Currently identical to ItemListModule base class.
    Reserved for future shopping-specific features:
    - bulk_transfer_to_inventory()
    - mark_as_bought() with different behavior than remove()
    """
    pass
```

**Step 3: Write test for PackingModule**

Create `tests/test_packing_new.py`:

```python
"""Tests for new PackingModule."""
import pytest
from db.connection import get_connection
from modules.packing_new import PackingModule


@pytest.fixture
def db():
    """Get test database connection."""
    conn = get_connection()
    yield conn
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = 'test_user')")
    cursor.execute("DELETE FROM lists WHERE user_id = 'test_user'")
    conn.commit()


def test_add_recurring_item(db):
    """Test adding item with recurring flag."""
    pack = PackingModule(db, 'test_user', 'gijón', 'packing')

    result = pack.add('cepillo', quantity=1, recurring=True)

    assert result['status'] == 'added'
    item = pack.get('cepillo')
    assert item['recurring'] is True


def test_add_non_recurring_item(db):
    """Test adding normal (non-recurring) item."""
    pack = PackingModule(db, 'test_user', 'gijón', 'packing')

    result = pack.add('toalla', quantity=1, recurring=False)

    assert result['status'] == 'added'
    item = pack.get('toalla')
    assert item['recurring'] is False


def test_check_item_removes_non_recurring(db):
    """Test that checking non-recurring item removes it."""
    pack = PackingModule(db, 'test_user', 'gijón', 'packing')
    pack.add('toalla', quantity=1, recurring=False)

    result = pack.check_item('toalla')

    assert result['status'] == 'checked'
    assert pack.get('toalla') is None  # Should be removed


def test_check_item_keeps_recurring(db):
    """Test that checking recurring item keeps it in list."""
    pack = PackingModule(db, 'test_user', 'gijón', 'packing')
    pack.add('cepillo', quantity=1, recurring=True)

    result = pack.check_item('cepillo')

    assert result['status'] == 'checked'
    assert pack.get('cepillo') is not None  # Should still exist
```

**Step 4: Implement PackingModule**

Create `modules/packing_new.py`:

```python
"""Packing module with recurring items support."""
from typing import Dict, Any
from modules.item_list import ItemListModule
from loguru import logger


class PackingModule(ItemListModule):
    """Packing lists module with recurring items support."""

    def add(self, item_name: str, quantity: float = 1, unit: str = 'unidades',
            recurring: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Add item to packing list with optional recurring flag.

        Args:
            item_name: Name of item
            quantity: Quantity
            unit: Unit of measurement
            recurring: True if item should stay after checking
            **kwargs: Additional fields

        Returns:
            Dict with status and message
        """
        return super().add(item_name, quantity, unit, recurring=recurring, **kwargs)

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
            logger.info(f"Checked recurring item {item_name} in {self.list_name}")
            return {
                'status': 'checked',
                'message': f'✅ {item_name} marcado (se mantiene en lista)'
            }
        else:
            # Remove non-recurring items
            self.remove(item_name)
            logger.info(f"Checked and removed {item_name} from {self.list_name}")
            return {
                'status': 'checked',
                'message': f'✅ {item_name} empacado y eliminado de lista'
            }
```

**Step 5: Run tests**

Run: `pytest tests/test_shopping_new.py tests/test_packing_new.py -v`

Expected: PASS - all tests pass

**Step 6: Commit**

```bash
git add modules/shopping_new.py modules/packing_new.py tests/test_shopping_new.py tests/test_packing_new.py
git commit -m "feat: add ShoppingModule and PackingModule with recurring items"
```

---

## Phase 4: Router Updates

### Task 7: Add Smart Defaults to Router

**Files:**
- Modify: `core/router.py`
- Create: `tests/test_router_smart_defaults.py`

**Step 1: Write failing test for smart defaults**

Create `tests/test_router_smart_defaults.py`:

```python
"""Tests for router smart defaults functionality."""
import pytest
from db.connection import get_connection
from core.router import Router
from modules.item_list import ItemListModule


@pytest.fixture
def db():
    """Get test database connection."""
    conn = get_connection()
    yield conn
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = 'test_user')")
    cursor.execute("DELETE FROM lists WHERE user_id = 'test_user'")
    conn.commit()


def test_smart_default_single_list_auto_selects(db):
    """Test that router auto-selects when user has only 1 list of that category."""
    # Create only one inventory list
    ItemListModule.create_list(db, 'test_user', 'despensa', 'inventory')

    router = Router(db, 'test_user')

    # Parse without list_name
    intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'aguacates',
        'quantity': 5,
        'list_name': None  # Not specified
    }

    result = router.route(intent)

    assert result['success'] is True
    # Should have auto-selected 'despensa'


def test_smart_default_multiple_lists_returns_error(db):
    """Test that router returns error when user has multiple lists and doesn't specify."""
    # Create multiple inventory lists
    ItemListModule.create_list(db, 'test_user', 'despensa', 'inventory')
    ItemListModule.create_list(db, 'test_user', 'nevera', 'inventory')

    router = Router(db, 'test_user')

    intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'aguacates',
        'quantity': 5,
        'list_name': None
    }

    result = router.route(intent)

    assert result['success'] is False
    assert '¿A qué lista?' in result['result']
    assert 'despensa' in result['result']
    assert 'nevera' in result['result']


def test_explicit_list_name_bypasses_smart_default(db):
    """Test that explicit list_name always works."""
    ItemListModule.create_list(db, 'test_user', 'despensa', 'inventory')
    ItemListModule.create_list(db, 'test_user', 'nevera', 'inventory')

    router = Router(db, 'test_user')

    intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'aguacates',
        'quantity': 5,
        'list_name': 'despensa'  # Explicit
    }

    result = router.route(intent)

    assert result['success'] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_router_smart_defaults.py -v`

Expected: FAIL - router doesn't have smart defaults yet

**Step 3: Update router with smart defaults**

Modify `core/router.py` - add this method and update route():

```python
# Add this import at the top
from modules.item_list import ItemListModule
from modules.inventory_new import InventoryModule
from modules.shopping_new import ShoppingModule
from modules.packing_new import PackingModule

# Add this method to Router class
def _resolve_list_name(self, module: str, list_name: Optional[str]) -> Optional[str]:
    """
    Resolve list name using smart defaults.

    - If list_name is provided → use it
    - If user has only 1 list of that category → auto-select
    - If user has 2+ lists → return None (caller should error)

    Args:
        module: Module name (inventory, shopping, packing)
        list_name: User-provided list name (or None)

    Returns:
        Resolved list name or None if ambiguous
    """
    if list_name:
        return list_name  # Explicit name provided

    # Map module to category
    category_map = {
        'inventory': 'inventory',
        'shopping': 'shopping',
        'packing': 'packing'
    }
    category = category_map.get(module)

    if not category:
        return None

    # Get user's lists for this category
    lists = ItemListModule.list_all_lists(self.conn, self.user_id, category=category)

    if len(lists) == 0:
        # No lists yet - will be created on demand
        # Use default names
        defaults = {
            'inventory': 'inventario',
            'shopping': 'compra',
            'packing': 'equipaje'
        }
        return defaults.get(category)
    elif len(lists) == 1:
        # Auto-select the only list
        return lists[0]['name']
    else:
        # Ambiguous - multiple lists
        return None

def _build_list_options_error(self, module: str) -> Dict[str, Any]:
    """
    Build error message with list of available lists.

    Args:
        module: Module name

    Returns:
        Error dict with list options
    """
    category_map = {
        'inventory': 'inventory',
        'shopping': 'shopping',
        'packing': 'packing'
    }
    category = category_map.get(module)

    lists = ItemListModule.list_all_lists(self.conn, self.user_id, category=category)
    list_names = [lst['name'] for lst in lists]

    return {
        'success': False,
        'result': f"¿A qué lista? Tienes: {', '.join(list_names)}"
    }

# Update the route() method to use smart defaults
def route(self, parsed_intent):
    """Route parsed intent to appropriate module."""
    module = parsed_intent.get('module')
    action = parsed_intent.get('action')
    list_name = parsed_intent.get('list_name')

    # Resolve list name with smart defaults
    if module in ['inventory', 'shopping', 'packing']:
        resolved_name = self._resolve_list_name(module, list_name)
        if resolved_name is None and list_name is None:
            # Ambiguous - return error with options
            return self._build_list_options_error(module)
        list_name = resolved_name

    # ... rest of routing logic (keep existing code)
```

**Step 4: Run tests**

Run: `pytest tests/test_router_smart_defaults.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add core/router.py tests/test_router_smart_defaults.py
git commit -m "feat: add smart defaults for list name resolution in router"
```

---

### Task 8: Update Router to Use New Modules

**Files:**
- Modify: `core/router.py`

**Step 1: Update router route() method to use new modules**

Replace the inventory/shopping/packing sections in `route()` method:

```python
def route(self, parsed_intent):
    """Route parsed intent to appropriate module."""
    module = parsed_intent.get('module')
    action = parsed_intent.get('action')

    # Handle system commands
    if module == 'system':
        return {
            'success': True,
            'result': parsed_intent.get('message', 'Sistema listo.')
        }

    # Get list_name with smart defaults
    list_name = parsed_intent.get('list_name')
    if module in ['inventory', 'shopping', 'packing']:
        resolved_name = self._resolve_list_name(module, list_name)
        if resolved_name is None and list_name is None:
            return self._build_list_options_error(module)
        list_name = resolved_name

    # Route to inventory
    if module == 'inventory':
        inv = InventoryModule(self.conn, self.user_id, list_name, 'inventory')

        if action == 'add':
            item = parsed_intent.get('item')
            quantity = parsed_intent.get('quantity', 1)
            unit = parsed_intent.get('unit', 'unidades')
            threshold = parsed_intent.get('threshold', 2)
            result = inv.add(item, quantity, unit, threshold)

            # Format response with warning if present
            if result.get('warning'):
                return {
                    'success': True,
                    'result': f"{result['message']}"
                }
            return {
                'success': True,
                'result': result['message']
            }

        elif action == 'set':
            item = parsed_intent.get('item')
            quantity = parsed_intent.get('quantity', 1)
            result = inv.set_quantity(item, quantity)

            if result.get('warning'):
                return {
                    'success': True,
                    'result': f"{result['message']}"
                }
            return {
                'success': True,
                'result': result['message']
            }

        elif action == 'get':
            item = parsed_intent.get('item')
            item_data = inv.get(item)
            if item_data:
                return {
                    'success': True,
                    'result': f"{item_data['name']}: {item_data['quantity']} {item_data['unit']}"
                }
            return {
                'success': False,
                'result': f"No tienes {item} en {list_name}"
            }

        elif action == 'list':
            items = inv.list_all()
            if items:
                item_list = '\n'.join([
                    f"• **{item['name']}**: {item['quantity']} {item['unit']}"
                    for item in items
                ])
                return {
                    'success': True,
                    'result': f"**{list_name}** ({len(items)} items):\n{item_list}",
                    'data': items
                }
            return {
                'success': True,
                'result': f"Lista {list_name} vacía.",
                'data': {'empty': True}
            }

        elif action == 'remove':
            item = parsed_intent.get('item')
            removed = inv.remove(item)
            if removed:
                return {
                    'success': True,
                    'result': f"Eliminado {item} de {list_name}."
                }
            return {
                'success': False,
                'result': f"{item} no está en {list_name}."
            }

        elif action == 'check_low_stock':
            low_items = inv.check_low_stock()
            if low_items:
                item_list = '\n'.join([
                    f"• **{item['name']}**: {item['quantity']} {item['unit']} (min: {item['low_threshold']})"
                    for item in low_items
                ])
                return {
                    'success': True,
                    'result': f"⚠️ Items con stock bajo en {list_name}:\n{item_list}"
                }
            return {
                'success': True,
                'result': f"Todo bien en {list_name}. No hay items con stock bajo."
            }

    # Route to shopping
    elif module == 'shopping':
        shop = ShoppingModule(self.conn, self.user_id, list_name, 'shopping')

        if action == 'create':
            result = ItemListModule.create_list(self.conn, self.user_id, list_name, 'shopping')
            return {
                'success': result['status'] == 'created',
                'result': result['message']
            }

        elif action == 'add':
            item = parsed_intent.get('item')
            quantity = parsed_intent.get('quantity', 1)
            unit = parsed_intent.get('unit', 'unidades')
            result = shop.add(item, quantity, unit)
            return {
                'success': True,
                'result': result['message']
            }

        elif action == 'remove':
            item = parsed_intent.get('item')
            removed = shop.remove(item)
            if removed:
                return {
                    'success': True,
                    'result': f"Eliminado {item} de {list_name}."
                }
            return {
                'success': False,
                'result': f"{item} no está en {list_name}."
            }

        elif action == 'list':
            items = shop.list_all()
            if items:
                item_list = '\n'.join([
                    f"• **{item['name']}**: {item['quantity']} {item['unit']}"
                    for item in items
                ])
                return {
                    'success': True,
                    'result': f"**{list_name}** ({len(items)} items):\n{item_list}",
                    'data': items
                }
            return {
                'success': True,
                'result': f"Lista {list_name} vacía.",
                'data': {'empty': True}
            }

        elif action == 'list_all_lists':
            lists = ItemListModule.list_all_lists(self.conn, self.user_id, category='shopping')
            if lists:
                list_names = '\n'.join([f"• {lst['name']}" for lst in lists])
                return {
                    'success': True,
                    'result': f"**Listas de compra:**\n{list_names}"
                }
            return {
                'success': True,
                'result': "No tienes listas de compra aún."
            }

    # Route to packing
    elif module == 'packing':
        pack = PackingModule(self.conn, self.user_id, list_name, 'packing')

        if action == 'add':
            item = parsed_intent.get('item')
            quantity = parsed_intent.get('quantity', 1)
            unit = parsed_intent.get('unit', 'unidades')
            recurring = parsed_intent.get('recurring', False)
            result = pack.add(item, quantity, unit, recurring)
            return {
                'success': True,
                'result': result['message']
            }

        elif action == 'check':
            item = parsed_intent.get('item')
            result = pack.check_item(item)
            return {
                'success': result['status'] != 'error',
                'result': result['message']
            }

        elif action == 'list':
            items = pack.list_all()
            if items:
                item_list = '\n'.join([
                    f"• **{item['name']}**: {item['quantity']} {item['unit']}" +
                    (" 🔄" if item['recurring'] else "")
                    for item in items
                ])
                return {
                    'success': True,
                    'result': f"**{list_name}** ({len(items)} items):\n{item_list}",
                    'data': items
                }
            return {
                'success': True,
                'result': f"Lista {list_name} vacía.",
                'data': {'empty': True}
            }

    # Route to notes (unchanged)
    elif module == 'notes':
        # Keep existing notes logic
        pass

    # Unknown module/action
    return {
        'success': False,
        'result': f"Acción '{action}' desconocida para módulo '{module}'"
    }
```

**Step 2: Test router updates**

Run existing router tests:

Run: `pytest tests/test_router.py -v`

Expected: Some tests may need updates (old inventory behavior changed)

**Step 3: Update failing router tests**

Update tests in `tests/test_router.py` to expect new module behavior (warnings, quantities, etc.)

**Step 4: Commit**

```bash
git add core/router.py tests/test_router.py
git commit -m "feat: update router to use new unified list modules"
```

---

## Phase 5: Parser Updates

### Task 9: Update Parser for List Name Extraction

**Files:**
- Modify: `core/haiku_parser.py`
- Create: `tests/test_parser_list_names.py`

**Step 1: Write parser test for list name extraction**

Create `tests/test_parser_list_names.py`:

```python
"""Tests for parser list name extraction."""
import pytest
from core.haiku_parser import HaikuParser


@pytest.fixture
def parser():
    """Get parser instance."""
    return HaikuParser()


def test_extract_inventory_list_name(parser):
    """Test parser extracts inventory list names."""
    result = parser.parse("añade aguacates a despensa de madrid")

    assert result['module'] == 'inventory'
    assert result['action'] == 'add'
    assert result['item'] == 'aguacates'
    assert result['list_name'] == 'despensa madrid' or 'despensa' in result['list_name']


def test_extract_shopping_list_name(parser):
    """Test parser extracts shopping list names."""
    result = parser.parse("añade pan a mercadona")

    assert result['module'] == 'shopping'
    assert result['action'] == 'add'
    assert result['item'] == 'pan'
    assert result['list_name'] == 'mercadona'


def test_default_compra_for_shopping(parser):
    """Test parser defaults to 'compra' for generic shopping."""
    result = parser.parse("añade leche a la compra")

    assert result['module'] == 'shopping'
    assert result['list_name'] == 'compra'


def test_no_list_name_returns_null(parser):
    """Test parser returns null list_name when not specified."""
    result = parser.parse("qué tengo en mi inventario")

    assert result['module'] == 'inventory'
    assert result['action'] == 'list'
    # list_name should be null or not present
    assert result.get('list_name') is None or result.get('list_name') == ''


def test_extract_quantity_with_list_name(parser):
    """Test parser extracts both quantity and list name."""
    result = parser.parse("añade 3 kg de arroz a despensa madrid")

    assert result['item'] == 'arroz'
    assert result['quantity'] == 3
    assert result['unit'] == 'kg'
    assert 'despensa' in result.get('list_name', '').lower() or 'madrid' in result.get('list_name', '').lower()
```

**Step 2: Run test to see current parser behavior**

Run: `pytest tests/test_parser_list_names.py -v`

Expected: May FAIL - parser may not extract list_name correctly yet

**Step 3: Update parser system prompt**

Modify `core/haiku_parser.py` - update the system_prompt:

```python
system_prompt = """Eres un asistente que parsea mensajes en español a JSON estructurado.

El usuario puede pedir operaciones sobre:
- **inventory**: inventario de items en casa (aguacates, leche, etc.)
  - Puede tener múltiples inventarios nombrados: "despensa madrid", "nevera gijón", "despensa magán"
- **shopping**: listas de compra (compra, mercadona, carrefour, etc.) - items a comprar
  - Múltiples listas nombradas por tienda
- **packing**: listas de empaque para viajes (gijón, madrid, playa, etc.)
  - Múltiples listas nombradas por destino
- **notes**: notas de texto libre con tags

IMPORTANTE - Extracción de list_name:
El usuario tiene múltiples listas nombradas. Debes extraer el nombre de la lista del mensaje:

Ejemplos de nombres de listas:
- inventory: "despensa madrid", "nevera gijón", "despensa magán", "inventario"
- shopping: "compra", "mercadona", "carrefour", "lidl"
- packing: "gijón", "madrid", "playa"

Reglas para list_name:
- Si el usuario menciona un nombre específico → extraerlo exactamente
- Si dice "la compra" sin otro nombre → list_name: "compra"
- Si dice "inventario" sin nombre específico → list_name: null
- Si no menciona lista → list_name: null

Acciones posibles:
- **add**: añadir/agregar cantidad (inventory) o item (lists)
- **set**: establecer cantidad absoluta (inventory)
- **remove**: quitar/eliminar item
- **create**: crear una lista vacía (solo shopping)
- **list**: listar/mostrar items de UNA lista
- **list_all_lists**: listar TODAS las listas de compra disponibles
- **check**: marcar como hecho (packing lists)
- **check_low_stock**: ver items con stock bajo (inventory)
- **search**: buscar notas
- **get**: obtener cantidad/info de un item

Devuelve SOLO JSON válido con esta estructura:
{
  "module": "inventory | shopping | packing | notes",
  "action": "add | set | remove | create | list | list_all_lists | check | check_low_stock | search | get",
  "item": "nombre del item",
  "quantity": número (opcional),
  "unit": "unidades | kg | litros | etc" (opcional),
  "list_name": "nombre de la lista o null",
  "tags": ["tag1", "tag2"] (opcional, para notes),
  "recurring": true/false (opcional, para packing),
  "threshold": número (opcional, para inventory)
}

Ejemplos con list_name:

"compré 6 aguacates" → {"module": "inventory", "action": "add", "item": "aguacates", "quantity": 6, "unit": "unidades", "list_name": null}

"añade aguacates a despensa de madrid" → {"module": "inventory", "action": "add", "item": "aguacates", "list_name": "despensa madrid"}

"cuánto me queda en nevera de gijón" → {"module": "inventory", "action": "list", "list_name": "nevera gijón"}

"añade pan a mercadona" → {"module": "shopping", "action": "add", "item": "pan", "list_name": "mercadona"}

"añade leche a la compra" → {"module": "shopping", "action": "add", "item": "leche", "list_name": "compra"}

"dime que listas tengo" → {"module": "shopping", "action": "list_all_lists"}

"qué tengo en mi inventario" → {"module": "inventory", "action": "list", "list_name": null}

"añade 3 kg de arroz a despensa madrid" → {"module": "inventory", "action": "add", "item": "arroz", "quantity": 3, "unit": "kg", "list_name": "despensa madrid"}

"añade cepillo a gijón, siempre" → {"module": "packing", "action": "add", "item": "cepillo", "list_name": "gijón", "recurring": true}

"dime que cosas me queda poco en nevera de madrid" → {"module": "inventory", "action": "check_low_stock", "list_name": "nevera madrid"}

Si no puedes parsear el mensaje, devuelve: {"module": "unknown", "action": "unknown"}"""
```

**Step 4: Run parser tests**

Run: `pytest tests/test_parser_list_names.py -v`

Expected: PASS (or mostly passing - some may need adjustment based on Claude's output)

**Step 5: Commit**

```bash
git add core/haiku_parser.py tests/test_parser_list_names.py
git commit -m "feat: update parser to extract list names from natural language"
```

---

## Phase 6: Integration Testing

### Task 10: End-to-End Integration Tests

**Files:**
- Create: `tests/test_list_system_integration.py`

**Step 1: Write integration tests**

Create `tests/test_list_system_integration.py`:

```python
"""Integration tests for unified list system."""
import pytest
from db.connection import get_connection
from core.haiku_parser import HaikuParser
from core.router import Router


@pytest.fixture
def db():
    """Get test database connection."""
    conn = get_connection()
    yield conn
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = 'test_integration')")
    cursor.execute("DELETE FROM lists WHERE user_id = 'test_integration'")
    conn.commit()


@pytest.fixture
def parser():
    return HaikuParser()


@pytest.fixture
def router(db):
    return Router(db, 'test_integration')


def test_multiple_inventories_workflow(db, parser, router):
    """Test full workflow with multiple inventory lists."""
    # Create two inventories
    from modules.item_list import ItemListModule
    ItemListModule.create_list(db, 'test_integration', 'despensa madrid', 'inventory')
    ItemListModule.create_list(db, 'test_integration', 'nevera gijón', 'inventory')

    # Add items to different inventories
    intent1 = parser.parse("añade 5 aguacates a despensa madrid")
    result1 = router.route(intent1)
    assert result1['success'] is True

    intent2 = parser.parse("añade 3 kg de arroz a nevera gijón")
    result2 = router.route(intent2)
    assert result2['success'] is True

    # List each inventory
    intent3 = parser.parse("qué tengo en despensa madrid")
    result3 = router.route(intent3)
    assert 'aguacates' in result3['result']
    assert 'arroz' not in result3['result']  # Arroz is in different list


def test_shopping_with_quantities(db, parser, router):
    """Test shopping lists with quantities."""
    intent1 = parser.parse("añade 2 kg de pan a mercadona")
    result1 = router.route(intent1)
    assert result1['success'] is True

    intent2 = parser.parse("lista de mercadona")
    result2 = router.route(intent2)
    assert 'pan' in result2['result']
    assert '2' in result2['result']
    assert 'kg' in result2['result']


def test_threshold_warning_flow(db, parser, router):
    """Test inventory threshold warnings."""
    from modules.inventory_new import InventoryModule
    inv = InventoryModule(db, 'test_integration', 'despensa', 'inventory')

    # Add item above threshold - no warning
    result1 = inv.add('leche', quantity=5, threshold=2)
    assert result1.get('warning') is False

    # Reduce to below threshold - warning
    result2 = inv.update_quantity('leche', -4)  # 5 - 4 = 1
    assert result2.get('warning') is True
    assert '⚠️' in result2['message']


def test_smart_defaults_single_list(db, parser, router):
    """Test smart defaults with single list."""
    from modules.item_list import ItemListModule
    ItemListModule.create_list(db, 'test_integration', 'despensa', 'inventory')

    # Parse without list name
    intent = parser.parse("añade aguacates")
    # Force list_name to None to test smart defaults
    intent['list_name'] = None

    result = router.route(intent)

    # Should auto-select the only inventory list
    assert result['success'] is True


def test_smart_defaults_multiple_lists_error(db, parser, router):
    """Test smart defaults error with multiple lists."""
    from modules.item_list import ItemListModule
    ItemListModule.create_list(db, 'test_integration', 'despensa', 'inventory')
    ItemListModule.create_list(db, 'test_integration', 'nevera', 'inventory')

    intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'aguacates',
        'list_name': None
    }

    result = router.route(intent)

    # Should return error with list options
    assert result['success'] is False
    assert '¿A qué lista?' in result['result']


def test_list_all_lists_command(db, parser, router):
    """Test listing all lists with categories."""
    from modules.item_list import ItemListModule
    ItemListModule.create_list(db, 'test_integration', 'mercadona', 'shopping')
    ItemListModule.create_list(db, 'test_integration', 'carrefour', 'shopping')
    ItemListModule.create_list(db, 'test_integration', 'despensa', 'inventory')

    intent = parser.parse("dime que listas tengo")
    result = router.route(intent)

    assert result['success'] is True
    assert 'mercadona' in result['result']
    assert 'carrefour' in result['result']


def test_packing_recurring_items(db, parser, router):
    """Test packing list recurring items."""
    intent1 = parser.parse("añade cepillo a gijón, siempre")
    result1 = router.route(intent1)
    assert result1['success'] is True

    # Check the item (should remain because recurring)
    from modules.packing_new import PackingModule
    pack = PackingModule(db, 'test_integration', 'gijón', 'packing')
    result2 = pack.check_item('cepillo')
    assert result2['status'] == 'checked'

    # Item should still exist
    assert pack.get('cepillo') is not None
```

**Step 2: Run integration tests**

Run: `pytest tests/test_list_system_integration.py -v`

Expected: PASS - all integration flows work

**Step 3: Commit**

```bash
git add tests/test_list_system_integration.py
git commit -m "test: add end-to-end integration tests for unified list system"
```

---

## Phase 7: Cleanup and Documentation

### Task 11: Rename New Modules to Replace Old Ones

**Files:**
- Rename: `modules/inventory_new.py` → `modules/inventory.py`
- Rename: `modules/shopping_new.py` → `modules/shopping.py`
- Rename: `modules/packing_new.py` → `modules/packing.py`
- Backup old files

**Step 1: Backup old modules**

```bash
cd /data/AssistantStudies/sebastian2
mkdir -p backup_old_modules
mv modules/inventory.py backup_old_modules/inventory_old.py
mv modules/shopping.py backup_old_modules/shopping_old.py
mv modules/packing.py backup_old_modules/packing_old.py
```

**Step 2: Rename new modules**

```bash
mv modules/inventory_new.py modules/inventory.py
mv modules/shopping_new.py modules/shopping.py
mv modules/packing_new.py modules/packing.py
```

**Step 3: Update test imports**

```bash
# Update test files to import from correct modules
sed -i 's/inventory_new/inventory/g' tests/test_inventory_new.py
sed -i 's/shopping_new/shopping/g' tests/test_shopping_new.py
sed -i 's/packing_new/packing/g' tests/test_packing_new.py

# Rename test files
mv tests/test_inventory_new.py tests/test_inventory_module_new.py
mv tests/test_shopping_new.py tests/test_shopping_module_new.py
mv tests/test_packing_new.py tests/test_packing_module_new.py
```

**Step 4: Update router imports**

Router should now import from `modules.inventory`, `modules.shopping`, `modules.packing` (already updated in Task 8)

**Step 5: Run all tests to verify**

Run: `pytest tests/ -v`

Expected: All tests pass with new module names

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: replace old modules with unified list system modules"
```

---

### Task 12: Update COMANDOS.md Documentation

**Files:**
- Modify: `docs/COMANDOS.md`

**Step 1: Update COMANDOS.md with new features**

Key sections to update:
1. Inventory section - mention multiple named inventories
2. Shopping section - mention quantities
3. Add examples of list name usage
4. Update parser behavior section
5. Add smart defaults explanation

Example updates:

```markdown
### 1. Inventory (Múltiples Inventarios)

**Crear/usar inventarios nombrados:**
```
✅ "añade aguacates a despensa de madrid"
✅ "cuánto me queda en nevera de gijón"
✅ "lista de despensa magán"
```

**Añadir items con threshold:**
```
✅ "compré 6 aguacates"  (threshold por defecto: 2)
✅ "añadí 2 kilos de arroz a despensa madrid"
```

**Avisos de stock bajo:**
Cuando actualizas un item y cae por debajo del threshold, recibes un aviso:
```
"quita 5 aguacates" → "✅ Actualizado. ⚠️ Te queda poco aguacates (1 unidades). Piensa en comprar."
```

**Comportamiento especial:**
- Puedes tener múltiples inventarios: "despensa madrid", "nevera gijón", etc.
- Threshold warnings automáticos (ya no auto-añade a compra)
- Smart defaults: si solo tienes 1 inventario, no necesitas nombrar la lista
```

```markdown
### 2. Shopping (Listas de Compra con Cantidades)

**Crear listas:**
```
✅ "crea una lista que se llame mercadona"
```

**Añadir items CON cantidades:**
```
✅ "añade 5 aguacates a mercadona"
✅ "añade 2 kg de pan a la compra"
✅ "añade 3 litros de leche a carrefour"
```

**Smart defaults:**
- Si solo tienes 1 lista de compra → auto-selecciona
- Si tienes múltiples → debes especificar el nombre
```

**Step 2: Commit documentation**

```bash
git add docs/COMANDOS.md
git commit -m "docs: update COMANDOS.md with unified list system features"
```

---

### Task 13: Run Full Test Suite and Verify

**Step 1: Run complete test suite**

Run: `pytest tests/ -v --tb=short`

Expected: All tests pass (60+ tests)

**Step 2: If any tests fail, use @superpowers:systematic-debugging**

Follow systematic debugging process to fix any failing tests.

**Step 3: Verify migration worked correctly**

Check database state:

```bash
mysql -u root sebastian_db -e "SELECT COUNT(*) as list_count FROM lists WHERE list_category = 'inventory'"
mysql -u root sebastian_db -e "SELECT name, list_category FROM lists LIMIT 10"
mysql -u root sebastian_db -e "SELECT COUNT(*) as item_count FROM list_items WHERE quantity IS NOT NULL"
```

Expected: Data migrated successfully

**Step 4: Create final verification commit**

```bash
git add -A
git commit -m "test: verify unified list system implementation complete

- All 60+ tests passing
- Database migration successful
- Documentation updated
- Old modules backed up"
```

---

## Phase 8: Deployment Preparation (Manual Steps)

### Task 14: Create Deployment Checklist

**Files:**
- Create: `docs/DEPLOYMENT_LIST_REDESIGN.md`

**Step 1: Write deployment checklist**

Create `docs/DEPLOYMENT_LIST_REDESIGN.md`:

```markdown
# List System Redesign - Deployment Checklist

## Pre-Deployment

- [ ] All tests passing locally (pytest tests/ -v)
- [ ] Migration 003 SQL file verified
- [ ] Database backup created
- [ ] Old modules backed up to backup_old_modules/

## Deployment Steps

### 1. Backup Current Production Data

```bash
mysqldump -u root sebastian_db > backup_pre_list_redesign_$(date +%Y%m%d).sql
```

### 2. Apply Migration 003

```bash
mysql -u root sebastian_db < db/migrations/003_unify_lists.sql
```

### 3. Verify Migration

```bash
mysql -u root sebastian_db -e "SHOW COLUMNS FROM lists LIKE 'list_category'"
mysql -u root sebastian_db -e "SHOW COLUMNS FROM list_items LIKE 'quantity'"
mysql -u root sebastian_db -e "SHOW TABLES LIKE 'inventory_backup'"
mysql -u root sebastian_db -e "SELECT COUNT(*) FROM lists WHERE list_category = 'inventory'"
```

### 4. Restart Service

```bash
sudo systemctl restart sebastian.service
sudo systemctl status sebastian.service
```

### 5. Test Basic Commands

Send these test messages to bot:
- "añade aguacates a inventario"
- "lista de inventario"
- "añade pan a mercadona"
- "dime que listas tengo"

### 6. Monitor Logs

```bash
sudo journalctl -u sebastian.service -f
```

## Rollback Plan (If Needed)

### 1. Restore Database Backup

```bash
mysql -u root sebastian_db < backup_pre_list_redesign_YYYYMMDD.sql
```

### 2. Revert Code

```bash
git revert HEAD~5  # Adjust number based on commits
```

### 3. Restore Old Modules

```bash
cp backup_old_modules/inventory_old.py modules/inventory.py
cp backup_old_modules/shopping_old.py modules/shopping.py
cp backup_old_modules/packing_old.py modules/packing.py
```

### 4. Restart Service

```bash
sudo systemctl restart sebastian.service
```

## Post-Deployment Verification

- [ ] All bot commands responding
- [ ] Inventory lists showing items with quantities
- [ ] Shopping lists accepting quantities
- [ ] Smart defaults working (single list auto-select)
- [ ] Threshold warnings appearing
- [ ] No ERROR logs in journalctl

## Success Criteria

✅ All existing functionality preserved
✅ Multiple inventories per user working
✅ Shopping lists have quantities
✅ Smart defaults functioning
✅ Threshold warnings in responses
✅ All tests passing
✅ No data loss from migration
✅ COMANDOS.md reflects new features
```

**Step 2: Commit deployment guide**

```bash
git add docs/DEPLOYMENT_LIST_REDESIGN.md
git commit -m "docs: add deployment checklist for list system redesign"
```

---

## Summary

This plan implements the unified list system redesign with:

**✅ Database Migration**
- Migration 003 adds list_category, quantity, unit fields
- Migrates inventory table to unified structure
- Preserves all existing data

**✅ Core Infrastructure**
- ItemListModule base class (add, remove, get, list, etc.)
- InventoryModule (threshold warnings)
- ShoppingModule (inherits base)
- PackingModule (recurring items)

**✅ Router Updates**
- Smart defaults (auto-select single list)
- Error with options (multiple lists)
- Routes to new modules

**✅ Parser Updates**
- List name extraction from natural language
- Updated system prompt with examples
- Handles multiple inventories

**✅ Testing**
- Unit tests for each module
- Integration tests for workflows
- Migration verification tests
- Parser list name tests

**✅ Documentation**
- COMANDOS.md updated
- Deployment checklist created

**Total estimated time:** 4-6 hours for full implementation

---

**Plan complete and saved to `docs/plans/2026-02-16-list-redesign.md`.**

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
