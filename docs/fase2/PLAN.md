# Plan de la fase 2 — Memoria v1: hechos que se pueden corregir

**Autor:** arquitecto (claudquitecto), 2026-10-15. **Plan:** arquitecto. La fase crea un contrato:
el esquema de memoria en MariaDB y la familia de tools `memory`.
**Rama:** `fase-2`, en el worktree `/data/AssistantStudies-fase2`, sobre `ccb93ab`. H0 ya está en
`main`.
**Decisiones:** `30-projects/sebastian/ADR-MEMORIA.md`. Esta fase aplica D1–D10, D12–D14, D16 y
D18, y añade **D31–D38**, en `tentativa` hasta que Josem apruebe este plan. Se citan en el código,
en la costura que gobiernan.
**Estado:** aprobado por Josem el 2026-10-15, junto con un tope de 5 $ (ver «Para el programador»).

## 0. Qué entra y qué no

**Entra:**
- hechos con vigencia por usuario: afirmar, corregir (sustituir) y retirar;
- catálogo controlado de entidades y atributos, con alias y con estado `pending`;
- `decision_log`;
- lectura estructurada, con historial;
- notas de texto libre con búsqueda semántica;
- proyectos del vault como entidades, con los campos del contrato leídos en vivo (D12, D13);
- retirada de `sebastian_memory` (D18), y el cuaderno sacando sus semillas de la memoria nueva.

**No entra (fase 3):**
- memoria prospectiva (`commitments`);
- consolidación nocturna;
- resumen de la mañana;
- `memory_links` (`depends_on`);
- extracción pasiva de cada mensaje;
- vistas markdown;
- `vault_fichas` (embeber las `ficha.md`);
- embedder local.

**Se trabaja contra:**
- `sebastian_test` y las colecciones `*_test_*` (D25);
- servicios externos neutralizados en los goldens (D27);
- `requirements.txt` fijado (D30). Si hace falta un paquete nuevo, para y pregunta.

## 1. Decisiones de esta fase (se registran en el ADR como `tentativa`)

| # | Decisión | Por qué |
|---|---|---|
| D31 | **La escritura es síncrona, por una tool del planner** (`mark_as_memorable`, con contrato nuevo). La extracción pasiva de cada mensaje va a la fase 3, sobre `conversations` (D23) | Así Alfred puede confirmar en la misma respuesta lo que guardó, lo que sustituyó y los atributos nuevos (D16). La extracción pasiva añade una llamada por turno y ruido, y encaja con la consolidación nocturna |
| D32 | **El extractor es Haiku 4.5 con una tool forzada** (`registrar_hechos`), que devuelve una lista de hechos estructurados. Recibe el catálogo del usuario y la fecha | Mismo modelo que el planner (D29). La tool forzada da un JSON válido en 4.5. El LLM propone nombres; quien decide es el código (D8) |
| D33 | **Memoria por usuario.** Las entidades y los hechos llevan `user_id`; el catálogo de atributos es común | Sebastian tiene 3 usuarios autorizados. Lo que cuenta uno no puede aparecer en las respuestas a otro |
| D34 | **Colecciones Qdrant derivadas de `memory_collection`:** `<base>_catalogo` y `<base>_notas`. La colección `<base>` (Sprint 3) deja de usarse y queda como archivo (D18). El embedder va detrás de una interfaz (`Embedder`), hoy con OpenAI `text-embedding-3-small` | Sin variables de entorno nuevas: D19 ya separa producción, desarrollo y test por `memory_collection`. La interfaz deja entrar el embedder local (D11) sin tocar el esquema |
| D35 | **Escalera de resolución:** alias exacto normalizado → búsqueda semántica en `<base>_catalogo` con señales (puntuación, margen con el segundo, compatibilidad de tipo) → umbral. Los umbrales van en `config.memoria.umbrales`, **calibrados en H1** con unas 30 parejas. **Solo se sustituye** con resolución fuerte (alias exacto, o puntuación y margen altos); si no, se guarda como `nota` y queda en `decision_log` | Es D9 aplicada. Una sustitución errónea hace olvidar algo cierto sin avisar |
| D36 | **Lectura:** el prompt del planner lleva cada turno un **índice** de lo que sabe del usuario (nombres de entidades y atributos con algún hecho vigente, **sin valores**, como mucho 40 líneas). Los valores solo llegan por `search_memory` | Es D6/D26: Sebastian sabe *de qué* sabe sin poder afirmar valores que no ha consultado en ese turno |
| D37 | **D12 en código.** Los proyectos con `30-projects/<p>/proyecto.md` son entidades de tipo `proyecto` con `nombre` = carpeta (D13), solo para el propietario del vault (`config.memoria.propietario_vault`, por defecto `cuaderno_chat_id`). Los atributos del contrato (`estado`, `host`, `stack`, `repo`, `db`) se leen **en vivo** del frontmatter. Si un hecho de conversación choca con el vault, gana el vault y la respuesta lo avisa | El vault es la fuente de lo declarado. Sebastian no lo copia ni lo escribe |
| D38 | **Esquema con prefijo `mem_`** en `sebastian_db` (migración 010, D14): `mem_entidades`, `mem_entidad_alias`, `mem_atributos`, `mem_atributo_alias`, `mem_hechos` y `mem_decisiones` | Concreta D5–D7 y el registro de decisiones. Las tablas de la fase 3 (`commitments`, `links`) llegarán en otra migración |

