#!/bin/bash
# Sebastian 2.0 Migration Runner
# Run from sebastian2/ directory: ./db/run_migration.sh

echo "Running Sebastian 2.0 database migration..."
echo "You will be prompted for the sebastian_user password."
echo ""

mysql -u sebastian_user -p sebastian_db < db/migrations/001_initial.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Migration completed successfully!"
    echo "Running verification..."
    ./db/verify_database.sh
else
    echo ""
    echo "✗ Migration failed. Check the error above."
    exit 1
fi
