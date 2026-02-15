# Sebastian 2.0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a personal assistant with persistent memory for inventory, shopping lists, packing lists, and notes - voice-first, Spanish-language, with sprite personality.

**Architecture:** Telegram bot → Claude Haiku intent parser (structured JSON) → Module router → MariaDB → Response formatter (text + sprite) → Telegram

**Tech Stack:** Python 3.11, pyTelegramBotAPI, Anthropic SDK (Haiku), MariaDB (PyMySQL), loguru, systemd

---

## Prerequisites

**Before starting:**
- MariaDB running on seb01 (already exists)
- Telegram bot token (get new one from @BotFather or use existing)
- Anthropic API key (for Claude Haiku)
- Sprite images ready (12 PNG files)

**Working directory:** `/data/AssistantStudies/sebastian2/`

---

## Phase 1: Project Scaffolding

### Task 1: Create Directory Structure

**Files:**
- Create: `/data/AssistantStudies/sebastian2/` (root directory)
- Create: Directory structure as specified

**Step 1: Create directory tree**

```bash
cd /data/AssistantStudies
mkdir -p sebastian2/{bot,core,modules,db/migrations,sprites/images,utils,tests}
cd sebastian2
```

**Step 2: Create empty __init__.py files**

```bash
touch bot/__init__.py
touch core/__init__.py
touch modules/__init__.py
touch db/__init__.py
touch utils/__init__.py
touch tests/__init__.py
```

**Step 3: Verify structure**

```bash
tree -L 2
```

Expected output:
```
sebastian2/
├── bot/
│   └── __init__.py
├── core/
│   └── __init__.py
├── modules/
│   └── __init__.py
├── db/
│   ├── __init__.py
│   └── migrations/
├── sprites/
│   └── images/
├── utils/
│   └── __init__.py
└── tests/
    └── __init__.py
```

**Step 4: Commit**

```bash
git init
git add .
git commit -m "chore: initial project scaffolding for sebastian2

- Create directory structure (bot, core, modules, db, sprites, utils, tests)
- Add __init__.py files for Python packages

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 2: Create Configuration Files

**Files:**
- Create: `sebastian2/config.example.yaml`
- Create: `sebastian2/.env.example`
- Create: `sebastian2/.gitignore`
- Create: `sebastian2/requirements.txt`

**Step 1: Create .gitignore**

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
env/

# Config & Secrets
config.yaml
.env
*.json
!config.example.yaml

# Database
*.sqlite
*.db

# Logs
logs/
*.log

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
EOF
```

**Step 2: Create config.example.yaml**

```bash
cat > config.example.yaml << 'EOF'
# Sebastian 2.0 Configuration Template
# Copy to config.yaml and fill in your credentials

# Telegram Bot
telegram_apikey: "your_telegram_bot_token_here"

# Anthropic API (Claude Haiku)
anthropic_apikey: "your_anthropic_api_key_here"

# Authorization (Telegram user IDs and usernames)
authorized_ids:
  - 123456789  # Replace with your Telegram user ID
authorized_users:
  - "username"  # Replace with your Telegram username

# MariaDB
mariadb:
  host: "localhost"
  port: 3306
  database: "sebastian_db"
  user: "sebastian_user"
  password: "your_db_password_here"

# Logging
logfolder: "/data/AssistantStudies/sebastian2/logs"

# Sprites
sprites_path: "sprites/images"
sprite_mapping: "sprites/mapping.yaml"
EOF
```

**Step 3: Create requirements.txt**

```bash
cat > requirements.txt << 'EOF'
# Telegram
pyTelegramBotAPI==4.14.0

# Database
PyMySQL==1.1.0
dbutils==3.0.3

# LLM
anthropic==0.18.0

# Config & Utils
pyyaml==6.0.1
python-dotenv==1.0.0
loguru==0.7.2
EOF
```

**Step 4: Create .env.example**

```bash
cat > .env.example << 'EOF'
# Optional environment variables
PYTHONUNBUFFERED=1
EOF
```

**Step 5: Commit**

