-- Sebastian 2.0 - project_tasks (Sprint 2: tasks_*)
-- Table originally created by glasspannel and SHARED across projects — not
-- user-scoped (no user_id column), scoped by `project` name instead.
-- Mirrored here (idempotent) so sebastian2's migration history documents the
-- schema it depends on; running this against sebastian_db is a no-op since
-- the table already exists there.
USE sebastian_db;
CREATE TABLE IF NOT EXISTS project_tasks (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    title      VARCHAR(255) NOT NULL,
    project    VARCHAR(100) NOT NULL,
    priority   ENUM('high', 'normal', 'low') DEFAULT 'normal',
    done       TINYINT(1) DEFAULT 0,
    notes      TEXT,
    tags       LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_project (project),
    KEY idx_done (done)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
