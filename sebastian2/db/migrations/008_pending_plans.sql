-- Sebastian 2.0 - Pending orchestrator plans
-- Stores Haiku loop state when a required input is missing

CREATE TABLE IF NOT EXISTS pending_plans (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          VARCHAR(64) NOT NULL,
    original_message TEXT NOT NULL,
    messages_json    LONGTEXT NOT NULL,
    question         TEXT NOT NULL,
    missing_field    VARCHAR(128),
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at       DATETIME NOT NULL,
    UNIQUE KEY uq_user_plan (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