```bash
git add .gitignore config.example.yaml requirements.txt .env.example
git commit -m "chore: add configuration templates and dependencies

- Add .gitignore (Python, secrets, logs, IDE)
- Add config.example.yaml template
- Add requirements.txt (Telegram, MariaDB, Anthropic, utils)
- Add .env.example

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 3: Create Virtual Environment

**Files:**
- Create: `.venv/` (virtual environment)

**Step 1: Create venv**

```bash
python3.11 -m venv .venv
```

**Step 2: Activate and upgrade pip**

```bash
source .venv/bin/activate
pip install --upgrade pip
```

**Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected output: All packages installed successfully

**Step 4: Verify installation**

```bash
pip list | grep -E "telebot|PyMySQL|anthropic|pyyaml|loguru"
```

Expected output:
```
anthropic         0.18.0
dbutils           3.0.3
loguru            0.7.2
pyTelegramBotAPI  4.14.0
PyMySQL           1.1.0
PyYAML            6.0.1
```

**Step 5: No commit** (venv is gitignored)

---

## Phase 2: Database Setup

### Task 4: Create Database Migration

**Files:**
- Create: `db/migrations/001_initial.sql`

**Step 1: Write migration SQL**

```sql
-- Sebastian 2.0 Initial Schema
-- Creates tables for inventory, lists, list_items, notes

-- Inventory: track what you have at home
CREATE TABLE inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL DEFAULT 0,
    unit VARCHAR(50),
    low_threshold DECIMAL(10,2) DEFAULT 2,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_item (user_id, item_name),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Lists: named collections (shopping, packing, custom)