## 2. Contratos

### 2.1 Esquema (migración `010_memoria.sql`, sin `USE`, D20)

```sql
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
);
CREATE TABLE IF NOT EXISTS mem_entidad_alias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  entidad_id INT NOT NULL,
  alias_norm VARCHAR(120) NOT NULL,             -- normalizado (§2.4)
  UNIQUE KEY uq_alias (entidad_id, alias_norm),
  INDEX idx_alias (alias_norm),
  FOREIGN KEY (entidad_id) REFERENCES mem_entidades(id)
);
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
);
CREATE TABLE IF NOT EXISTS mem_atributo_alias (
  id INT AUTO_INCREMENT PRIMARY KEY,
  atributo_id INT NOT NULL,
  alias_norm VARCHAR(80) NOT NULL,
  UNIQUE KEY uq_alias (atributo_id, alias_norm),
  INDEX idx_alias (alias_norm),
  FOREIGN KEY (atributo_id) REFERENCES mem_atributos(id)
);
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
);
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
);
```

- **Nada se borra.** Corregir o retirar solo pone `valid_to`, y en la sustitución, `superseded_by`.
  Cerrar el hecho viejo y abrir el nuevo van en **una transacción**.
- **Semillas** (migración `011_memoria_semillas.sql`, idempotente):
  - **atributos activos:**
    - `nota` (texto, varios, `*`);
    - `alergia` (varios, persona);
    - `cumpleanos` (fecha, uno, persona);
    - `parentesco` (uno, persona);
    - `preferencia` (varios, `*`);
  - **atributos del contrato del vault**, con `fuente='contrato_vault'` y tipo `proyecto`:
    `estado`, `host`, `stack`, `repo`, `db`.

  Cada uno lleva su `descripcion` en una frase y sus alias. **Las entidades no se siembran**: la
  entidad «yo» se crea la primera vez que la usa cada usuario (`es_usuario`, alias `yo`, `mi`,
  `me`, más su `username` normalizado).

### 2.2 Tool `mark_as_memorable` (contrato nuevo, mismo nombre)

- **Entrada:** `{"texto": str}`. Es lo que el usuario ha dicho que hay que recordar, corregir u
  olvidar, en una frase autocontenida. Sustituye a `content` y `tags`.
- **Descripción para el planner:** cuándo usarla y cuándo no.
  - **Sí:** «recuerda que…»; datos duraderos sobre él, su gente, sus cosas o sus proyectos;
    decisiones («he decidido…»); correcciones («no, es…», «me equivoqué»); retiradas («olvida
    lo de…»).
  - **No:** lo operativo que ya tiene tool (notas, listas, calendario, tareas), ni lo de salud
    (comidas, hambre, sueño: `salud`).
  - Mantén la frontera de los goldens #20 y #22 y de la fase 3 de tristras.
