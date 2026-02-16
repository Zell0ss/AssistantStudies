-- Migration 003: Unify list system
-- Adds list_category to lists table and low_threshold to list_items
-- Migrates inventory table data to unified lists structure

START TRANSACTION;

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

-- Add NOT NULL constraint after setting defaults
ALTER TABLE lists MODIFY COLUMN list_category
  ENUM('inventory', 'shopping', 'packing') NOT NULL DEFAULT 'shopping';

-- Step 2: Add low_threshold to existing list_items
-- Note: quantity and unit already exist in list_items from initial schema
ALTER TABLE list_items
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

COMMIT;
