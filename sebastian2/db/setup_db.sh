#!/bin/bash
# Sebastian 2.0 - crea una BD NO productiva y le aplica todas las migraciones.
# Uso (desde sebastian2/): bash db/setup_db.sh sebastian_test|sebastian_dev
#
# D19/D25: se niega con cualquier nombre que no sea de test o desarrollo (sobre todo
# sebastian_db, la de producción). Las migraciones no llevan `USE`: la BD la elige este script.
# Seguro de repetir: CREATE DATABASE IF NOT EXISTS y migraciones con IF NOT EXISTS.

set -e

DB="$1"
case "$DB" in
    sebastian_test|sebastian_dev) ;;
    *)
        echo "Uso: $0 sebastian_test|sebastian_dev" >&2
        echo "Rechazado: '$DB' (la BD de producción no se crea ni se toca desde aquí)." >&2
        exit 1
        ;;
esac

echo "Creating $DB database (sudo mysql)..."
sudo mysql -e "
CREATE DATABASE IF NOT EXISTS $DB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON $DB.* TO 'sebastian_user'@'localhost';
FLUSH PRIVILEGES;
"

echo "Applying migrations to $DB..."
for f in db/migrations/*.sql; do
    echo "  -> $f"
    sudo mysql "$DB" < "$f"
done

echo ""
echo "✓ $DB ready. Verifying tables..."
sudo mysql "$DB" -e "SHOW TABLES;"