- **Lo que hace:**
  1. Llama al extractor (D32).
  2. Resuelve cada hecho con la escalera (D35).
  3. Escribe y deja todo en `mem_decisiones`.
- **Salida:**

  ```json
  {"success": true, "result": "<resumen corto>",
   "data": {"guardados": [{"entidad": "...", "atributo": "...", "valor": "...",
                           "operacion": "afirmar|corregir|retirar",
                           "sustituye": {"valor": "...", "desde": "AAAA-MM-DD"} | null}],
            "nuevos_pendientes": {"entidades": ["..."], "atributos": ["..."]},
            "notas": ["..."],
            "sin_cambio": ["..."]}}
  ```

  `_ALFRED_SYSTEM` recibe una línea con D16: si hay `nuevos_pendientes`, Alfred lo dice en una
  frase («he abierto la categoría *publicación*; dígame si prefiere otro nombre»).

### 2.3 Tool `search_memory` (contrato nuevo, mismo nombre)

- **Entrada:**

  ```json
  {"query": str, "entidad": str?, "atributo": str?, "historial": bool = false}
  ```

- **Lo que hace:**
  1. Si llegan `entidad` o `atributo`, los resuelve **solo por alias exacto** contra el
     catálogo del usuario. **No hay SQL libre**: la consulta se arma con ids.
  2. Devuelve los hechos vigentes de esa entidad y ese atributo, o todos los de la entidad. Con
     `historial`, también los cerrados, con `valid_from`, `valid_to` y quién sustituyó a quién.
  3. Además hace una búsqueda semántica en `<base>_notas`, filtrada por `user_id`, con `query`.
  4. Si la entidad es un proyecto del vault y el atributo es del contrato, añade el valor en vivo
     del frontmatter y la marca de conflicto si hay un hecho distinto (D37).
- **Salida:**

  ```json
  {"hechos": [...], "historial": [...], "notas": [...], "vault": {...} | null,
   "conflictos": [...]}
  ```

  Si todo viene vacío, Alfred dice que no le consta (D26).

### 2.4 Normalización de alias (`core/memoria/normalizar.py`)

Pasa a minúsculas, quita tildes y diéresis (la `ñ` se queda), quita la puntuación, junta los
espacios y quita **un** artículo o posesivo inicial (`el la los las un una mi mis su sus`). Así,
«El coche» → `coche` y «Mis alergias» → `alergias`. El plural no se toca: para eso están los
alias.

### 2.5 Índice para el planner (D36)

Una función `indice_memoria(user_id)` devuelve unas líneas del tipo:

```
Lo que me consta de ti (nombres, sin valores; usa search_memory para los valores):
- Josem (tú): alergia, preferencia
- Paco (persona): alergia, parentesco
- coche (vehiculo): presion_neumaticos
- saxhero (proyecto, vault): publicacion
```

- Se ordena por el último hecho y se corta en 40 líneas. Si no hay nada, la sección no se pone.
- Va en `_planner_system()` después de las capacidades. **No** va en `_ALFRED_SYSTEM`.
- Si falla, el turno sigue sin índice y deja un `warning` (mismo patrón que D22).

### 2.6 Módulos

Paquete nuevo `core/memoria/`:
- `normalizar.py`;
- `embedder.py` (`Embedder` + `OpenAIEmbedder`);
- `catalogo.py` (alias, índice y búsqueda semántica del catálogo);
- `extractor.py` (la llamada a Haiku);
- `resolucion.py` (la escalera y sus señales, funciones puras);
- `repositorio.py` (SQL, con transacciones);
- `vault.py` (proyectos y frontmatter, solo lectura);
- `servicio.py` (`guardar(texto)` y `consultar(...)`, que usan las tools).

`modules/memory.py` (Sprint 3) **se borra en H4**, junto con su test.

## 3. Hitos

### H1 — Esquema, catálogo y calibración

1. Las migraciones 010 y 011, aplicadas a `sebastian_test` y a `sebastian_dev` como
   `sebastian_user`. A producción no.
2. `normalizar.py`, `embedder.py`, `repositorio.py` (alta y consulta de entidades, atributos y
   alias) y `catalogo.py`, con el embebido de **descripciones**, no de alias sueltos (truco de
   pictohistorias, briefing §4.3).
