-- Sebastian 2.0 - memoria v1 (fase 2, H3, R7, D41 y D42): la frase de origen de cada hecho.
-- Sin `USE` (D20): la BD la elige quien aplica la migracion. Idempotente, como 010 y 011.
--
-- Una fuente por llamada a `mark_as_memorable`. `texto` es lo que recibio el extractor (la frase que el planner
-- reescribe como autocontenida: sirve para volver a extraer); `mensaje` es el literal del usuario en ese turno
-- (sirve para auditar). Los dos son NULL cuando la fuente se purga (D42: «olvida lo de...» borra el texto).
-- `conversations` se borra a los 7 dias (D23): un hecho que se guarda sin fuente ya no la recupera.
CREATE TABLE IF NOT EXISTS mem_fuentes (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     VARCHAR(50) NOT NULL,
  texto       TEXT NULL,
  mensaje     TEXT NULL,
  purgada_at  DATETIME NULL,
  created_at  DATETIME NOT NULL,
  INDEX idx_user_fecha (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- NULL solo para lo que existia antes de esta migracion (origen 'migracion', D18).
ALTER TABLE mem_hechos
  ADD COLUMN IF NOT EXISTS fuente_id BIGINT NULL,
  ADD INDEX IF NOT EXISTS idx_fuente (fuente_id),
  ADD FOREIGN KEY IF NOT EXISTS fk_hechos_fuente (fuente_id) REFERENCES mem_fuentes(id);