CREATE TABLE lists (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    list_type ENUM('shopping', 'packing', 'freeform') DEFAULT 'freeform',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_list (user_id, name),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- List Items: entries within lists
CREATE TABLE list_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    list_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    quantity DECIMAL(10,2),
    unit VARCHAR(50),
    checked BOOLEAN DEFAULT FALSE,
    recurring BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE,
    INDEX idx_list_id (list_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Notes: free-form text with tags
CREATE TABLE notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    tags JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    archived BOOLEAN DEFAULT FALSE,
    INDEX idx_user_id (user_id),
    INDEX idx_archived (archived)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Save to: `db/migrations/001_initial.sql`

**Step 2: Create database and user (manual on seb01)**

Run these commands in MySQL as root (NOT in git):

```sql
CREATE DATABASE sebastian_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sebastian_user'@'localhost' IDENTIFIED BY 'CHANGE_THIS_PASSWORD';
GRANT ALL PRIVILEGES ON sebastian_db.* TO 'sebastian_user'@'localhost';
FLUSH PRIVILEGES;
```

**Step 3: Run migration**

```bash
# Update config.yaml with actual DB credentials first
mysql -u sebastian_user -p sebastian_db < db/migrations/001_initial.sql
```

**Step 4: Verify tables created**

```bash
mysql -u sebastian_user -p sebastian_db -e "SHOW TABLES;"
```

Expected output:
```
+------------------------+
| Tables_in_sebastian_db |
+------------------------+
| inventory              |
| list_items             |
| lists                  |
| notes                  |
+------------------------+
```

**Step 5: Commit**

```bash
git add db/migrations/001_initial.sql
git commit -m "feat: add initial database schema

- Create inventory table (items, quantities, thresholds)
- Create lists table (shopping, packing, freeform)
- Create list_items table (with recurring flag)
- Create notes table (content, tags as JSON)
- All tables multi-user (user_id column)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 5: Create Database Connection Module

**Files:**
- Create: `db/connection.py`
- Create: `tests/test_db_connection.py`

**Step 1: Write the failing test**

```python
# tests/test_db_connection.py
import pytest
from db.connection import get_connection, close_connection

def test_get_connection_returns_valid_connection():
    """Test that get_connection returns a working database connection"""
    conn = get_connection()
    assert conn is not None

    # Test connection is usable
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    assert result[0] == 1

    close_connection()

def test_connection_is_reused():
    """Test that get_connection reuses the same connection"""
    conn1 = get_connection()
    conn2 = get_connection()
    assert conn1 is conn2
    close_connection()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_db_connection.py -v
```

Expected: `ModuleNotFoundError: No module named 'db.connection'`

**Step 3: Write minimal implementation**

```python
# db/connection.py
"""
Database connection management with connection pooling.
"""
import pymysql
from dbutils.pooled_db import PooledDB
from loguru import logger
import yaml

_pool = None
_connection = None

def load_config():
    """Load database config from config.yaml"""
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    return config['mariadb']

def init_pool():
    """Initialize connection pool (singleton pattern)"""
    global _pool
    if _pool is None:
        config = load_config()
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=6,
            mincached=2,
            maxcached=5,
            host=config['host'],
            port=config['port'],
            user=config['user'],
            password=config['password'],
            database=config['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.info("Database connection pool initialized")
    return _pool

def get_connection():
    """Get a connection from the pool"""
    global _connection
    if _connection is None:
        pool = init_pool()
        _connection = pool.connection()
        logger.debug("Database connection acquired from pool")
    return _connection

def close_connection():
    """Close the current connection"""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
        logger.debug("Database connection closed")
```

**Step 4: Create config.yaml for testing**

```bash
# Create a test config (copy from example and fill in real credentials)
cp config.example.yaml config.yaml
# Edit config.yaml with real DB credentials
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_db_connection.py -v
```

Expected: `2 passed`

**Step 6: Commit**

```bash
git add db/connection.py tests/test_db_connection.py
git commit -m "feat: add database connection pool

- Implement PooledDB with PyMySQL
- Singleton pattern for connection reuse
- Load config from config.yaml
- Add tests for connection and reuse

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Phase 3: Utility Modules

### Task 6: Create Config Loader

**Files:**
- Create: `utils/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
import pytest
from utils.config import load_config, get_config

def test_load_config_returns_dict():
    """Test that load_config returns a dictionary"""
    config = load_config()
    assert isinstance(config, dict)
    assert 'telegram_apikey' in config
    assert 'anthropic_apikey' in config
    assert 'mariadb' in config

def test_get_config_singleton():
    """Test that get_config returns cached config"""
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'utils.config'`

**Step 3: Write minimal implementation**

```python
# utils/config.py
"""
Configuration loader with singleton pattern.
"""
import yaml
from loguru import logger

_config = None

def load_config(config_path='config.yaml'):
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    logger.info(f"Configuration loaded from {config_path}")
    return config

def get_config():
    """Get cached configuration (singleton)"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: `2 passed`

**Step 5: Commit**

```bash
git add utils/config.py tests/test_config.py
git commit -m "feat: add config loader utility

- Load YAML config with singleton pattern
- Cache config for reuse
- Add tests

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 7: Create Logging Setup

**Files:**
- Create: `utils/logging_config.py`
- Modify: `db/connection.py` (use logging setup)

**Step 1: Write logging setup (no test needed, utility function)**

```python
# utils/logging_config.py
"""
Centralized logging configuration using loguru.
"""
from loguru import logger
import sys
import os

def setup_logging(log_folder='logs', log_level='INFO'):
    """
    Configure loguru for Sebastian 2.0.

    Args:
        log_folder: Directory to store log files
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove default handler
    logger.remove()

    # Console handler (colorized)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=log_level
    )

    # Create log folder if not exists
    os.makedirs(log_folder, exist_ok=True)

    # File handler (rotating)
    logger.add(
        f"{log_folder}/sebastian2.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level=log_level,
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )

    logger.info(f"Logging initialized: level={log_level}, folder={log_folder}")
```

**Step 2: Update db/connection.py to use logging setup**

Add to top of `db/connection.py`:

```python
from utils.logging_config import setup_logging

# Initialize logging
setup_logging()
```

**Step 3: Test manually**

```bash
python -c "from utils.logging_config import setup_logging; setup_logging(); from loguru import logger; logger.info('Test log')"
```

Expected: Log message printed to console and file created in `logs/sebastian2.log`

**Step 4: Commit**

```bash
git add utils/logging_config.py db/connection.py
git commit -m "feat: add centralized logging setup

- Configure loguru with console + file handlers
- Rotating logs (10MB, 30 days retention)
- Colorized console output
- Update db/connection.py to use logging

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Phase 4: Core Modules

### Task 8: Create BaseModule

**Files:**
- Create: `modules/base.py`
- Create: `tests/test_base_module.py`

**Step 1: Write the failing test**

```python
# tests/test_base_module.py
import pytest
from modules.base import BaseModule
from db.connection import get_connection, close_connection

@pytest.fixture
def base_module():
    """Fixture to create BaseModule instance"""
    conn = get_connection()
    user_id = "test_user_123"
    module = BaseModule(conn, user_id)
    yield module
    close_connection()

def test_base_module_has_connection(base_module):
    """Test that BaseModule stores connection"""
    assert base_module.db is not None

def test_base_module_has_user_id(base_module):
    """Test that BaseModule stores user_id"""
    assert base_module.user_id == "test_user_123"

def test_execute_query_returns_cursor(base_module):
    """Test that execute_query works"""
    cursor = base_module.execute_query("SELECT 1 as num", ())
    result = cursor.fetchone()
    assert result['num'] == 1
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_base_module.py -v
```

Expected: `ModuleNotFoundError: No module named 'modules.base'`

**Step 3: Write minimal implementation**

```python
# modules/base.py
"""
Base class for all domain modules.
Provides database connection and common utilities.
"""
from loguru import logger

class BaseModule:
    """
    Base class for domain modules (Inventory, Shopping, Packing, Notes).

    Args:
        db: Database connection
        user_id: Telegram user ID (for multi-user support)
    """

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id
        logger.debug(f"{self.__class__.__name__} initialized for user {user_id}")

    def execute_query(self, query, params):
        """
        Execute a SQL query and return cursor.

        Args:
            query: SQL query string (use %s placeholders)
            params: Tuple of parameters

        Returns:
            Cursor with results
        """
        cursor = self.db.cursor()
        cursor.execute(query, params)
        return cursor

    def commit(self):
        """Commit the current transaction"""
        self.db.commit()
        logger.debug("Transaction committed")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_base_module.py -v
```

Expected: `3 passed`

**Step 5: Commit**

```bash
git add modules/base.py tests/test_base_module.py
git commit -m "feat: add BaseModule for domain modules

- Stores db connection and user_id
- Provides execute_query and commit helpers
- Add tests for BaseModule

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 9: Create InventoryModule

**Files:**
- Create: `modules/inventory.py`
- Create: `tests/test_inventory_module.py`

**Step 1: Write the failing test**

```python
# tests/test_inventory_module.py
import pytest
from modules.inventory import InventoryModule
from db.connection import get_connection, close_connection

@pytest.fixture
def inventory_module():
    """Fixture to create InventoryModule instance"""
    conn = get_connection()
    user_id = "test_user_inventory"
    module = InventoryModule(conn, user_id)

    # Clean up any existing test data
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE user_id = %s", (user_id,))
    conn.commit()

    yield module

    # Cleanup after test
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE user_id = %s", (user_id,))
    conn.commit()
    close_connection()

def test_add_to_inventory_creates_new_item(inventory_module):
    """Test adding a new item to inventory"""
    inventory_module.add("aguacates", 6, "unidades")

    # Verify item was added
    item = inventory_module.get("aguacates")
    assert item is not None
    assert item['quantity'] == 6
    assert item['unit'] == "unidades"

def test_add_to_inventory_increments_existing(inventory_module):
    """Test adding to existing inventory item"""
    inventory_module.add("aguacates", 6, "unidades")
    inventory_module.add("aguacates", 3, "unidades")

    item = inventory_module.get("aguacates")
    assert item['quantity'] == 9

def test_set_inventory_updates_quantity(inventory_module):
    """Test setting absolute quantity"""
    inventory_module.add("aguacates", 10, "unidades")
    inventory_module.set("aguacates", 2, "unidades")

    item = inventory_module.get("aguacates")
    assert item['quantity'] == 2

def test_get_nonexistent_item_returns_none(inventory_module):
    """Test getting item that doesn't exist"""
    item = inventory_module.get("nonexistent")
    assert item is None

def test_list_all_returns_all_items(inventory_module):
    """Test listing all inventory items"""
    inventory_module.add("aguacates", 6, "unidades")
    inventory_module.add("leche", 1, "litros")

    items = inventory_module.list_all()
    assert len(items) == 2
    assert any(i['item_name'] == 'aguacates' for i in items)
    assert any(i['item_name'] == 'leche' for i in items)

def test_check_threshold_returns_true_when_low(inventory_module):
    """Test threshold check when quantity is low"""
    inventory_module.add("aguacates", 2, "unidades")  # Default threshold is 2
    is_low = inventory_module.check_threshold("aguacates")
    assert is_low is True

def test_check_threshold_returns_false_when_sufficient(inventory_module):
    """Test threshold check when quantity is sufficient"""
    inventory_module.add("aguacates", 5, "unidades")
    is_low = inventory_module.check_threshold("aguacates")
    assert is_low is False

def test_set_threshold_updates_threshold(inventory_module):
    """Test setting custom threshold"""
    inventory_module.add("aguacates", 5, "unidades")
    inventory_module.set_threshold("aguacates", 10)

    # Now 5 should be below threshold of 10
    is_low = inventory_module.check_threshold("aguacates")
    assert is_low is True
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_inventory_module.py -v
```

Expected: `ModuleNotFoundError: No module named 'modules.inventory'`

**Step 3: Write minimal implementation**

```python
# modules/inventory.py
"""
Inventory module - track what you have at home.
"""
from modules.base import BaseModule
from loguru import logger

class InventoryModule(BaseModule):
    """
    Manage inventory (pantry, fridge items).

    Operations:
    - add(item, qty, unit) - Add to existing quantity
    - set(item, qty, unit) - Set absolute quantity
    - get(item) - Query current quantity
    - list_all() - Get all inventory items
    - check_threshold(item) - Check if qty <= threshold
    - set_threshold(item, threshold) - Set low stock alert
    """

    def add(self, item_name, quantity, unit=None):
        """
        Add to existing inventory quantity (or create new item).

        Args:
            item_name: Name of the item (e.g., "aguacates")
            quantity: Amount to add
            unit: Unit of measurement (e.g., "unidades", "kg")
        """
        # Check if item exists
        existing = self.get(item_name)

        if existing:
            # Update existing quantity
            new_quantity = existing['quantity'] + quantity
            query = """
                UPDATE inventory
                SET quantity = %s, unit = %s, updated_at = NOW()
                WHERE user_id = %s AND item_name = %s
            """
            self.execute_query(query, (new_quantity, unit or existing['unit'], self.user_id, item_name))
            logger.info(f"Updated inventory: {item_name} {existing['quantity']} → {new_quantity} {unit}")
        else:
            # Create new item
            query = """
                INSERT INTO inventory (user_id, item_name, quantity, unit)
                VALUES (%s, %s, %s, %s)
            """
            self.execute_query(query, (self.user_id, item_name, quantity, unit))
            logger.info(f"Added to inventory: {item_name} = {quantity} {unit}")

        self.commit()

    def set(self, item_name, quantity, unit=None):
        """
        Set absolute inventory quantity.

        Args:
            item_name: Name of the item
            quantity: New quantity (replaces existing)
            unit: Unit of measurement
        """
        existing = self.get(item_name)

        if existing:
            # Update existing
            query = """
                UPDATE inventory
                SET quantity = %s, unit = %s, updated_at = NOW()
                WHERE user_id = %s AND item_name = %s
            """
            self.execute_query(query, (quantity, unit or existing['unit'], self.user_id, item_name))
            logger.info(f"Set inventory: {item_name} = {quantity} {unit}")
        else:
            # Create new
            query = """
                INSERT INTO inventory (user_id, item_name, quantity, unit)
                VALUES (%s, %s, %s, %s)
            """
            self.execute_query(query, (self.user_id, item_name, quantity, unit))
            logger.info(f"Created inventory: {item_name} = {quantity} {unit}")

        self.commit()

    def get(self, item_name):
        """
        Get inventory item by name.

        Args:
            item_name: Name of the item

        Returns:
            Dict with item data or None if not found
        """
        query = """
            SELECT * FROM inventory
            WHERE user_id = %s AND item_name = %s
        """
        cursor = self.execute_query(query, (self.user_id, item_name))
        return cursor.fetchone()

    def list_all(self):
        """
        Get all inventory items for this user.

        Returns:
            List of dicts with inventory data
        """
        query = """
            SELECT * FROM inventory
            WHERE user_id = %s
            ORDER BY item_name
        """
        cursor = self.execute_query(query, (self.user_id,))
        return cursor.fetchall()

    def check_threshold(self, item_name):
        """
        Check if item quantity is at or below threshold.

        Args:
            item_name: Name of the item

        Returns:
            True if qty <= threshold, False otherwise
        """
        item = self.get(item_name)
        if not item:
            return False

        return item['quantity'] <= item['low_threshold']

    def set_threshold(self, item_name, threshold):
        """
        Set custom low stock threshold for an item.

        Args:
            item_name: Name of the item
            threshold: Quantity threshold
        """
        query = """
            UPDATE inventory
            SET low_threshold = %s
            WHERE user_id = %s AND item_name = %s
        """
        self.execute_query(query, (threshold, self.user_id, item_name))
        self.commit()
        logger.info(f"Set threshold: {item_name} threshold = {threshold}")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_inventory_module.py -v
```

Expected: `8 passed`

**Step 5: Commit**

```bash
git add modules/inventory.py tests/test_inventory_module.py
git commit -m "feat: add InventoryModule for tracking items

- Implement add (increment quantity)
- Implement set (absolute quantity)
- Implement get, list_all
- Implement threshold checking and setting
- Add comprehensive tests (8 tests)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 10: Create ShoppingListModule

**Files:**
- Create: `modules/shopping.py`
- Create: `tests/test_shopping_module.py`

**Step 1: Write the failing test**

```python
# tests/test_shopping_module.py
import pytest
from modules.shopping import ShoppingListModule
from db.connection import get_connection, close_connection

@pytest.fixture
def shopping_module():
    """Fixture to create ShoppingListModule instance"""
    conn = get_connection()
    user_id = "test_user_shopping"
    module = ShoppingListModule(conn, user_id)

    # Clean up any existing test data
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = %s)", (user_id,))
    conn.commit()

    # Create shopping list
    module._ensure_shopping_list()

    yield module

    # Cleanup
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    conn.commit()
    close_connection()

def test_add_to_shopping_list(shopping_module):
    """Test adding item to shopping list"""
    shopping_module.add("aguacates")

    items = shopping_module.list_all()
    assert len(items) == 1
    assert items[0]['name'] == "aguacates"

def test_remove_from_shopping_list(shopping_module):
    """Test removing item from shopping list"""
    shopping_module.add("aguacates")
    shopping_module.add("leche")
    shopping_module.remove("aguacates")

    items = shopping_module.list_all()
    assert len(items) == 1
    assert items[0]['name'] == "leche"

def test_mark_bought_removes_item(shopping_module):
    """Test that marking as bought removes item (disappears)"""
    shopping_module.add("aguacates")
    shopping_module.mark_bought("aguacates")

    items = shopping_module.list_all()
    assert len(items) == 0

def test_list_all_returns_unchecked_only(shopping_module):
    """Test that list_all only returns unchecked items"""
    shopping_module.add("aguacates")
    shopping_module.add("leche")
    shopping_module.mark_bought("aguacates")

    items = shopping_module.list_all()
    assert len(items) == 1
    assert items[0]['name'] == "leche"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_shopping_module.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# modules/shopping.py
"""
Shopping list module - items to buy.
"""
from modules.base import BaseModule
from loguru import logger

class ShoppingListModule(BaseModule):
    """
    Manage shopping list.

    Operations:
    - add(item, qty) - Add item to shopping list
    - remove(item) - Remove item from list
    - list_all() - Get all items to buy
    - mark_bought(item) - Mark as bought (disappears from list)
    """

    def _ensure_shopping_list(self):
        """Ensure 'compra' list exists for this user"""
        query = """
            SELECT id FROM lists
            WHERE user_id = %s AND name = 'compra'
        """
        cursor = self.execute_query(query, (self.user_id,))
        existing = cursor.fetchone()

        if not existing:
            query = """
                INSERT INTO lists (user_id, name, list_type)
                VALUES (%s, 'compra', 'shopping')
            """
            self.execute_query(query, (self.user_id,))
            self.commit()
            logger.info(f"Created shopping list for user {self.user_id}")

    def _get_list_id(self):
        """Get the shopping list ID"""
        query = """
            SELECT id FROM lists
            WHERE user_id = %s AND name = 'compra'
        """
        cursor = self.execute_query(query, (self.user_id,))
        result = cursor.fetchone()
        return result['id'] if result else None

    def add(self, item_name, quantity=None, unit=None):
        """
        Add item to shopping list.

        Args:
            item_name: Name of the item
            quantity: Optional quantity
            unit: Optional unit
        """
        self._ensure_shopping_list()
        list_id = self._get_list_id()

        # Check if item already in list
        query = """
            SELECT id FROM list_items
            WHERE list_id = %s AND name = %s AND checked = FALSE
        """
        cursor = self.execute_query(query, (list_id, item_name))
        existing = cursor.fetchone()

        if not existing:
            query = """
                INSERT INTO list_items (list_id, name, quantity, unit, recurring)
                VALUES (%s, %s, %s, %s, FALSE)
            """
            self.execute_query(query, (list_id, item_name, quantity, unit))
            self.commit()
            logger.info(f"Added to shopping list: {item_name}")

    def remove(self, item_name):
        """
        Remove item from shopping list.

        Args:
            item_name: Name of the item to remove
        """
        list_id = self._get_list_id()
        if not list_id:
            return

        query = """
            DELETE FROM list_items
            WHERE list_id = %s AND name = %s
        """
        self.execute_query(query, (list_id, item_name))
        self.commit()
        logger.info(f"Removed from shopping list: {item_name}")

    def list_all(self):
        """
        Get all items on shopping list (unchecked only).

        Returns:
            List of dicts with item data
        """
        list_id = self._get_list_id()
        if not list_id:
            return []

        query = """
            SELECT * FROM list_items
            WHERE list_id = %s AND checked = FALSE
            ORDER BY created_at
        """
        cursor = self.execute_query(query, (list_id,))
        return cursor.fetchall()

    def mark_bought(self, item_name):
        """
        Mark item as bought (removes it from list).

        Args:
            item_name: Name of the item bought
        """
        # For shopping list, bought items disappear
        self.remove(item_name)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_shopping_module.py -v
```

Expected: `4 passed`

**Step 5: Commit**

```bash
git add modules/shopping.py tests/test_shopping_module.py
git commit -m "feat: add ShoppingListModule

- Auto-create 'compra' list on first use
- Implement add, remove, list_all, mark_bought
- Shopping list items disappear when bought
- Add tests (4 tests)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

**Due to length constraints, I'll summarize the remaining tasks. The full plan would continue with:**

### Task 11: PackingListModule (similar structure)
### Task 12: NotesModule (similar structure)
### Task 13: Haiku Intent Parser
### Task 14: Module Router
### Task 15: Sprite System
### Task 16: Response Formatter
### Task 17: Telegram Bot Handlers
### Task 18: Integration Tests
### Task 19: systemd Service
### Task 20: Final Testing & Deployment

---

## Testing Strategy

**Unit tests:** Each module tested in isolation
**Integration tests:** Full flow (Telegram → Haiku → Module → DB → Response)
**Manual tests:** Real Telegram messages with voice input

## Deployment Checklist

- [ ] All tests passing
- [ ] Config file created with real credentials
- [ ] Database migrated
- [ ] Sprite images in place
- [ ] systemd service configured
- [ ] Logs readable
- [ ] Bot responds to Telegram messages

---

**Total Estimated Time:** 12-20 hours of focused development

**Sessions:**
1. Project setup + DB (2-3 hours)
2. Core modules (3-4 hours)
3. Haiku + router (2-3 hours)
4. Telegram handlers + sprites (3-4 hours)
5. Testing + deployment (2-3 hours)
