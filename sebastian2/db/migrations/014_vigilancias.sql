-- Sebastian 2.0 - vigilancias (fase 4, H1, D63-D67): busquedas que Sebastian repite cada manana y le cuenta a Josem.
-- Sin `USE` (D20): la BD la elige quien aplica la migracion. Idempotente.
--
-- Una vigilancia = la busqueda (fuente, consultas, hora), un filtro simple (precio y palabras que descartan; los aplica el
-- codigo) y las reglas del juez (texto libre; las aplica Haiku solo a lo que pasa el filtro). Son de solo lectura (D63).
-- `fuente` lo valida el codigo, no un ENUM: anadir fuentes no migra. `ultima_ronda` y `aviso_fallo` son DATE (D67): la
-- ronda es una al dia. `vigilancia_vistos` guarda lo ya visto por vigilancia (D65); la firma es el sha1 de titulo+descripcion.
CREATE TABLE IF NOT EXISTS vigilancias (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id        VARCHAR(50)  NOT NULL,
  nombre         VARCHAR(100) NOT NULL,
  fuente         VARCHAR(20)  NOT NULL,
  consultas      JSON         NOT NULL,
  filtros        JSON         NOT NULL,
  reglas         TEXT         NOT NULL,
  hora           TIME         NOT NULL,
  activa         BOOLEAN      NOT NULL DEFAULT TRUE,
  ultima_ronda   DATE         NULL,
  aviso_fallo    DATE         NULL,
  created_at     DATETIME     NOT NULL,
  updated_at     DATETIME     NOT NULL,
  UNIQUE KEY uq_user_nombre (user_id, nombre),
  INDEX idx_activa (activa)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS vigilancia_vistos (
  vigilancia_id  BIGINT        NOT NULL,
  anuncio_id     VARCHAR(80)   NOT NULL,
  precio         DECIMAL(10,2) NULL,
  firma          CHAR(40)      NOT NULL,
  modificado     DATETIME      NOT NULL,
  visto_en       DATETIME      NOT NULL,
  PRIMARY KEY (vigilancia_id, anuncio_id),
  INDEX idx_visto (visto_en),
  FOREIGN KEY (vigilancia_id) REFERENCES vigilancias(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
