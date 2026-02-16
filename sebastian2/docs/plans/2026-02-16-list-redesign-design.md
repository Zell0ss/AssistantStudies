# List System Redesign - Design Document

**Date:** 2026-02-16
**Status:** Approved
**Author:** Claude (with user collaboration)

---

## Executive Summary

Redesign Sebastian's list system to eliminate duplication and complexity by recognizing that only **Notes** is fundamentally different from other list types. All other lists (inventory, shopping, packing) are **item-based** with name + quantity + unit, differing only in behavior (threshold warnings, recurring flags).

**Key Changes:**
- Unify inventory/shopping/packing into single `ItemList` base class
- Support multiple named inventories ("despensa madrid", "nevera gijón")
- Add quantities to shopping lists ("5 aguacates", not just "aguacates")
- Eliminate auto-trigger from inventory → shopping (replace with warnings)
- All lists are named and searchable

---

## Architecture Overview

### Two Fundamental Types

**1. NoteList** (unchanged)
- Text content + automatic tags
- Multiple named lists per user
- Search by content and tags

**2. ItemList** (unifies inventory/shopping/packing)
- Items with: `name` (unique in list) + `quantity` + `unit`
- Multiple named lists per user
- Categories: `inventory`, `shopping`, `packing`
- Category determines behavior:
  - **inventory**: warnings when `quantity < threshold`
  - **shopping**: standard shopping lists with quantities
  - **packing**: items can have `recurring` flag

### Common Characteristics

- All lists have user-defined names
- All lists are searchable/listable by name
- Command to list all lists with their types
- Smart defaults: auto-select if user has only 1 list of that category

### Key Simplifications

❌ **Removed:** Auto-trigger inventory → shopping
✅ **Added:** Threshold warnings in responses
✅ **Added:** All lists have names (including inventories)
✅ **Added:** Shopping lists have quantities

---

## Database Schema

### Tables

```sql
-- NOTES: No changes (already working well)
notes (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id VARCHAR(255) NOT NULL,
  content TEXT NOT NULL,
  tags JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)

-- LISTS: Unified for inventory/shopping/packing
lists (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,           -- "despensa madrid", "mercadona", "gijón_llevar"
  list_category ENUM('inventory', 'shopping', 'packing') NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY unique_user_list (user_id, name)  -- Name unique per user
)

-- LIST_ITEMS: Unified with all optional fields
list_items (
  id INT PRIMARY KEY AUTO_INCREMENT,
  list_id INT NOT NULL,
  name VARCHAR(255) NOT NULL,           -- "aguacates", "leche", "cepillo"
  quantity DECIMAL(10,2) DEFAULT 1,     -- ALL lists now have quantity
  unit VARCHAR(50) DEFAULT 'unidades',  -- "kg", "litros", "unidades"
  low_threshold DECIMAL(10,2) NULL,     -- Only for inventory lists
  recurring BOOLEAN DEFAULT FALSE,      -- Only for packing lists
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY unique_list_item (list_id, name),  -- Item unique per list
  FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
)
```

### Migration from Current Schema

**Migration 003: Unify list system**

1. **Add `list_category` to existing `lists` table**
   ```sql
   ALTER TABLE lists ADD COLUMN list_category
     ENUM('inventory', 'shopping', 'packing') DEFAULT 'shopping';
   UPDATE lists SET list_category = list_type WHERE list_type IS NOT NULL;
   ```

2. **Add quantity/unit fields to existing `list_items`**
   ```sql
   ALTER TABLE list_items
     ADD COLUMN quantity DECIMAL(10,2) DEFAULT 1,
     ADD COLUMN unit VARCHAR(50) DEFAULT 'unidades',
     ADD COLUMN low_threshold DECIMAL(10,2) NULL;
   ```

3. **Migrate `inventory` table → `lists` + `list_items`**
   ```sql
   -- Create inventory lists (default name: "inventario")
   INSERT INTO lists (user_id, name, list_category)
   SELECT DISTINCT user_id, 'inventario', 'inventory'
   FROM inventory;

   -- Migrate inventory items
   INSERT INTO list_items (list_id, name, quantity, unit, low_threshold)
   SELECT l.id, i.item_name, i.quantity, i.unit, i.low_threshold
   FROM inventory i
   JOIN lists l ON l.user_id = i.user_id
   WHERE l.list_category = 'inventory' AND l.name = 'inventario';
   ```

4. **Drop old `inventory` table** (after verification)

---

## Module Structure

### Class Hierarchy

