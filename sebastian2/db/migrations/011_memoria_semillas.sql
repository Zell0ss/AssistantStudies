-- Sebastian 2.0 - memoria v1 (fase 2): atributos semilla y sus alias. Idempotente: INSERT IGNORE
-- sobre las claves unicas (nombre; atributo_id + alias_norm). Las entidades NO se siembran: la
-- entidad «yo» de cada usuario se crea la primera vez que la usa (D33).
-- `descripcion` es la frase que se embebe en <base>_catalogo (D35): una frase, sin alias sueltos.
-- Los alias van ya normalizados (core/memoria/normalizar.py): minusculas, sin tildes, sin articulo.

INSERT IGNORE INTO mem_atributos (nombre, tipo_valor, tipos_entidad, cardinalidad, estado, fuente, descripcion, created_at) VALUES
 ('nota',        'texto',  '*',       'varios', 'activo', 'semilla', 'Cualquier dato suelto que hay que recordar y no encaja en otra categoria', NOW()),
 ('alergia',     'texto',  'persona', 'varios', 'activo', 'semilla', 'Sustancia o alimento que a una persona le provoca alergia o intolerancia', NOW()),
 ('cumpleanos',  'fecha',  'persona', 'uno',    'activo', 'semilla', 'Fecha en la que cumple años una persona', NOW()),
 ('parentesco',  'texto',  'persona', 'uno',    'activo', 'semilla', 'Relacion familiar o de amistad de una persona con el usuario', NOW()),
 ('preferencia', 'texto',  '*',       'varios', 'activo', 'semilla', 'Gusto, preferencia o manera favorita de hacer algo', NOW()),
 ('estado',      'texto',  'proyecto', 'uno',   'activo', 'contrato_vault', 'Fase o situacion actual de un proyecto de software', NOW()),
 ('host',        'texto',  'proyecto', 'uno',   'activo', 'contrato_vault', 'Maquina o servidor donde se ejecuta un proyecto', NOW()),
 ('stack',       'texto',  'proyecto', 'uno',   'activo', 'contrato_vault', 'Lenguajes, librerias y tecnologias con las que esta hecho un proyecto', NOW()),
 ('repo',        'texto',  'proyecto', 'uno',   'activo', 'contrato_vault', 'Repositorio de codigo donde vive un proyecto', NOW()),
 ('db',          'texto',  'proyecto', 'uno',   'activo', 'contrato_vault', 'Base de datos que usa un proyecto', NOW());

INSERT IGNORE INTO mem_atributo_alias (atributo_id, alias_norm)
SELECT a.id, s.alias_norm FROM mem_atributos a
JOIN (
  SELECT 'nota' AS nombre, 'notas' AS alias_norm
  UNION ALL SELECT 'nota', 'apunte'
  UNION ALL SELECT 'nota', 'apuntes'
  UNION ALL SELECT 'alergia', 'alergias'
  UNION ALL SELECT 'alergia', 'alergico a'
  UNION ALL SELECT 'alergia', 'alergica a'
  UNION ALL SELECT 'alergia', 'intolerancia'
  UNION ALL SELECT 'cumpleanos', 'cumple'
  UNION ALL SELECT 'cumpleanos', 'cumpleaños'
  UNION ALL SELECT 'cumpleanos', 'cumples'
  UNION ALL SELECT 'cumpleanos', 'fecha de nacimiento'
  UNION ALL SELECT 'cumpleanos', 'aniversario de nacimiento'
  UNION ALL SELECT 'parentesco', 'relacion'
  UNION ALL SELECT 'preferencia', 'preferencias'
  UNION ALL SELECT 'preferencia', 'gusto'
  UNION ALL SELECT 'preferencia', 'gustos'
  UNION ALL SELECT 'estado', 'fase'
  UNION ALL SELECT 'estado', 'situacion'
  UNION ALL SELECT 'host', 'servidor'
  UNION ALL SELECT 'host', 'maquina'
  UNION ALL SELECT 'stack', 'tecnologias'
  UNION ALL SELECT 'stack', 'lenguaje'
  UNION ALL SELECT 'repo', 'repositorio'
  UNION ALL SELECT 'db', 'base de datos'
  UNION ALL SELECT 'db', 'bd'
) s ON s.nombre = a.nombre;

-- El nombre canonico de cada semilla tambien es un alias (todos son una sola palabra, ya normalizada).
INSERT IGNORE INTO mem_atributo_alias (atributo_id, alias_norm)
SELECT id, nombre FROM mem_atributos WHERE fuente IN ('semilla', 'contrato_vault');
