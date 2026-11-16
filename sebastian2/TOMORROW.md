# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-11-16): H2 APROBADO (`30b9f34`); H3 EN CURSO.** Datos de prueba inventados (Josem lo confirmó; goldens y tests). Goldens #67–#76: línea base 3/10, tras retocar las descripciones de `mark_as_memorable` y `salud` (`3b267da`) otra vez 3/10, y tras la regla `_REGLA_COMPROMISOS` del planner 5/10 (pasan 69, 70, 73, 74, 75). Fallan #67 (hoy es lunes: «el lunes» ambiguo), #68/#71/#72 (historial sin evento en la BD), #76 (pregunta en texto, sin llamar a `request_clarification`). Pasada completa #1–#76 hecha: 68/76, 2,04 $ (no 1,5). Fallan #62 (antiguo, intermitente conocido de la fase 2: `search_memory` en vez de `mark_as_memorable`; falta repetirlo ×3), #67, #68, #71, #72, #76 (los de antes) y #73/#74 (variación: #73 volvió a `salud`; #74 hizo dos `compromisos_crear`). Gasto de la fase 3: 3,12 $ de 4 $; quedan 0,88 $ para #62 ×3 (≈0,08) y E10 ×3 (≈0,6–0,7): al límite. Falta: E10 (cada [API] con «sí» de Josem en mi ventana). Salida de goldens: guardarla con redirección a un fichero del scratchpad.
**H3 es [API]: cada paso necesita un «sí» de Josem en mi ventana (el de la comprobación de modelos ya está hecho: ids y precios iguales).** Buzón: `git log -1 --format='%h %ad %s' --date=short --name-only -- 'docs/fase3/H*-revision.md' 'docs/fase3/H*-encargo.md' 'docs/fase3/H*-informe.md' docs/fase3/PLAN.md`.

**Fase 2 (aparte):** aprobada y a la espera del despliegue de Josem (`deploy/PASOS-CON-SUDO.md`, «Fase 2»; control clave: el `--dry-run` del paso 4). Si falla algo, Josem lo trae y el arreglo va como anexo a `docs/fase2/H4-informe.md`, en la rama `fase-2` (`/data/AssistantStudies-fase2`).

**Gotchas (fase 3):**
- **Gasto de la fase 3: 0,00 $ de 4 $** (Josem, 2026-11-16, en la ventana del arquitecto). Cada paso [API] se confirma además en mi ventana. Antes del primer [API] de H3: comprobar con la skill `claude-api` que `claude-haiku-4-5-20251001` y `claude-sonnet-4-6` siguen servidos y los precios (1/5 $ y 3/15 $ por millón).
- Migración 013 aplicada a `sebastian_test` y `sebastian_dev`, **no a producción** (el despliegue es H4, de Josem). `git commit` siempre por rutas.
- `.venv` y `config.yaml` del worktree de la fase 3 son copias propias (el `config.yaml` apunta a `sebastian_test`).
- La FK `compromisos.evento_id → events` no tiene ON DELETE y bloquea el borrado del evento aunque el compromiso esté cancelado: `cancelar_por_eventos_borrados` pone `evento_id = NULL` (desviación 1 del informe; pendiente de la respuesta del arquitecto). Cualquier `DELETE FROM events` nuevo (fixtures incluidos) tiene que pasar por ahí o borrar antes los compromisos.
- Los datos de las pruebas son inventados: el caso de la colonoscopia usa fechas y pasos, ningún nombre, teléfono ni centro reales.
- PyMySQL devuelve las columnas TIME como `timedelta`: `_hora()` en `modules/compromisos.py` las normaliza.
- Planificador (`bot/scheduler.py`): `armar_resumen` y `enviar_avisos` abren una conexión propia del pool (no el singleton `get_connection()`: cerrarlo cada minuto desde el hilo del planificador podría quitársela a un manejador). Las pruebas usan bot falso, reloj inyectado y una guarda que falla si se construye el `TeleBot` real. En pruebas, una conexión que ya leyó no ve lo que otra confirma después (REPEATABLE READ): hacer `commit()` antes de volver a leer.
- La pasada de arranque (`avisos_compromisos_arranque`) es un trabajo `date` a los 2 s con `arranque=True`; el «caducado» se loguea una vez.
- Heredado de la fase 2: `-k "golden_1"` casa también `golden_10`…: usar ids exactos. Un fallo de tool en goldens vuelca miles de líneas: filtrar con `grep -v 'INFO\|DEBUG\|^ *│\|^ *└\|Turn end'`.

**Bloqueos:** ninguno propio; H3 espera la revisión de H2 y el «sí» de Josem al gasto [API].
