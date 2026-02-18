-- Sebastian 2.0 - Weather location support
-- Adds per-user weather location to user_settings

ALTER TABLE user_settings
  ADD COLUMN IF NOT EXISTS weather_location VARCHAR(100) DEFAULT 'Madrid',
  ADD COLUMN IF NOT EXISTS weather_lat      FLOAT        DEFAULT 40.4168,
  ADD COLUMN IF NOT EXISTS weather_lon      FLOAT        DEFAULT -3.7038,
  ADD COLUMN IF NOT EXISTS weather_country  VARCHAR(50)  DEFAULT 'ES';
