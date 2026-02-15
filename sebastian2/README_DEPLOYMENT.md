# Sebastian 2.0 - Deployment Guide

## Prerequisites

1. **Python 3.11+** with venv support
2. **MariaDB** running with `sebastian_db` database created
3. **Telegram Bot Token** (from @BotFather)
4. **Anthropic API Key** (Claude Haiku access)

## Setup Steps

### 1. Create Configuration File

```bash
cd /data/AssistantStudies/sebastian2
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your credentials:
- `telegram_apikey`: Your Telegram bot token
- `anthropic_apikey`: Your Anthropic API key
- `authorized_ids`: Your Telegram user ID (get with /id_me)
- `authorized_users`: Your Telegram username
- `mariadb`: Database connection details

### 2. Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv

# Activate venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Setup Database

```bash
# Run database migrations
cd db
./run_migration.sh
./verify_database.sh
cd ..
```

### 4. Test Bot Manually

```bash
# Activate venv
source .venv/bin/activate

# Run bot
python sebastian_bot.py
```

Test with Telegram:
- Send `/start` to your bot
- Send "compré 6 aguacates"
- Verify sprite photo response

Press Ctrl+C to stop.

### 5. Install systemd Service

```bash
# Copy service file
sudo cp sebastian2.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable sebastian2.service

# Start service
sudo systemctl start sebastian2.service

# Check status
sudo systemctl status sebastian2.service
```

### 6. Verify Service is Running

```bash
# Check status
sudo systemctl status sebastian2.service

# View logs
sudo journalctl -u sebastian2.service -f

# Test with Telegram
# Send messages to your bot
```

## Service Management

### Start Service
```bash
sudo systemctl start sebastian2.service
```

### Stop Service
```bash
sudo systemctl stop sebastian2.service
```

### Restart Service
```bash
sudo systemctl restart sebastian2.service
```

### View Logs
```bash
# Follow logs (real-time)
sudo journalctl -u sebastian2.service -f

# View last 100 lines
sudo journalctl -u sebastian2.service -n 100

# View logs since today
sudo journalctl -u sebastian2.service --since today
```

### Check Status
```bash
sudo systemctl status sebastian2.service
```

## Troubleshooting

### Bot doesn't start
1. Check config.yaml exists and has valid credentials
2. Check MariaDB is running: `sudo systemctl status mariadb`
3. Check database exists: `mysql -u root -p -e "SHOW DATABASES LIKE 'sebastian_db'"`
4. Check logs: `sudo journalctl -u sebastian2.service -n 50`

### Bot crashes on startup
1. Check virtual environment: `.venv/bin/python3 --version`
2. Check dependencies: `.venv/bin/pip list`
3. Test manually: `source .venv/bin/activate && python sebastian_bot.py`

### No response to messages
1. Check authorization: Your user ID must be in `authorized_ids`
2. Check Anthropic API key: Valid and has credits
3. Check logs for errors: `sudo journalctl -u sebastian2.service -f`

### Service doesn't auto-restart
1. Check service file: `sudo systemctl cat sebastian2.service`
2. Verify `Restart=on-failure` is set
3. Check service enabled: `sudo systemctl is-enabled sebastian2.service`

## Updating the Bot

```bash
# Stop service
sudo systemctl stop sebastian2.service

# Pull updates (if using git)
git pull

# Activate venv and update dependencies
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# Run any new migrations
cd db && ./run_migration.sh && cd ..

# Restart service
sudo systemctl restart sebastian2.service

# Verify
sudo systemctl status sebastian2.service
```

## File Locations

- **Service file**: `/etc/systemd/system/sebastian2.service`
- **Application**: `/data/AssistantStudies/sebastian2/`
- **Config**: `/data/AssistantStudies/sebastian2/config.yaml`
- **Logs** (file): `/data/AssistantStudies/sebastian2/logs/app.log`
- **Logs** (systemd): `sudo journalctl -u sebastian2.service`
- **Database**: MariaDB on localhost, database `sebastian_db`
- **Virtual env**: `/data/AssistantStudies/sebastian2/.venv/`

## Security Notes

- **config.yaml** contains secrets - never commit to git (already in .gitignore)
- **API keys** are sensitive - protect config.yaml with `chmod 600`
- **Database credentials** should use strong passwords
- **Telegram bot token** should never be shared

## Performance

- **Memory**: ~50-100 MB typical usage
- **CPU**: Minimal (mostly idle, spikes on messages)
- **Database**: Connection pooling reduces overhead
- **API calls**: ~1-2 Haiku API calls per user message (~$0.01/100 messages)

## Monitoring

### Check Service Health
```bash
# Status
sudo systemctl is-active sebastian2.service

# Uptime
sudo systemctl show sebastian2.service --property=ActiveEnterTimestamp

# Recent restarts
sudo journalctl -u sebastian2.service | grep "Started Sebastian"
```

### Monitor Resource Usage
```bash
# Memory and CPU
systemctl status sebastian2.service | grep -E "Memory|CPU"

# Detailed stats
systemd-cgtop | grep sebastian2
```

## Architecture Overview

### Components
- **sebastian_bot.py**: Main entry point, Telegram handlers
- **core/parser.py**: Natural language parsing (quantities, items)
- **core/router.py**: Message routing logic
- **core/formatter.py**: Response formatting
- **modules/**: Feature modules (inventory, sprites, help, admin)
- **db/**: Database migrations and utilities
- **sprites/**: Sprite image generation system

### Message Flow
```
Telegram Message
    ↓
sebastian_bot.py (handlers)
    ↓
Router (route message based on content)
    ↓
Module (process request)
    ↓
Formatter (format response)
    ↓
Telegram Response (text/photo)
```

### Database Schema
- **inventory**: Item tracking with quantities
- **shopping_lists**: Shopping list items
- **consumption_log**: Historical consumption data

### Dependencies
- **telebot**: Telegram Bot API wrapper
- **anthropic**: Claude Haiku API
- **mysql-connector-python**: MariaDB connection
- **loguru**: Structured logging
- **pydantic**: Configuration validation
- **python-dotenv**: Environment variable loading

## Common Tasks

### Adding New Items
Send: "compré 3 manzanas"
Bot: Parses, adds to inventory, returns sprite

### Checking Inventory
Send: "qué tengo" or "inventario"
Bot: Returns formatted inventory list

### Creating Shopping List
Send: "necesito comprar leche"
Bot: Adds to shopping list

### Getting Help
Send: "/start" or "/help"
Bot: Returns command list and examples

## Development Notes

- **Tests**: Run with `pytest` (54 tests, all passing)
- **Logging**: File logs at `logs/app.log`, systemd logs via journalctl
- **Configuration**: Uses YAML config + .env for sensitive data
- **Database migrations**: Located in `db/migrations/`
- **Sprites**: Generated on-the-fly using PIL, cached in memory

## Support

For issues, check:
1. Logs: `sudo journalctl -u sebastian2.service -f`
2. Database connectivity: `mysql -u root -p sebastian_db -e "SELECT COUNT(*) FROM inventory"`
3. API keys: Verify in config.yaml
4. Authorization: Check authorized_ids in config.yaml
