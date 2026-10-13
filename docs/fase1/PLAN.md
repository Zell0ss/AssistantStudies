# Plan de la fase 1 — Producción y desarrollo separados, y contexto entre turnos

**Autor:** arquitecto (claudquitecto), 2026-10-13. **Plan:** arquitecto. La fase cambia dos
contratos: cómo se elige la BD y la colección (config/entorno), y qué historial entra en el
orquestador.
**Rama:** `fase-1`, en el worktree `/data/AssistantStudies-fase1`, sacada de `main` = `b96e5e0`.
**Decisiones:** `30-projects/sebastian/ADR-MEMORIA.md` (D19–D25). Se citan en el código, en la
costura que gobiernan.
**Estado:** pendiente de aprobación de Josem. **No se toca código hasta su «adelante».**

## 0. Antes de empezar

- **Config del worktree:** se **copia** `sebastian2/config.yaml` desde `/data/AssistantStudies`
  (nunca un symlink), y en la copia se cambia `mariadb.database` a `sebastian_test` y se añade
  `memory_collection: sebastian_memory_test`. Hasta H3 no existe `sebastian_dev`, así que se
  trabaja contra test.
- **`.venv`:** se usa el de producción solo para ejecutar. Si hace falta instalar algo, se crea
  un `.venv` propio en el worktree.
- **Línea base:** `pytest` (384 en verde hoy) y `pytest -m golden` **[API]** (los 49, una vez),
  antes de tocar nada. Así se ve qué goldens fallaban ya.

## 1. Lista previa (convención §4)

- **¿Algo borra o sobrescribe datos?** Sí.
  - Los tests borran filas (hoy, en producción: es justo lo que arregla H1).
  - La limpieza de `conversations` borra filas de más de 7 días.
  - El harness borra el historial del usuario de golden.

  Después de H1, todo test que toque MariaDB va contra `sebastian_test`, y lo vigila un
  guardarraíl que aborta la sesión (T1.3). La limpieza solo borra por fecha y se prueba contra
  test (T2.6).
- **¿Algo llama a una API externa?** Solo los goldens, y son pasos **[API]**.
  - No cambia ningún modelo: siguen `claude-haiku-4-5-20251001` (planner) y `claude-sonnet-4-6`
    (síntesis). Comprobado con la skill `claude-api` el 2026-10-13: los dos IDs están vigentes.
    Haiku 4.5 cuesta 1 $ / 5 $ por millón de tokens de entrada / salida, y Sonnet 4.6, 3 $ / 15 $.
  - El historial añade como mucho unos 1.000 tokens de entrada por llamada, es decir, unos
    0,005 $ por turno con síntesis.
  - **Tope de gasto para la fase: 2 $**, autorizado por Josem, en un máximo de tres pasadas
    completas de goldens. El informe da el coste por modelo.
- **¿Algo toca producción?** Sí, en H3, y lo ejecuta **Josem**. Toca tres cosas: las unidades
  `sebastian.service` y `cuaderno.service` (con `Environment=`), una BD nueva `sebastian_dev`,
  una colección Qdrant nueva `sebastian_memory_dev` y el `config.yaml` del directorio de
  producción. El orden importa (§4, H3).

## 2. H1 — Producción y desarrollo separados (D19, D20, D25)

### Qué se hace

1. **Un único cargador de config.** `utils/config.get_config()` aplica, después de leer el
   YAML, dos overrides del entorno:
   - `SEBASTIAN_DB_NAME`, que pisa `mariadb.database`;
   - `SEBASTIAN_MEMORY_COLLECTION`, que pisa `memory_collection`.

   `db/connection.load_config()` deja de leer el YAML por su cuenta y usa `get_config()["mariadb"]`.
2. **Sin nombres de producción por defecto en el código.**
   - `tool_executor._memory_module` lee `config["memory_collection"]`, sin el
     `.get(..., 'sebastian_memory')`.
   - `scripts/cuaderno/despertar.py` deja la constante `_MEMORY_COLLECTION` y lee el mismo
     campo.
   - Si falta la clave, debe fallar al arrancar, no caer en producción.
3. **El bot dice dónde escribe.** Al arrancar, una línea INFO con la BD y la colección efectivas.
   El cuaderno, lo mismo al despertar.
