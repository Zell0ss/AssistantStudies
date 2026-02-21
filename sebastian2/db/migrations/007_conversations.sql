-- Sebastian 2.0 - Conversational memory
-- Stores intra-day chat history for Alfred-style responses

CREATE TABLE IF NOT EXISTS conversations (
    id         BIGINT       AUTO_INCREMENT PRIMARY KEY,
    user_id    VARCHAR(50)  NOT NULL,
    user_msg   TEXT         NOT NULL,
    bot_reply  TEXT         NOT NULL,
    created_at DATETIME     DEFAULT NOW(),
    INDEX idx_user_date (user_id, created_at)
);
