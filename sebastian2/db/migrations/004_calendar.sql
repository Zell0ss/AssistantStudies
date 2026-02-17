-- Sebastian 2.0 - Calendar Module
-- Adds events table for personal calendar management

CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    event_date DATE NULL,               -- for all-day events
    start_datetime DATETIME NULL,       -- for timed events
    end_datetime DATETIME NULL,         -- optional end time
    all_day BOOLEAN DEFAULT FALSE,
    recurrence_rule VARCHAR(100) NULL,  -- NULL=single | 'daily' | 'weekly:MON' | 'weekly:MON,WED' | 'monthly:15' | 'monthly:first-TUE'
    recurrence_end DATE NULL,           -- when recurrence stops (NULL = forever)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_event_date (event_date),
    INDEX idx_start_datetime (start_datetime)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