4. **Migraciones sin `USE`.** Se quita `USE sebastian_db;` de 006–009. `db/setup_test_db.sh`
   pasa a `db/setup_db.sh <nombre>`: acepta `sebastian_test` y `sebastian_dev`, y **se niega**
   con `sebastian_db` o con cualquier otro nombre. `db/run_migration.sh`, que apunta a
   `sebastian_db` y solo aplica la 001, se borra: ya no lo usa nadie.
5. **Tests contra test.**
   - El `conftest.py` raíz fija `SEBASTIAN_DB_NAME=sebastian_test` y
     `SEBASTIAN_MEMORY_COLLECTION=sebastian_memory_test` antes de importar nada, igual que ya
     hace con `LOGCENTRAL_LOG_DIR`.
   - Una fixture de sesión `autouse` abre una conexión con `get_connection()`, comprueba
     `SELECT DATABASE()` y llama a `pytest.exit` si no es `sebastian_test`.
   - Los guardarraíles del harness de goldens se quedan como están.

### Pruebas normativas de H1

Se copian tal cual (nombres incluidos) y se hacen pasar. Un fichero nuevo,
`tests/test_entorno.py`, salvo donde se dice otra cosa.

- **T1.1** `test_override_db_name_desde_entorno`: con `SEBASTIAN_DB_NAME=x` en el entorno y un
  YAML que dice `sebastian_dev`, `get_config()["mariadb"]["database"] == "x"`. Se resetea la
  caché del singleton antes y después.
- **T1.2** `test_override_memory_collection_desde_entorno`: lo mismo con
  `SEBASTIAN_MEMORY_COLLECTION`.
- **T1.3** `test_conexion_de_tests_es_sebastian_test`: `get_connection()` devuelve una conexión
  donde `SELECT DATABASE()` vale `sebastian_test`.
- **T1.4** `test_sin_memory_collection_falla`: un `ToolExecutor` con una config sin
  `memory_collection` lanza `KeyError` al pedir el módulo de memoria. No vale caer a
  `sebastian_memory`.
- **T1.5** `test_ninguna_migracion_lleva_use`: ningún `db/migrations/*.sql` contiene `USE `
  (regex `(?im)^\s*USE\s+`).
- **T1.6** `test_cuaderno_lee_coleccion_de_config`: `despertar` con
  `memory_collection: "coleccion_x"` en la config pide las semillas a `coleccion_x`. Va en
  `tests/test_cuaderno_despertar.py`.
- **T1.7** `test_setup_db_rechaza_produccion`: `bash db/setup_db.sh sebastian_db` sale con un
  código distinto de 0 **sin llamar a `mysql`**. Se comprueba con un `PATH` que pone primero un
  `mysql` falso, que deja una marca si se ejecuta.

**Validar el guardarraíl rompiéndolo** (convención de la casa): con el override de T1.3
apuntando a `sebastian_db` a mano, la sesión de pytest tiene que abortar. Se cuenta en el
informe; no se deja así.

**Parada:** informe `docs/fase1/H1-informe.md`.

## 3. H2 — Contexto entre turnos (D21–D24)

### Contrato

- **`db/conversation_repo.py`, nuevo**, con el mismo estilo que `pending_plan_repo.py`.
  `ConversationRepository(db)` tiene tres métodos:
  - `recientes(user_id, limite=6, ventana_min=120) -> list[dict]`: devuelve
    `[{"user_msg", "bot_reply"}]` en orden cronológico, los últimos `limite` intercambios de ese
    usuario con `created_at >= ahora - ventana_min`. **El corte se calcula en Python** y va como
    parámetro, sin `NOW()` ni `DATE_SUB` en el SQL, para que los tests con sqlite y con MariaDB
    usen la misma consulta.
  - `guardar(user_id, user_msg, bot_reply) -> None`.
  - `limpiar(dias=7) -> int`: borra lo anterior a `ahora - dias` y devuelve cuántas filas.
- **`modules/chat.py` se borra**, con `tests/test_chat_module.py`. Es el `ChatModule` del
  Sebastian antiguo, con su propio cliente de Anthropic y sin ningún uso salvo la limpieza.
  `bot/scheduler.py` pasa a llamar a `ConversationRepository(conn).limpiar(dias=7)`, a la misma
  hora de siempre.