3. Las colecciones `<base>_catalogo` y `<base>_notas` se crean si no existen, con 1536
   dimensiones y Cosine, mediante `scripts/memoria/crear_colecciones.py`.
   - **Se niega** si la base no termina en `_test` o `_dev`, salvo que se pase
     `--produccion`, que es lo que hará Josem.
   - El harness de goldens recrea las suyas en cada sesión.
4. **Calibración [API, OpenAI, menos de 0,01 $].** El fichero es
   `tests/golden/calibracion_catalogo.yaml`, con unas 30 parejas en español:
   - 15 positivas (expresión del usuario → entrada correcta del catálogo; por ejemplo, «las ruedas
     del coche» → `presion_neumaticos`, o «mi cuñado» → `parentesco`);
   - 15 negativas cercanas (por ejemplo, «la presión arterial» frente a `presion_neumaticos`).

   El script `scripts/memoria/calibrar.py` saca:
   - la puntuación de la mejor candidata;
   - el margen con la segunda;
   - para cada umbral entre 0,50 y 0,90, en pasos de 0,05, cuántas positivas acepta y cuántas
     negativas deja pasar.

   **El informe trae la tabla, y los umbrales los fijo yo en la revisión de H1.** El código lee
   los umbrales de `config.memoria.umbrales`, con estos valores provisionales:
   - `reutilizar`: 0,75, con margen de 0,05;
   - `sustituir`: 0,85, con margen de 0,08.

**Pruebas normativas de H1** (sin API, salvo la calibración):

- `test_normalizar_*` (6 casos):
  - «El Coche» → `coche`;
  - «mis alergias» → `alergias`;
  - «Cumpleaños» → `cumpleanos`;
  - «año» se queda con `ñ` y sin tilde;
  - «  la   casa  » → `casa`;
  - «el el» → `el`, porque solo se quita un artículo.
- `test_migraciones_memoria_sin_use` (ya lo cubre T1.5) y `test_semillas_idempotentes`: aplicar
  la 011 dos veces no duplica nada.
- `test_entidad_por_usuario`: la misma `nombre` para dos `user_id` da dos filas. El alias de un
  usuario no resuelve para el otro.
- `test_yo_se_crea_una_vez`: dos llamadas a `entidad_usuario(user_id)` devuelven el mismo id.
- `test_crear_colecciones_rechaza_produccion`: con base `sebastian_memory` y sin `--produccion`,
  sale con código distinto de 0 **sin llamar a Qdrant**. Usa un cliente falso que deja marca.
- `test_embedder_es_intercambiable`: el catálogo funciona con un `EmbedderFalso` determinista.
  Todos los tests unitarios usan este.

**Parada:** `H1-informe.md`, con la tabla de calibración.

### H2 — Escritura

1. `extractor.py` (D32):
   - Haiku 4.5, `tool_choice` forzado a `registrar_hechos`.
   - **Esquema:**
     `hechos: [{entidad, tipo_entidad, atributo, tipo_valor, cardinalidad, valor, operacion, descripcion_atributo}]`,
     con un máximo de 8.
   - **Prompt:** el catálogo del usuario (nombres, alias, atributos con su descripción), la fecha
     de hoy y la regla de usar un nombre existente si es la misma cosa, y no inventar hechos que
     el texto no dice. Las fechas, en ISO.
   - **Va en un fichero:** `prompts/extractor_hechos.md` o el patrón que ya use el repo (cuéntalo).
2. `resolucion.py`:
   - Decide `reutilizar` o `crear` para la entidad y el atributo.
   - Para el hecho decide entre `anadir`, `sustituir`, `retirar`, `nota` y `sin_cambio`, con
     estas reglas:
     - si el atributo tiene cardinalidad `varios` → `anadir`, salvo que el mismo valor normalizado
       ya esté vigente → `sin_cambio`;
     - si es `uno`, no hay vigente → `anadir`;
     - si es `uno`, el vigente es igual → `sin_cambio`;
     - si es `uno`, el vigente es distinto **y** la resolución fue fuerte (alias exacto, o
       puntuación y margen por encima del umbral `sustituir`) → `sustituir`;
     - si es `uno`, el vigente es distinto **y** la resolución fue débil → `nota`, con el texto
       original, y `mem_decisiones` lo marca para revisión;
     - si la operación es `retirar` con resolución fuerte → cierra el vigente; con resolución
       débil → `sin_cambio` y aviso en la salida («no he encontrado qué olvidar»).
   - Un atributo nuevo con `tipos_entidad` incompatible con el tipo de la entidad cuenta como
     resolución débil.
