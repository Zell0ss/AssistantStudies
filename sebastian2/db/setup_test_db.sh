#!/bin/bash
# Sebastian 2.0 - Golden harness test schema setup
# Creates an ISOLATED sebastian_test database (separate from sebastian_db) and
# applies all migrations to it. Run from sebastian2/ directory.
#
# Safe to re-run: CREATE DATABASE IF NOT EXISTS, migrations use IF NOT EXISTS/IF NOT EXISTS-style guards.

set -e

echo "Creating sebastian_test database (sudo mysql)..."
sudo mysql -e "
CREATE DATABASE IF NOT EXISTS sebastian_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON sebastian_test.* TO 'sebastian_user'@'localhost';
FLUSH PRIVILEGES;
"

echo "Applying migrations to sebastian_test..."
for f in db/migrations/*.sql; do
    echo "  -> $f"
    sudo mysql sebastian_test < "$f"
done

echo ""
echo "✓ sebastian_test ready. Verifying tables..."
sudo mysql sebastian_test -e "SHOW TABLES;"
