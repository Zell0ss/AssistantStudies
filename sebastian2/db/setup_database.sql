-- Sebastian 2.0 Database Setup
-- Run this as MySQL root user: mysql -u root -p < setup_database.sql

CREATE DATABASE IF NOT EXISTS sebastian_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Change 'your_secure_password_here' to your actual password
CREATE USER IF NOT EXISTS 'sebastian_user'@'localhost' IDENTIFIED BY 'your_secure_password_here';

GRANT ALL PRIVILEGES ON sebastian_db.* TO 'sebastian_user'@'localhost';
FLUSH PRIVILEGES;

-- Verify
SELECT User, Host FROM mysql.user WHERE User = 'sebastian_user';
SHOW DATABASES LIKE 'sebastian_db';
