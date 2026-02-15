# Sebastian 2.0 - Deployment Checklist

**Quick reference for seb01 deployment**

## Pre-Deployment (5 minutes)

- [ ] SSH into seb01
- [ ] Navigate to project directory
- [ ] Verify git repository is up-to-date (`git pull`)
- [ ] Verify Python 3.11+ installed (`python3 --version`)
- [ ] Verify MariaDB running (`sudo systemctl status mariadb`)

## Configuration (10 minutes)

- [ ] Copy template: `cp config.example.yaml config.yaml`
- [ ] Edit config.yaml:
  - [ ] Add Telegram bot token (from @BotFather)
  - [ ] Add Anthropic API key
  - [ ] Add your Telegram user ID (get via /id_me command)
  - [ ] Add your Telegram username
  - [ ] Update MariaDB password
  - [ ] Update logfolder path if needed
  - [ ] Update sprites_path if needed

## Database Setup (5 minutes)

```bash
# Create database and user
sudo mysql -e "CREATE DATABASE sebastian_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER 'sebastian_user'@'localhost' IDENTIFIED BY 'your_password_here';"
sudo mysql -e "GRANT ALL PRIVILEGES ON sebastian_db.* TO 'sebastian_user'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

# Run migrations
cd db && ./run_migration.sh && cd ..

# Verify tables created
./db/verify_database.sh
```

**Expected output:** 4 tables (inventory, shopping_lists, packing_lists, notes)

- [ ] Database `sebastian_db` created
- [ ] User `sebastian_user` created with privileges
- [ ] Migration script executed successfully
- [ ] 4 tables verified in database

## Sprite Setup (5-10 minutes)

- [ ] Create directory: `mkdir -p sprites/images`
- [ ] Copy sprite images to `sprites/images/`
- [ ] Verify filenames match `sprites/mapping.yaml`:
  - [ ] `confident.png` (or .jpg)
  - [ ] `happy.png`
  - [ ] `concerned.png`
  - [ ] `confused.png`
  - [ ] `apologetic.png`
  - [ ] `thinking.png`
  - [ ] `neutral.png`
  - [ ] `excited.png`
  - [ ] `tired.png`
  - [ ] `surprised.png`

## Virtual Environment (2 minutes)

```bash
# Create virtual environment
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

- [ ] Virtual environment created
- [ ] Dependencies installed (8 packages)
- [ ] No installation errors

## Manual Testing (5 minutes)

```bash
# Start bot manually
source .venv/bin/activate
python sebastian_bot.py
```

- [ ] Bot starts without errors
- [ ] See "Bot started successfully" in logs
- [ ] Database connection pool initialized
- [ ] Send test message via Telegram
- [ ] Verify bot responds with sprite image
- [ ] Check database has new entries
- [ ] Stop bot with Ctrl+C

## Service Installation (5 minutes)

```bash
# Copy service file
sudo cp sebastian2.service /etc/systemd/system/

# Update service file paths if needed
sudo nano /etc/systemd/system/sebastian2.service

# Reload systemd
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable sebastian2.service

# Start service
sudo systemctl start sebastian2.service
```

- [ ] Service file copied
- [ ] Working directory path correct in service file
- [ ] User correct in service file (ubuntu)
- [ ] systemd reloaded
- [ ] Service enabled
- [ ] Service started

## Service Verification (5 minutes)

```bash
# Check service status
sudo systemctl status sebastian2.service

# View logs
sudo journalctl -u sebastian2.service -f
```

**Expected status:** `active (running)`

- [ ] Service status shows "active (running)"
- [ ] No errors in service logs
- [ ] Bot initialization messages visible
- [ ] Database connection successful

## Production Testing (5 minutes)

- [ ] Send text message via Telegram → Verify response
- [ ] Add inventory item → Check database
- [ ] Create shopping list → Verify in DB
- [ ] Add note with tags → Search works
- [ ] Test error handling (invalid input) → Graceful failure
- [ ] Verify sprite images display correctly
- [ ] Check response time (<2 seconds)

## Post-Deployment Monitoring (Ongoing)

```bash
# Watch logs live
sudo journalctl -u sebastian2.service -f

# Check service status
sudo systemctl status sebastian2.service

# View database data
mysql -u sebastian_user -p sebastian_db
> SELECT COUNT(*) FROM inventory;
> SELECT * FROM notes ORDER BY created_at DESC LIMIT 5;
```

- [ ] Logs showing normal operation
- [ ] No error messages
- [ ] Database growing as expected
- [ ] Memory usage normal (<100 MB)

## Troubleshooting Quick Reference

### Bot won't start
```bash
# Check logs
sudo journalctl -u sebastian2.service -n 50

# Common issues:
# - Missing config.yaml → Create from template
# - Wrong API key → Check Telegram token
# - Database connection error → Verify MariaDB running
# - Missing dependencies → Reinstall requirements.txt
```

### Bot not responding
```bash
# Check service running
sudo systemctl status sebastian2.service

# Restart service
sudo systemctl restart sebastian2.service

# Check authorization
# - User ID must be in config.yaml authorized_ids
# - Username must be in config.yaml authorized_users
```

### Database errors
```bash
# Check MariaDB running
sudo systemctl status mariadb

# Verify credentials in config.yaml
# Verify tables exist:
mysql -u sebastian_user -p sebastian_db -e "SHOW TABLES;"
```

### Sprite images not showing
```bash
# Check images exist
ls -la sprites/images/

# Check mapping.yaml
cat sprites/mapping.yaml

# Check file permissions
chmod 644 sprites/images/*.png
```

## Rollback

If deployment fails:

```bash
# Stop service
sudo systemctl stop sebastian2.service

# Disable service
sudo systemctl disable sebastian2.service

# Remove service file
sudo rm /etc/systemd/system/sebastian2.service
sudo systemctl daemon-reload

# Drop database (optional, if needed)
sudo mysql -e "DROP DATABASE sebastian_db;"
sudo mysql -e "DROP USER 'sebastian_user'@'localhost';"
```

## Success Criteria

**Deployment successful when:**
- ✅ Service status shows "active (running)"
- ✅ Bot responds to Telegram messages
- ✅ Sprite images display correctly
- ✅ Database queries work (add inventory, create notes, etc.)
- ✅ Response time <2 seconds
- ✅ No errors in journalctl logs
- ✅ Authorization working (only authorized users can interact)

## Timeline

**Total estimated time:** 30-40 minutes

- Pre-deployment: 5 min
- Configuration: 10 min
- Database setup: 5 min
- Sprite setup: 5-10 min
- Virtual environment: 2 min
- Manual testing: 5 min
- Service installation: 5 min
- Service verification: 5 min
- Production testing: 5 min

## Next Steps After Deployment

1. **Week 1**: Monitor logs daily, verify no crashes
2. **Week 2**: Check API costs, database growth
3. **Month 1**: User feedback, feature requests
4. **Month 2+**: Multi-user support, advanced features

---

**Quick Commands Reference:**

```bash
# Start service
sudo systemctl start sebastian2.service

# Stop service
sudo systemctl stop sebastian2.service

# Restart service
sudo systemctl restart sebastian2.service

# View status
sudo systemctl status sebastian2.service

# View logs
sudo journalctl -u sebastian2.service -f

# Check database
mysql -u sebastian_user -p sebastian_db

# Manual test
source .venv/bin/activate && python sebastian_bot.py
```