```python
# modules/item_list.py
class ItemListModule:
    """Base class for all item-based lists (inventory/shopping/packing)"""

    def __init__(self, conn, user_id, list_name, list_category):
        self.conn = conn
        self.user_id = user_id
        self.list_name = list_name
        self.list_category = list_category
        self._ensure_list_exists()

    # Common operations
    def add(self, item_name, quantity=1, unit='unidades', **kwargs)
    def remove(self, item_name)
    def update_quantity(self, item_name, quantity)
    def set_quantity(self, item_name, quantity)
    def get(self, item_name) → dict
    def list_all() → list[dict]

    # List management
    @staticmethod
    def list_all_lists(conn, user_id, category=None) → list[dict]
    @staticmethod
    def create_list(conn, user_id, name, category)
```

```python
# modules/inventory.py
class InventoryModule(ItemListModule):
    """Extends ItemList with threshold warnings"""

    def add(self, item_name, quantity, unit='unidades', threshold=2):
        super().add(item_name, quantity, unit, low_threshold=threshold)
        return self._check_and_warn(item_name)

    def update_quantity(self, item_name, quantity):
        super().update_quantity(item_name, quantity)
        return self._check_and_warn(item_name)

    def _check_and_warn(self, item_name):
        """Returns warning if quantity < threshold"""
        item = self.get(item_name)
        if item and item['low_threshold'] and item['quantity'] < item['low_threshold']:
            return {
                'warning': True,
                'message': f"⚠️ Te queda poco {item_name} ({item['quantity']} {item['unit']}). Piensa en comprar."
            }
        return {'warning': False}

    def check_low_stock(self) → list[dict]:
        """List all items with low stock"""
```

```python
# modules/shopping.py
class ShoppingModule(ItemListModule):
    """Shopping lists - same as base, possible future extensions"""

    # Future: compound command helper
    def bulk_transfer_to_inventory(self, inventory_list_name):
        """Delete all items from shopping and add to inventory"""
        # Phase 2
        pass
```

```python
# modules/packing.py
class PackingModule(ItemListModule):
    """Packing lists - handles recurring flag"""

    def add(self, item_name, quantity=1, unit='unidades', recurring=False):
        super().add(item_name, quantity, unit, recurring=recurring)

    def check_item(self, item_name):
        """Mark as checked - removes if not recurring"""
        item = self.get(item_name)
        if item and not item['recurring']:
            self.remove(item_name)
```

### Router Changes

```python
# core/router.py
def route(self, parsed_intent):
    module = parsed_intent.get('module')
    action = parsed_intent.get('action')
    list_name = parsed_intent.get('list_name')

    # Smart defaults: auto-select if only 1 list
    if not list_name:
        list_name = self._resolve_list_name(module)
        if list_name is None:  # Ambiguous (2+ lists)
            return error_with_list_options(module)

    if module == 'inventory':
        inv = InventoryModule(self.conn, self.user_id, list_name, 'inventory')
        # dispatch action...

    elif module == 'shopping':
        shop = ShoppingModule(self.conn, self.user_id, list_name, 'shopping')
        # dispatch action...
```

---

## Parser Changes

### List Name Extraction

Parser must extract list names from natural language:

**Examples:**
- "añade aguacates a **despensa de madrid**" → `list_name: "despensa madrid"`
- "cuánto me queda en **nevera de gijón**" → `list_name: "nevera gijón"`
- "añade pan a **mercadona**" → `list_name: "mercadona"`
- "lista de **la compra**" → `list_name: "compra"`
- "qué tengo en mi inventario" → `list_name: null` (ambiguous if multiple)

### Updated System Prompt

```python
"""
El usuario tiene múltiples listas nombradas por categoría:
- inventory: "despensa madrid", "nevera gijón", "despensa magán"
- shopping: "compra", "mercadona", "carrefour", "lidl"
- packing: "gijón_llevar", "madrid_llevar", "playa"

IMPORTANTE - Extracción de list_name:
- Si el usuario menciona un nombre específico → extraerlo
- Si menciona "inventario" sin nombre → list_name: null (se pedirá clarificación)
- Si menciona "la compra" → list_name: "compra" (default shopping)

Ejemplos:
"añade aguacates a despensa de madrid" → {
  "module": "inventory",
  "action": "add",
  "item": "aguacates",
  "quantity": 5,
  "list_name": "despensa madrid"
}

"cuánto me queda en nevera de gijón" → {
  "module": "inventory",
  "action": "list",
  "list_name": "nevera gijón"
}

"añade 3 kg de pan a la compra" → {
  "module": "shopping",
  "action": "add",
  "item": "pan",
  "quantity": 3,
  "unit": "kg",
  "list_name": "compra"
}
"""
```

### Smart Defaults (No Conversational State)

**Behavior:**
- If `list_name` is null and user has **only 1 list** of that category → auto-select
- If `list_name` is null and user has **2+ lists** → error with options
- User re-asks with explicit list name (no state management needed)

**Example:**
```python
# User has 3 inventories: "despensa madrid", "nevera gijón", "despensa magán"
# User says: "añade aguacates"

→ Error: "¿A qué lista? Tienes: despensa madrid, nevera gijón, despensa magán"

# User re-asks: "añade aguacates a despensa madrid"
→ Success
```

