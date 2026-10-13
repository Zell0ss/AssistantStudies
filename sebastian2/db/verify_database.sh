#!/bin/bash
# Sebastian 2.0 Database Verification
# Checks that all tables were created correctly

# Uso: bash db/verify_database.sh [bd]   (por defecto sebastian_db; solo lee: SHOW/DESCRIBE)
# Fase 1 (D19): la BD se elige con el argumento, p. ej. sebastian_dev o sebastian_test.
DB="${1:-sebastian_db}"

echo "Verifying Sebastian 2.0 database schema in $DB..."
echo "You will be prompted for the sebastian_user password."
echo ""

mysql -u sebastian_user -p "$DB" -e "
SHOW TABLES;
SELECT 'Checking inventory table...' as '';
DESCRIBE inventory;
SELECT 'Checking lists table...' as '';
DESCRIBE lists;
SELECT 'Checking list_items table...' as '';
DESCRIBE list_items;
SELECT 'Checking notes table...' as '';
DESCRIBE notes;
"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ All tables verified successfully!"
else
    echo ""
    echo "✗ Verification failed."
    exit 1
fi