- **Orquestador:**
  - `_handle_inner`: antes del bucle del planner, lee el historial en un `try`. Si falla,
    historial vacío y un `warning` (D22). Lo convierte en mensajes `user`/`assistant`
    alternos y los pone **delante** del mensaje actual. Ese historial va también a la síntesis:
    los mismos mensajes previos y, al final, el `synthesis_prompt` de hoy como último `user`.
  - `_resume_plan`: **no** añade historial. El plan guardado ya lleva su contexto, y meterlo
    rompería la conversación serializada.
  - `handle()`: cuando `_handle_inner` termina sin excepción (completado o pidiendo una
    aclaración), guarda `(user_message, result["text"])` en un `try`. Si falla, `warning` y la
    respuesta sale igual (D22). Las respuestas de los `except` de error de API (sin conexión,
    rate limit, créditos…) **no** se guardan.
  - La ventana y el límite se leen de `config` con valores por defecto 6 y 120:
    `config.get("historial", {}).get("intercambios", 6)` y `ventana_min`. Los tests deben poder
    cambiarlos.
- **Fuera del historial (D24):** las fotos (`ticket_handler`), los comandos `/…` y
  `try_resolve_pending`. Ninguno pasa por `Orchestrator.handle`, así que no hay que tocarlos.
- **Contenido de salud:** el historial guarda texto que puede ser de salud. Eso queda en
  MariaDB, que ya guarda esos datos, pero **en el log no se escribe el contenido del historial**,
  solo cuántos intercambios se cargaron (igual que `_TOOLS_SIN_LOG_DE_CONTENIDO`).

### Pruebas normativas de H2

Repo: `tests/test_conversation_repo.py`, contra `sebastian_test`. Orquestador:
`tests/test_orchestrator.py`, con los mocks de Anthropic que ya usa.

- **T2.1** `test_recientes_orden_cronologico_y_limite`: guardados 8 intercambios,
  `recientes(limite=6)` devuelve los 6 últimos, del más antiguo al más nuevo.
- **T2.2** `test_recientes_respeta_ventana`: un intercambio con `created_at` de hace 3 h y otro
  de hace 10 min. Con `ventana_min=120` solo vuelve el segundo.
- **T2.3** `test_recientes_solo_del_usuario`: lo de otro `user_id` no aparece.
- **T2.4** `test_planner_recibe_historial_antes_del_mensaje`: con 2 intercambios previos, la
  primera llamada al planner recibe
  `messages == [u1, a1, u2, a2, {"role": "user", "content": <mensaje actual>}]`.
- **T2.5** `test_sintesis_recibe_historial`: la llamada de síntesis lleva los mismos 4 mensajes
  previos, y su último mensaje es `user` con el prompt de síntesis.
- **T2.6** `test_limpiar_borra_mas_de_7_dias`: con filas de hace 8 días y de hace 6 días,
  `limpiar(7)` borra solo la primera y devuelve 1.
- **T2.7** `test_handle_guarda_intercambio`: tras un turno completado, `conversations` tiene
  `(mensaje, texto de la respuesta)`.
- **T2.8** `test_handle_guarda_pregunta_de_aclaracion`: si el planner pide una aclaración, se
  guarda `(mensaje, pregunta de Alfred)`.
- **T2.9** `test_error_de_api_no_se_guarda`: si el planner lanza `APIConnectionError`, la tabla
  queda vacía y la respuesta es la de siempre.
- **T2.10** `test_fallo_al_leer_historial_no_rompe_turno`: si `recientes` lanza una excepción,
  el planner recibe solo el mensaje actual, el turno se completa y queda un `warning`.
- **T2.11** `test_fallo_al_guardar_no_rompe_turno`: si `guardar` lanza una excepción,
  `handle()` devuelve la respuesta igual.
- **T2.12** `test_resume_plan_sin_historial`: al reanudar un plan pendiente, los mensajes al
  planner son exactamente los del plan guardado más el `tool_result`, sin historial delante.
- **T2.13** `test_log_no_lleva_contenido_del_historial`: con un historial que contiene
  «ZZ-SECRETO», ninguna línea de log del turno lo contiene.

### Harness de goldens

- **Aislamiento (normativo):** una fixture `autouse` en `tests/golden/conftest.py` borra
  `conversations` del usuario de golden **antes de cada golden**. Sin ella, cada golden vería el
  historial del anterior, porque ahora el orquestador guarda cada turno.
