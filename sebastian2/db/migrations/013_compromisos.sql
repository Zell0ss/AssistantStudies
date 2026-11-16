-- Sebastian 2.0 - compromisos (fase 3, H1, D45, D50, D51): cosas que el usuario tiene que hacer, con dia, hora o intervalo,
-- sueltas o atadas a un evento del calendario. Sin `USE` (D20): la BD la elige quien aplica la migracion. Idempotente.
--
-- Cuando: exactamente una de dos formas (lo comprueba `modules/compromisos.py`, no la BD):
--   a) suelto: fecha_inicio [, fecha_fin] [, hora]
--   b) atado a un evento (D50): dias_inicio [, dias_fin] [, hora]  o  minutos (relativo a la hora del evento).
-- Un compromiso atado NO guarda fecha: el momento se calcula al leerlo desde events, asi que si el evento se mueve, se mueve.
-- `aviso_para` (D51) es el momento para el que ya se aviso, no un «enviado si/no».
-- La FK no lleva ON DELETE (plan §2.1): al borrar un evento, CalendarModule cancela y desvincula antes sus compromisos.
CREATE TABLE IF NOT EXISTS compromisos (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id          VARCHAR(50)  NOT NULL,
  texto            VARCHAR(500) NOT NULL,
  evento_id        INT NULL,
  fecha_inicio     DATE NULL,
  fecha_fin        DATE NULL,
  dias_inicio      SMALLINT NULL,
  dias_fin         SMALLINT NULL,
  hora             TIME NULL,
  minutos          INT NULL,
  estado           ENUM('pendiente','hecho','cancelado') NOT NULL DEFAULT 'pendiente',
  aviso_para       DATETIME NULL,
  created_at       DATETIME NOT NULL,
  updated_at       DATETIME NOT NULL,
  INDEX idx_user_estado (user_id, estado),
  INDEX idx_evento (evento_id),
  FOREIGN KEY (evento_id) REFERENCES events(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