3. `servicio.guardar(texto)`: hace la transacción, escribe en `mem_decisiones`, embebe las
   `nota` en `<base>_notas` (payload `{hecho_id, user_id}`) y devuelve la salida del §2.2.
4. La tool `mark_as_memorable` pasa al contrato nuevo, y hay que actualizar la línea de D16 en
   `_ALFRED_SYSTEM` y el `FAMILY_SUMMARY` de memoria.
   - **El `FAMILY_SUMMARY` no puede prometer lo que no hay:** nada de recordatorios todavía.
   - Comprueba el resumen contra lo que de verdad hacen las tools (el guardarraíl garantiza que
     la tool existe, no que el resumen diga la verdad).

**Pruebas normativas de H2:**

- **Resolución** (funciones puras, sin BD ni API), en `tests/test_memoria_resolucion.py`:
  - `test_varios_anade`;
  - `test_varios_mismo_valor_sin_cambio`;
  - `test_uno_sin_vigente_anade`;
  - `test_uno_igual_sin_cambio`;
  - `test_uno_distinto_fuerte_sustituye`;
  - `test_uno_distinto_debil_va_a_nota`;
  - `test_retirar_fuerte_cierra`;
  - `test_retirar_debil_no_toca`;
  - `test_tipo_incompatible_es_debil`.
- **Repositorio** (contra `sebastian_test`):
  - `test_sustitucion_es_atomica`: si falla el INSERT del nuevo, el viejo sigue vigente;
  - `test_nada_se_borra`: después de sustituir y retirar, el número de filas de `mem_hechos` no
    baja;
  - `test_superseded_by_apunta_al_nuevo`.
- **Servicio**, con el extractor y el embedder falsos:
  - `test_guardar_devuelve_contrato` (las claves del §2.2);
  - `test_atributo_nuevo_queda_pending_y_se_informa`;
  - `test_cada_decision_queda_en_log`.
- **Privacidad:** `test_log_no_lleva_valores`. Al log van ids y tipos de decisión, nunca
  `valor` ni `texto` (igual que `_TOOLS_SIN_LOG_DE_CONTENIDO`: añade `mark_as_memorable` y
  `search_memory` a esa lista).
- **[API] extractor** (`tests/golden/test_extractor.py`, marcado `golden`). Los 10 casos, en
  ese fichero:
  1. «Mi cuñado Paco es alérgico a los frutos secos» → Paco (persona), alergia, «frutos secos»,
     afirmar.
  2. «Me equivoqué, la presión de las ruedas es 2,4 bares» → coche, presión, «2,4 bar»,
     corregir.
  3. «Olvida lo de las camisetas UV» → retirar.
  4. «He decidido no publicar saxhero en GitHub de momento» → saxhero (proyecto), un atributo de
     publicación.
  5. «Mi cumpleaños es el 12 de marzo» → yo, cumpleanos, `--03-12` o una fecha con mes y día.
  6. «Qué tal estás» → `[]`.
  7. «Tengo hambre» → `[]`.
  8. «Paco y Ana son hermanos» → dos hechos.
  9. «Ya no vivo en Gijón, ahora en Oviedo» → corregir.
  10. «Recuerda que mi talla de camisa es la M» → yo, una talla, afirmar.

  Se acepta un atributo con otro nombre si se resuelve por alias o por descripción al canónico
  esperado; el test lo comprueba con el catálogo, no con el string. Cada caso se lanza una vez.

**Parada:** `H2-informe.md`.

### H3 — Lectura, índice, vault y escenarios