- **Campo nuevo, opcional, en `goldens.yaml`:**
  `historia: [{user: "...", bot: "..."}, ...]`. El runner lo siembra en `sebastian_test`, con
  `created_at` de hace pocos minutos, antes de llamar a `handle`. La cabecera del YAML documenta
  el campo.
- **Goldens nuevos, escritos antes del código** y pasados en la línea base, sin historial
  implementado, para ver que fallan o que pasan por casualidad:
  - **#50:** historia `¿Qué tengo hoy en el calendario?` → `Hoy no tiene nada anotado, señor.`;
    frase `¿y mañana?`. Modo `any_of`: `[calendar_list_events]` o
    `[calendar_search_events]`. Valida que «¿y mañana?» se resuelve con el turno anterior.
  - **#51:** historia `¿Qué tiempo hace en Madrid?` → `En Madrid, 21 °C y despejado.`;
    frase `¿y en Gijón?`. Modo `any_of`: `[weather_get]` o `[weather_forecast]`. Valida el
    cambio de ciudad sin repetir la intención.
  - **#52 (negativa):** misma historia que #51; frase `apunta leche a la compra`. Modo
    `exact`: `[list_add_item]`. Valida que el historial no arrastra la tool anterior.
  - Los 49 goldens actuales tienen que seguir pasando. Si alguno cambia, se cuenta en
    Desviaciones con lo observado; no se reescribe para que pase.

**[API]** Pasada completa de goldens: una de línea base (§0) y una al final de H2. Una tercera
solo si hay retoques.

**Parada:** informe `docs/fase1/H2-informe.md`, con el coste de las pasadas por modelo.

## 4. H3 — Preparar el despliegue (lo ejecuta Josem)

El programador escribe los pasos y un script de comprobación **de solo lectura**. No ejecuta
nada con sudo ni toca producción.

- **`PASOS-CON-SUDO.md` (nuevo, en `sebastian2/deploy/`), sección «Fase 1», en este orden:**
  1. Crear `sebastian_dev` con su `GRANT` (`sudo mysql`) y aplicarle las migraciones con
     `db/setup_db.sh sebastian_dev`.
  2. Crear la colección `sebastian_memory_dev` en Qdrant, con 1536 dimensiones y Cosine, la
     misma config que `sebastian_memory_test`.
  3. Añadir `Environment="SEBASTIAN_DB_NAME=sebastian_db"` y
     `Environment="SEBASTIAN_MEMORY_COLLECTION=sebastian_memory"` a **las dos** unidades
     (`sebastian.service`, `cuaderno.service`), y `systemctl daemon-reload`. **Antes** de tocar
     el `config.yaml`.
  4. Merge `--ff-only` de `fase-1` en `/data/AssistantStudies`.
  5. Solo entonces, en el `config.yaml` de producción: `mariadb.database: sebastian_dev` y
     `memory_collection: sebastian_memory_dev`.
  6. Reiniciar `sebastian.service`.
- **`deploy/comprobar_fase1.sh` (solo lectura).** Comprueba:
  - que las dos unidades llevan las dos variables (`systemctl show -p Environment`);
  - que la línea de arranque del bot dice `sebastian_db` / `sebastian_memory`;
  - que `sebastian_dev` existe y tiene las tablas de las migraciones;
  - que `sebastian_memory_dev` existe;
  - que `config.yaml` ya no menciona `sebastian_db`;
  - que no hay errores en LogCentral desde el reinicio.
- **Prueba de Josem por Telegram:** «¿qué tiempo hace en Madrid?» y luego «¿y mañana?». La
  segunda tiene que contestar sobre Madrid mañana, sin preguntar la ciudad.

**Parada:** informe `docs/fase1/H3-informe.md`. Tras la prueba de Josem, el arquitecto cierra
la fase.

## 5. Fuera de esta fase

- Memoria v1, extracción de hechos y catálogo: son la fase 2.
- Meter en el historial las fotos y los comandos (D24).
- Cambiar de modelos: Haiku 5.5 es más barato que Haiku 4.5, pero eso es otra decisión, con sus
  propios goldens.
- Retirar `sebastian_memory` (D18, fase 2).
- Quitar el worktree `AssistantStudies-comidas`: es de la fase 3 de tristras, y lo cierra Josem
  desde allí.
