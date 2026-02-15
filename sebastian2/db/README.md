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

### 2. Run Migration
```bash
cd /data/AssistantStudies/sebastian2
./db/run_migration.sh
```

### 3. Verify (optional - run_migration.sh does this automatically)
```bash
./db/verify_database.sh
```

## Troubleshooting

If migration fails:
- Check that database and user were created
- Verify password in setup_database.sql
- Ensure MariaDB is running
- Check migration file exists: `db/migrations/001_initial.sql`
