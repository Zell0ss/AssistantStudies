# H1 — informe (fase 3): compromisos, tabla, repositorio y tools

> Responde a: 892ee7e (PLAN, «Para el programador»). Programador, 2026-11-16. Rama `fase-3`, commits
> `8438fc2` y `962cee4`. Todo sin API.

## Hecho

- **Migración `013_compromisos.sql`**, el SQL del plan §2.1 tal cual, sin `USE`. Aplicada a
  `sebastian_test` y `sebastian_dev`; **no a producción**.
- **`modules/compromisos.py`**:
  - `validar_forma` (las reglas de forma);
  - `momento_efectivo` y `describir`;
  - `CompromisosModule`: `crear`, `listar`, `completar`, `borrar` y `pendientes`.
  - `crear` es todo o nada, de 1 a 20, y devuelve cada compromiso con su momento ya calculado y escrito en
    llano («jueves 17/12 a las 01:00»).
  - Reloj inyectado (`reloj=`); en ningún sitio `datetime.now()` directo, salvo como valor por defecto del
    reloj.
- **`core/tools/compromisos_tools.py`**: las cuatro tools y su familia (`FAMILY_SUMMARY`) en `ALL_TOOLS`,
  `_TOOL_FAMILIES` y el digest. Despacho en `ToolExecutor`.
- **`calendar_remove_event`** (por título y por id): cancela los compromisos atados en la misma transacción
  que el borrado. **`calendar_add_note`**: descripción ampliada con el texto del plan §2.2.
- **Pruebas:** las 14 normativas de §3-H1 están, con los nombres del plan, más las mías (forma, ejecutor,
  descripciones, logs). Todas en `sebastian_test`, sin API.

**`pytest -m "not golden"`: 683 antes → 731 después** (+37 en `test_compromisos_module.py`, +11 en
`test_compromisos_tools.py`). 0 fallos, 90 goldens deseleccionados como siempre.

## Gasto

**0,00 $.** Sin API. Autorizado para la fase 3: hasta 4 $ (Josem, 2026-11-16, en la ventana del arquitecto).
Por modelo: Haiku 0, Sonnet 0. **Acumulado de la fase 3: 0,00 $.**

## Desviaciones

1. **La FK bloquea el borrado del evento aunque el compromiso esté cancelado** (lo comprobé en
   `sebastian_test`: error 1451 con una fila `cancelado` apuntando al evento). El plan §2.1 dice «la FK no lleva
   `ON DELETE`: el código lo hace primero», pero cancelar no suelta la referencia, así que el `DELETE` del evento
   falla. **Lo resuelvo en el código, sin tocar el SQL del plan:** `cancelar_por_eventos_borrados` pone los
   pendientes en `cancelado` **y** `evento_id = NULL` en todos los compromisos del evento (pendientes, hechos y
   cancelados), en la misma transacción. Lo hecho sigue hecho; solo pierde el enlace. La alternativa equivalente
   sería `ON DELETE SET NULL` en la FK; no la he tomado porque cambia un contrato que es tuyo.
2. **Eventos recurrentes:** el plan no dice nada y `compromisos_crear` los **rechaza** como destino de un
   compromiso atado («¿a qué ocurrencia?»), con un mensaje que manda crearlo suelto. Un evento de todo el día
   rechaza `minutos` (no tiene hora) y admite `dias_*` con `hora`, como dice §2.1.
3. **Los textos de los compromisos no van a los logs del ejecutor:** las cuatro tools están en
   `_TOOLS_SIN_LOG_DE_CONTENIDO`, junto a `salud` y la memoria. El plan solo lo pide para los avisos (§2.3); lo
   hago también aquí por D52 y por la lección de R12 (la preparación de una prueba médica es el caso de uso).
4. **`tests/golden/conftest.py`** (fixture, no `goldens.yaml`): ahora borra `compromisos` del usuario de los
   goldens antes que sus eventos, por la FK. Sin esto, la primera pasada de H3 con un evento atado fallaría al
   limpiar. No lo he podido ejecutar (es [API]); el cambio es de una línea.
5. **Añadidos para H2, que el plan no nombra:** `CompromisosModule.pendientes(evento_id=None)` devuelve los
   pendientes con su `Momento` tipado (datetimes), el título del evento y `aviso_para`; es lo que usará el
   planificador, y `listar` es su serialización. `Momento.problema` cubre un evento que ha perdido su hora o su
   fecha (por ejemplo, pasado a «todo el día» con `calendar_update_event`): ese compromiso **sale siempre en
   `listar`** con `cuando: null` y el motivo, en vez de desaparecer o romper.
6. **Descripciones:** las líneas de §2.2 están. Las de `compromisos_listar/completar/borrar` y las de los campos
   del esquema son mías. En `compromisos_crear` añadí «busca antes el evento con `calendar_search_events` o
   `calendar_find_by_datetime`», por el riesgo de §5 (que el planner cree compromisos sueltos con fechas y D50
   no se cumpla). **No he tocado la descripción de `calendar_remove_event`**: no dice que cancela los
   compromisos; no lo cambio sin saber si quieres que Alfred lo cuente (movería goldens de calendario).

## Decisiones que necesito

1. **¿Vale la desviación 1** (código en vez de `ON DELETE SET NULL`)? Si prefieres la FK, es una migración
   `014` de dos líneas y se quita el `evento_id = NULL` del código.
2. **¿Vale rechazar los eventos recurrentes** como destino (desviación 2), o quieres otra regla (por ejemplo,
   atar a la próxima ocurrencia)? Para la colonoscopia no hace falta.
3. **Aviso para H3:** `tasks_create` dice «recuérdame hacer Y en X» y `compromisos_crear` dice «cosas que tiene
   que hacer». Son familias distintas (tareas de proyecto frente a la vida del usuario), pero las frases se
   pisan. Lo vigilaré en la línea base de #67–#76; si #67 cae en `tasks_create`, lo traigo.

## Para la revisión

- Esquema real: `DESCRIBE compromisos` en `sebastian_test` y `sebastian_dev`.
- `sebastian2/.venv` y `config.yaml` del worktree de la fase 3 son copias propias (sin symlinks); `config.yaml`
  apunta a `sebastian_test`, igual que el de la fase 2.
- Siguiente paso, tras tu revisión: **H2** (planificador). No empiezo sin ella.