1. `search_memory` con el contrato nuevo (§2.3), el índice en el planner (§2.5) y `vault.py`
   (D37).
   - `vault.py` lee `30-projects/*/proyecto.md` desde `vault_docs_path`, con el **mismo
     confinamiento que `consult_docs`**: solo carpetas directas de `30-projects/`, sin seguir
     symlinks fuera.
   - Lee solo el frontmatter, con `yaml.safe_load`.
2. El harness de goldens tiene que:
   - sembrar la memoria de test en **MariaDB** (los 3 hechos que hoy siembra en Qdrant, con
     Paco y su alergia, y la entidad «yo»);
   - dejar de usar `sebastian_memory_test` como colección plana;
   - recrear `<base>_catalogo` y `<base>_notas` de test en cada sesión.
3. **Goldens nuevos**, escritos antes del código y pasados en la línea base solo con `-k`:

   | # | Frase (historia si la hay) | Modo | Esperado |
   |---|---|---|---|
   | 56 | «He decidido no publicar saxhero en GitHub de momento» | exact | `[mark_as_memorable]` |
   | 57 | historia del #56 · «Al final sí publico saxhero este finde» | exact | `[mark_as_memorable]` |
   | 58 | «¿Qué había decidido sobre publicar saxhero?» | exact | `[search_memory]` |
   | 59 | «Me equivoqué: la presión de las ruedas es 2,4 bares» | exact | `[mark_as_memorable]` |
   | 60 | «Apunta en mis notas: presión ruedas 2,4» (negativa) | exact | `[notes_create]` |
   | 61 | «He desayunado tostadas con tomate» (negativa) | exact | `[salud]` |
   | 62 | «Olvida lo de las camisetas UV» | exact | `[mark_as_memorable]` |
   | 63 | «¿Qué alergias tiene Paco?» | exact | `[search_memory]` |

4. **Escenarios con estado [API]**, en `tests/golden/test_escenarios_memoria.py`, marcado
   `golden`.
   - Usan el `Orchestrator` de punta a punta contra `sebastian_test` y las colecciones de test,
     y comprueban **la BD**, no solo la tool.
   - Cada escenario empieza con la memoria del usuario de golden vacía.

   | Escenario | Turnos | Qué tiene que pasar |
   |---|---|---|
   | E1 | «Mi cuñado Paco es alérgico a los frutos secos» → «¿Qué alergias tiene Paco?» | 1 hecho vigente (Paco, alergia); la respuesta contiene «frutos secos» |
   | E2 | «La presión de las ruedas del coche es 2,30 bares» → «Me equivoqué: es 2,4 bares» | el primero cerrado con `superseded_by` = segundo; un vigente; `mem_decisiones` con `sustituir` |
   | E3 | E2 + «¿Qué presión te dije antes?» | la respuesta menciona 2,3 (o 2,30) |
   | E4 | E1 + «Paco también es alérgico al marisco» | dos vigentes en alergia |
   | E5 | E4 + «Olvida lo del marisco de Paco» | el del marisco con `valid_to` y sin `superseded_by`; frutos secos sigue vigente |
   | E6 | «He decidido no publicar saxhero en GitHub» | atributo nuevo `pending`; `mem_decisiones` con `crear_atributo`; la respuesta lo menciona (D16): contiene el nombre del atributo o «nuevo/nueva» |
   | E7 | el usuario A guarda «Mi coche es rojo»; el usuario B pregunta «¿De qué color es mi coche?» | B no recibe «rojo» (D33) |
   | E8 | con un vault de prueba (`tmp`, proyecto `proyecto-prueba` con `estado: stable`): «proyecto-prueba está pausado» → «¿En qué estado está proyecto-prueba?» | la respuesta da `stable` y avisa de que lo dicho no coincide con el vault (D37) |

   - E8 usa su propia config, con `vault_docs_path` apuntando al vault de prueba. **El vault
     real no se toca en ningún escenario.**
   - Los criterios de texto son redes, no pruebas de corrección: el informe pega las respuestas.
5. **Pruebas sin API de H3:**
   - `test_indice_sin_valores`: el índice no contiene ningún `valor`;
   - `test_indice_max_40`;
   - `test_indice_falla_y_turno_sigue`;
   - `test_search_memory_no_resuelve_por_semantica`: `entidad` solo se resuelve por alias
     exacto;
   - `test_vault_confinado`: un `proyecto.md` symlink fuera de `30-projects` se ignora;
   - `test_vault_gana_y_avisa`.

