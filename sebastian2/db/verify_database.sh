#!/bin/bash
# Sebastian 2.0 Database Verification
# Checks that all tables were created correctly

echo "Verifying Sebastian 2.0 database schema..."
echo "You will be prompted for the sebastian_user password."
echo ""

mysql -u sebastian_user -p sebastian_db -e "
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
