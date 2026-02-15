-- Migration 002: User Settings
-- Adds user_settings table for preferences like sprite skin

CREATE TABLE IF NOT EXISTS user_settings (
    user_id VARCHAR(255) PRIMARY KEY,
    sprite_skin VARCHAR(50) DEFAULT 'sebastian',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Index for faster lookups
CREATE INDEX idx_user_settings_user_id ON user_settings(user_id);

-- Insert default settings for existing users if needed
-- (Run this after migration if you have existing users)
-- INSERT IGNORE INTO user_settings (user_id, sprite_skin)
-- SELECT DISTINCT user_id, 'sebastian' FROM inventory;