**Parada:** `H3-informe.md`, con la pasada completa de goldens (63) y los escenarios.

### H4 — Retirada del Sprint 3 y despliegue

1. `scripts/memoria/migrar_sprint3.py`. Lee la colección base (`memory_collection`, solo
   lectura) y escribe en MariaDB, con un **mapa explícito en el código**:
   - «Tengo alergia al ácido acetilsalicílico» → yo, alergia, «ácido acetilsalicílico»;
   - «…camisetas de protección UV…» → yo, nota, con el texto **corregido de sujeto**: «Uso
     camisetas UV para bañarme…»;
   - «La presión de las ruedas del coche es 2,30 bares» → coche (vehiculo),
     `presion_neumaticos` (atributo nuevo, activo), «2,30 bar». Una sola vez: el duplicado se
     descarta.

   Los tres van con `origen='migracion'` y el `user_id` del propietario del vault. Es
   **idempotente**: si ya existen, no hace nada. Con `--dry-run` enseña lo que haría.
2. El cuaderno: `get_random_memory` pasa a sacar un hecho vigente al azar del propietario del
   vault desde MariaDB («entidad · atributo: valor»). `despertar.py` deja de crear el cliente de
   Qdrant si ya no lo necesita. El texto de la semilla no cambia de sentido («un hecho que Josem
   le ha pedido recordar»).
3. Se borran `modules/memory.py` y su test. `memory_collection` queda solo como base de los
   nombres (D34).
4. `deploy/PASOS-CON-SUDO.md`, sección «Fase 2», que ejecuta Josem:
   1. copia de seguridad (`sudo mysqldump`);
   2. `sudo mysql sebastian_db < db/migrations/010_memoria.sql` y la 011;
   3. `crear_colecciones.py --produccion`;
   4. merge `--ff-only`;
   5. `migrar_sprint3.py --dry-run` y después sin él, con
      `SEBASTIAN_DB_NAME=sebastian_db SEBASTIAN_MEMORY_COLLECTION=sebastian_memory` explícitos
      en la línea, porque el `config.yaml` apunta a desarrollo (D19);
   6. reinicio;
   7. `deploy/comprobar_fase2.sh`, de solo lectura;
   8. la prueba por Telegram.

   Lleva vuelta atrás: las tablas `mem_*` no molestan al código viejo, así que basta con
   `git reset --hard` al `main` anterior y reiniciar. **La colección `sebastian_memory` no se
   borra en esta fase.**
5. Prueba de Josem: «¿Qué sabes de mí?» (alergia y camisetas), luego «Mi coche ahora lleva 2,4
   bares», y luego «¿Qué presión llevaba antes?».

**Pruebas normativas de H4:**
- `test_migrar_sprint3_idempotente`;
- `test_migrar_sprint3_mapa` (los 3 hechos, el duplicado descartado y el sujeto corregido);
- `test_migrar_sprint3_no_escribe_en_qdrant`;
- `test_cuaderno_semilla_desde_mariadb`;
- `test_cuaderno_sin_hechos_no_falla`.

**Parada:** `H4-informe.md`, listo para el despliegue de Josem.

## 4. Lista previa (convención §4)

- **¿Algo borra o sobrescribe datos?**
  - **Producción:** las migraciones 010 y 011 solo crean tablas y siembran filas; no tocan las
    existentes. `migrar_sprint3.py` solo inserta, es idempotente y tiene `--dry-run`. La
    colección `sebastian_memory` no se borra. La memoria nueva **no borra filas**, solo cierra
    vigencias.
  - **Tests:** borran la memoria del usuario de golden y de los usuarios de prueba en
    `sebastian_test` (D25), y recrean las colecciones `*_test_*`. `crear_colecciones.py` y el
    harness **se niegan** con bases que no sean de test o desarrollo (T del H1).
  - **El vault** solo se lee (D37). Los escenarios usan un vault de prueba en `tmp`.
