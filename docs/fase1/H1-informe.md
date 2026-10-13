# H1 — Informe: producción y desarrollo separados (D19, D20, D25)

Responde a: 43ac04b (PLAN.md, «Para el programador»)

## Hecho

- Commit de código: `ee0e4f7`. **391 tests en verde** (384 de la línea base + 7 nuevos, T1.1–T1.7).
- `utils/config.py`: `load_config` aplica `SEBASTIAN_DB_NAME` → `mariadb.database` y
  `SEBASTIAN_MEMORY_COLLECTION` → `memory_collection` después de leer el YAML. `get_config()` los
  hereda. `db/connection.py` ya no lee el YAML: usa `get_config()["mariadb"]`.
- Sin nombre de producción por defecto: `tool_executor._memory_module` usa
  `config['memory_collection']` (KeyError si falta); `despertar.py` pierde `_MEMORY_COLLECTION` y
  `despertar()` recibe `memory_collection` sin valor por defecto, que `main()` lee de la config.
- Línea INFO de arranque con la BD y la colección efectivas: bot (`sebastian_bot.py`) y cuaderno
  (`despertar.main`).
- Migraciones 006–009 sin `USE`. `db/setup_test_db.sh` → `db/setup_db.sh <nombre>` (solo
  `sebastian_test`/`sebastian_dev`; el resto sale con código 1 antes de llamar a `sudo`/`mysql`).
  `db/run_migration.sh` borrado. `db/README.md` actualizado (apuntaba al script borrado).
- `conftest.py` raíz: fija las dos variables de entorno antes de importar la app y añade la fixture
  de sesión `autouse` que comprueba `SELECT DATABASE()` y hace `pytest.exit` si no es
  `sebastian_test`.
- §0: `sebastian2/config.yaml` copiado (no symlink) al worktree, con `database: sebastian_test` y
  `memory_collection: sebastian_memory_test`. Sigue gitignored. `.venv` de producción solo para
  ejecutar.

**Validación del guardarraíl (rompiéndolo):** puse a mano `SEBASTIAN_DB_NAME = "sebastian_db"` en el
`conftest.py` y lancé `pytest tests/test_db_connection.py`. Salida: `Exit: ABORTO: la conexión de la
app apunta a 'sebastian_db', no a 'sebastian_test'…`, código 1, «no tests ran». La fixture solo hace
un `SELECT DATABASE()`, así que no se escribió nada en producción. Restaurado antes de commitear
(el diff final solo lleva `"sebastian_test"`).

**Línea base (§0):**
- `pytest`: 384 passed (config ya apuntando a test).
- `pytest -m golden` **[API]**: 48/49 en la pasada completa. Falló el **#28** («recuérdame
  acostarme pronto»). No guardé el mensaje del fallo. Repetido solo (`-k golden_28`) pasa
  (sin tool, que es válido). Lo trato como intermitente del modelo; no lo he investigado más.
  No se ha cambiado ningún golden.

## Gasto

Autorizado por Josem el 2026-10-13, en la ventana del arquitecto (tope 2 $, máximo tres pasadas
completas; ver PLAN.md), y confirmado de nuevo por Josem el 2026-10-13 en la ventana del programador.

Usado: **una pasada completa de goldens (49) + una repetición del #28.** No hay medición de tokens
en el harness, así que **no tengo el coste real por modelo**: es una estimación, no un dato (orden
de magnitud 0,3–0,6 $ entre Haiku 4.5 para el planner y Sonnet 4.6 para la síntesis). Queda
muy por debajo del tope. Si el arquitecto quiere el dato exacto, hay que consultar el panel de
Anthropic. En H1 no se ha lanzado ninguna pasada más de goldens.

## Desviaciones

1. **Tests existentes tocados (no normativos, sin cambiar aserciones):**
   - `tests/test_tool_executor.py` (4 tests de memoria): su `config` ahora lleva
     `'memory_collection': 'sebastian_memory_test'`. Sin ello fallan con KeyError, que es
     justo lo que exige D20/T1.4.
   - `tests/test_cuaderno_despertar.py`: las llamadas a `despertar()` pasan
     `memory_collection="sebastian_memory_test"`, porque el parámetro ya no tiene valor por defecto.
2. **T1.6** lo hice llamando a `despertar.main()` con `get_config`, Anthropic, Qdrant y Telegram
   parcheados, y comprobando que `qdrant.scroll` se llama solo con `collection_name="coleccion_x"`.
   El plan dice «`despertar` con `memory_collection` en la config»; `despertar()` no recibe la
   config, así que el punto de lectura de la config es `main()`.
3. `db/README.md` no estaba en el plan; lo toqué porque citaba `run_migration.sh`, que se borra.
4. No hay nada en `tests/golden/conftest.py` cambiado: su `TEST_DB_NAME`/`TEST_MEMORY_COLLECTION`
   siguen como estaban (el plan pedía dejarlos).

## Cosas que he visto y no he tocado

- `docs/COMANDOS.md` y `docs/DEPLOYMENT_CHECKLIST.md` siguen citando `sebastian_db` y
  `mysql … < db/migrations/…` sin `USE`. Con las migraciones sin `USE`, esos comandos de la
  checklist funcionan igual (`mysql -u root -p sebastian_db < fichero`), pero H3 reescribe el
  despliegue; lo dejo para entonces.
- `db/verify_database.sh` apunta a `sebastian_db`; es de solo lectura, lo dejo.
- `modules/chat.py` aún usa `get_config` y se borra en H2.

## Decisiones que necesito

Ninguna.

## Parada

H1 completo. No sigo con H2 hasta tu revisión. El merge, el reinicio y el despliegue quedan para H3
y los ejecuta Josem.
