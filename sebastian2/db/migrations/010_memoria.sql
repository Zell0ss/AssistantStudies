-- Sebastian 2.0 - memoria v1 (fase 2, D38): entidades, atributos, hechos con vigencia y decisiones.
-- Sin `USE` (D20): la BD la elige quien aplica la migracion. Idempotente (IF NOT EXISTS).
-- Nada se borra (D7): corregir o retirar solo cierra `valid_to`.
-- `alias_norm` va en utf8mb4_bin: la colacion por defecto (unicode_ci) igualaria `ano` y `año`, y el
-- normalizador conserva la ñ a proposito (plan §2.4).
CREATE TABLE IF NOT EXISTS mem_entidades (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  user_id     VARCHAR(50)  NOT NULL,
  nombre      VARCHAR(120) NOT NULL,            -- canónico, tal como se muestra
  tipo        VARCHAR(40)  NOT NULL,            -- persona, proyecto, vehiculo, lugar, mascota, organizacion, objeto, otro
  estado      ENUM('activo','pending') NOT NULL DEFAULT 'pending',
  es_usuario  BOOLEAN NOT NULL DEFAULT FALSE,   -- la entidad «yo» de ese user_id
  origen      ENUM('conversacion','vault','semilla','migracion') NOT NULL,
  descripcion VARCHAR(255),
  created_at  DATETIME NOT NULL,
  UNIQUE KEY uq_entidad (user_id, nombre),
  INDEX idx_user_tipo (user_id, tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS mem_entidad_alias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  entidad_id INT NOT NULL,
  alias_norm VARCHAR(120) COLLATE utf8mb4_bin NOT NULL,           -- normalizado (§2.4)
  UNIQUE KEY uq_alias (entidad_id, alias_norm),
  INDEX idx_alias (alias_norm),
  FOREIGN KEY (entidad_id) REFERENCES mem_entidades(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS mem_atributos (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  nombre        VARCHAR(80) NOT NULL UNIQUE,    -- snake_case, canónico
  tipo_valor    ENUM('texto','numero','fecha','booleano') NOT NULL DEFAULT 'texto',
  tipos_entidad VARCHAR(255) NOT NULL DEFAULT '*',   -- csv de tipos, o '*'
  cardinalidad  ENUM('uno','varios') NOT NULL DEFAULT 'uno',
  estado        ENUM('activo','pending') NOT NULL DEFAULT 'pending',
  fuente        ENUM('conversacion','contrato_vault','semilla') NOT NULL,
  descripcion   VARCHAR(255) NOT NULL,          -- la frase que se embebe
  created_at    DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS mem_atributo_alias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  atributo_id INT NOT NULL,
  alias_norm VARCHAR(80) COLLATE utf8mb4_bin NOT NULL,
  UNIQUE KEY uq_alias (atributo_id, alias_norm),
  INDEX idx_alias (alias_norm),
  FOREIGN KEY (atributo_id) REFERENCES mem_atributos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS mem_hechos (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id       VARCHAR(50) NOT NULL,
  entidad_id    INT NOT NULL,
  atributo_id   INT NOT NULL,
  valor         TEXT NOT NULL,
  valid_from    DATETIME NOT NULL,
  valid_to      DATETIME NULL,                  -- NULL = vigente
  superseded_by BIGINT NULL,                    -- id del hecho que lo sustituye
  origen        ENUM('conversacion','migracion') NOT NULL,
  confianza     DECIMAL(4,3) NULL,              -- calculada con señales (D8), no la declara el LLM
  created_at    DATETIME NOT NULL,
  INDEX idx_vigentes (user_id, entidad_id, atributo_id, valid_to),
  FOREIGN KEY (entidad_id) REFERENCES mem_entidades(id),
  FOREIGN KEY (atributo_id) REFERENCES mem_atributos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS mem_decisiones (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     VARCHAR(50) NOT NULL,
  tipo        ENUM('crear_entidad','reutilizar_entidad','crear_atributo','reutilizar_atributo',
                   'anadir','sustituir','retirar','nota','sin_cambio') NOT NULL,
  hecho_id    BIGINT NULL,
  senales     JSON NOT NULL,                    -- puntuaciones, margen, tipo, regla aplicada
  detalle     VARCHAR(255) NOT NULL,
  created_at  DATETIME NOT NULL,
  INDEX idx_user_fecha (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