- **¿Algo llama a una API externa?** Sí, en pasos **[API]**.
  - **Anthropic, sin cambio de modelos (D29):**
    - planner y extractor en `claude-haiku-4-5-20251001`;
    - síntesis en `claude-sonnet-4-6`;
    - precios en vivo comprobados el 2026-10-14 (H0): 1 $ / 5 $ y 3 $ / 15 $ por millón de
      tokens.
  - **OpenAI** `text-embedding-3-small` (embebido de catálogo y notas): es despreciable (Sprint 3
    midió unos 0,0000003 $ por operación).
  - **El extractor** suma una llamada a Haiku solo en los turnos que guardan algo: unos
    4.000–6.000 tokens con el catálogo, es decir, ≈ 0,006 $ por guardado.
  - **El índice** suma ≤ 40 líneas al prompt del planner en cada turno: unos 400 tokens, es
    decir, ≈ 0,0004 $ por iteración.
  - **Presupuesto de la fase, con 1,25 $ por pasada completa de 63 goldens:**

    | Partida | Coste |
    |---|---|
    | Calibración (H1) | < 0,01 $ |
    | Extractor (H2) | ≈ 0,1 $ |
    | Línea base de los goldens nuevos (H3) | ≈ 0,15 $ |
    | Pasada completa (H3) | ≈ 1,25 $ |
    | Escenarios (H3), unos 20 turnos | ≈ 0,9 $ |
    | Una pasada de retoques | ≈ 1,25 $ |
    | Escenarios de retoques | ≈ 0,9 $ |
    | **Total** | **≈ 4,6 $** |

    **Tope que pido: 5 $** para toda la fase. Cada informe da el coste por modelo, y el harness
    tiene que medir también OpenAI. Si se pasa del tope, para.
- **¿Algo toca producción?** Sí, en H4, y lo ejecuta **Josem**:
  - `sebastian_db` (migraciones 010 y 011 y el script de migración);
  - Qdrant (dos colecciones nuevas);
  - `sebastian.service` (reinicio).

  El cuaderno coge el código nuevo en su próximo disparo. **No cambian** las unidades ni las
  variables de entorno: D34 deriva las colecciones de `memory_collection`.

## 5. Riesgos que vigilo en las revisiones

- **El índice en el prompt del planner (D36)** puede cambiar la elección de tools en goldens que
  hoy pasan. Por eso la pasada completa de H3 va con el índice puesto y con la memoria de test
  sembrada. Si cae algún golden antiguo, se para y se cuenta.
- **La frontera entre memoria y salud.** «He comido…» va a `salud`, nunca a `mark_as_memorable`
  (#61). «Recuerda que soy alérgico a…» va a memoria. La descripción de las dos tools tiene que
  dejarlo claro.
- **La calibración con 30 parejas es poco.** Por eso los umbrales son `tentativa`, y los ajustará
  `mem_decisiones` tras dos semanas de uso (briefing §4.9, paso 5).

## Para el programador

Responde a: 4d8fa07 (H0-revision §6)

- **Plan aprobado** por Josem el 2026-10-15, en la ventana del arquitecto («DALE!»).
- **Gasto autorizado:** hasta **5 $** para toda la fase 2, entre Anthropic y OpenAI. Lo autorizó
  Josem el 2026-10-15, en la ventana del arquitecto. Cópialo en el «Gasto» de cada informe, con lo
  gastado por modelo y lo que se lleva acumulado. Cada paso **[API]** se confirma también en tu
  ventana, como siempre.
- **D31–D38** pasan a `vigente` al aprobarse el plan; los umbrales de D35 siguen en `tentativa`
  hasta la calibración.

Orden:
1. **H1** completo (§3): las migraciones 010 y 011 en `sebastian_test` y `sebastian_dev`,
   `core/memoria/` (normalizar, embedder, repositorio, catálogo), `crear_colecciones.py` con su
   negativa, y las pruebas normativas de H1.
2. La calibración **[API, OpenAI]** con las 30 parejas. La tabla va en el informe, y **los umbrales
   no los fijas tú**.
3. **Para** en H1 con `docs/fase2/H1-informe.md`. No sigas con H2 sin mi revisión.
