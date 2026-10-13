# Database Setup

## Prerequisites
- MariaDB running on localhost
- Root access to MySQL

## Setup Steps

### 1. Create Database and User (as root)
```bash
# Edit setup_database.sql and change password first!
mysql -u root -p < db/setup_database.sql
```

### 2. Run Migrations (BD de test o desarrollo; D19/D25)
```bash
cd sebastian2
bash db/setup_db.sh sebastian_test   # o sebastian_dev; rechaza sebastian_db
```
La BD de producción solo la toca Josem, a mano (ver `deploy/PASOS-CON-SUDO.md`).

### 3. Verify (optional)
```bash
./db/verify_database.sh
```

## Troubleshooting

If migration fails:
- Check that database and user were created
- Verify password in setup_database.sql
- Ensure MariaDB is running
- Check migration file exists: `db/migrations/001_initial.sql`