---

## Error Handling & Edge Cases

### List Name Ambiguity

```python
# Create list with name that already exists
create_list(user_id, "compra", category="shopping")
→ Error: "Ya tienes una lista 'compra'"

# Same name in different categories? NO
# "compra" can only exist once per user_id (enforced by UNIQUE constraint)
```

### Items in Multiple Lists

```python
# "aguacates" can be in:
# - despensa madrid (inventory)
# - mercadona (shopping)
# - nevera gijón (inventory)
# → This is OK, they are different lists
```

### Threshold Warnings

```python
# "quita 5 aguacates" → quantity drops to 1, threshold is 2
→ Response: "✅ Actualizado. ⚠️ Te queda poco aguacates (1 unidades). Piensa en comprar."
```

### Zero or Negative Quantities

```python
# set_quantity("aguacates", 0)
→ Remove item automatically

# add("aguacates", -2)
→ Error: "Cantidad debe ser positiva"
```

### List Doesn't Exist

```python
# "añade pan a mercadona" (but mercadona doesn't exist)
→ Error: "Lista 'mercadona' no existe. Usa 'crea lista mercadona' primero."

# Auto-create is too magical for MVP
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_item_list_module.py
- test_add_item()
- test_remove_item()
- test_update_quantity()
- test_list_all()
- test_unique_item_per_list()

# tests/test_inventory_module.py
- test_threshold_warning()
- test_check_low_stock()
- test_no_warning_when_above_threshold()

# tests/test_shopping_module.py
- test_create_list()
- test_add_with_quantity()

# tests/test_packing_module.py
- test_recurring_items()
- test_check_item_removes_non_recurring()
```

### Integration Tests

```python
# tests/test_list_system_integration.py
- test_multiple_inventories_per_user()
- test_same_item_different_lists()
- test_smart_defaults_single_list()
- test_smart_defaults_multiple_lists_error()
- test_list_all_lists_with_categories()
```

### Parser Tests

```python
# tests/test_parser_list_names.py
- test_extract_list_name_inventory()
- test_extract_list_name_shopping()
- test_default_compra_when_not_specified()
- test_ambiguous_list_name_null()
```

### Migration Tests

```python
# tests/test_migration_003.py
- test_inventory_migrated_to_lists()
- test_list_items_have_quantity_unit()
- test_data_integrity_after_migration()
```

---

## Implementation Phases

### Phase 1: Core Infrastructure
1. Create `ItemListModule` base class
2. Create specialized modules (Inventory, Shopping, Packing)
3. Database migration 003
4. Update router to use new modules
5. Unit tests for all modules

### Phase 2: Parser Updates
1. Update parser system prompt with list_name extraction examples
2. Implement smart defaults logic in router
3. Parser tests for list name extraction

### Phase 3: Integration & Migration
1. Data migration script (inventory → lists)
2. Integration tests
3. Backward compatibility verification
4. Deploy migration

### Phase 4: Cleanup
1. Remove old inventory module
2. Remove old database table (after verification period)
3. Update documentation (COMANDOS.md)

### Phase 5: Future Enhancements (Post-MVP)
1. Compound commands ("borra lista X y apunta en Y")
2. User-configurable defaults per category
3. List renaming command
4. Bulk operations

---

## Trade-offs & Decisions

### Why This Design?

✅ **Simplicity**: Two fundamental types (Notes vs Items) is conceptually clear
✅ **Reusability**: Single codebase for all item operations
✅ **Flexibility**: Multiple named inventories support real use cases
✅ **Migration**: Can reuse existing tables with schema updates
✅ **Testability**: Clear separation of concerns

### What We Gave Up

❌ **Auto-trigger**: Removed inventory → shopping auto-add (replaced with warnings)
❌ **Conversational state**: No multi-turn dialogues (user re-asks with explicit names)
❌ **Compound commands**: Deferred to Phase 5 (too complex for MVP)

### Alternative Considered

**Fully generic lists with JSON config**: More flexible but adds complexity with behavior config scattered across JSON fields. Rejected in favor of explicit categories.

---

## Success Criteria

- ✅ All existing functionality preserved (inventory, shopping, packing, notes)
- ✅ Multiple named inventories per user working
- ✅ Shopping lists have quantities
- ✅ Smart defaults auto-select when unambiguous
- ✅ Threshold warnings in inventory responses
- ✅ All tests passing (unit + integration)
- ✅ Data migration successful with no data loss
- ✅ COMANDOS.md updated

---

## Open Questions for Implementation

1. Should we allow renaming lists in Phase 1 or defer to Phase 5?
2. Default threshold value for new inventory items? (Currently 2)
3. Should packing's recurring flag be user-visible or just a behavior?
4. Compound commands: parse as single intent with multiple actions, or require sequential commands?

---

**Design Status:** ✅ Approved
**Next Step:** Create implementation plan with writing-plans skill
