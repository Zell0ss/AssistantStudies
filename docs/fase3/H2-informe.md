# H2 — informe (fase 3): planificador, resumen y avisos

> Responde a: fbf1b93 (H1-revision, «Para el programador»). Programador, 2026-11-16. Rama `fase-3`, commits
> `b585960` (R1 y docstrings) y `587b091` (H2). Todo sin API y sin Telegram real.

## Hecho

- **R1:** `calendar_remove_event` devuelve `compromisos_cancelados: n` cuando `n > 0`. La `n` cuenta solo los
  **pendientes** que pasan a `cancelado` (no los hechos ni los ya cancelados). Prueba:
  `test_remove_event_informa_compromisos_cancelados` (y tres más: sin campo si no hay compromisos, suma de varios
  eventos y la cuenta sin hechos). La descripción de la tool no se toca.
- **Docstring de `momento_efectivo`:** «solo se llama sobre pendientes» y «`minutos` va en hora de reloj».
- **`bot/scheduler.py`** (`start_daily_reminder` conserva su nombre: `sebastian_bot.py` no cambia):
  - **`armar_resumen(usuario, ahora, conn=None, hora_resumen=08:00) -> str | None`**, función pura sobre la BD,
    con tres bloques (agenda, «Para hoy», «Antes del próximo resumen»). Sin LLM. Si no hay nada, `None`.
  - **`_send_daily_reminder`**: arma y envía; si es `None`, no manda nada (D47).
  - **`enviar_avisos(bot, user_ids, reloj=None, arranque=False)`**: la tarea de cada minuto, D51 al pie de la letra
    (ventana `ahora − 2 h < m ≤ ahora`, `aviso_para ≠ m`, se escribe **después** de enviar).
  - **`_registrar_jobs`**: `daily_calendar_reminder` (cron a `calendar.daily_reminder_time`), `avisos_compromisos`
    (cada minuto, `max_instances=1`, `coalesce=True`), `avisos_compromisos_arranque` (una pasada con
    `arranque=True` a los 2 s de arrancar) y `cleanup_conversations`. Sin unidades systemd.
  - Smoke con el `BackgroundScheduler` real, bot falso y `sebastian_test`: los trabajos se registran, la pasada de
    arranque corre a los 2 s y no hay errores.
- **`CalendarModule.list_events(..., hoy=None)`** y **`CompromisosModule.registrar_aviso`**, las dos costuras que
  necesitaba el reloj inyectado.
- **Pruebas:** las 11 normativas de §3-H2 con sus nombres, más las mías (resumen de los días 15 y 17, sección vacía,
  hora del resumen configurable, aislamiento, fallos por usuario, idempotencia, ventana de 2 h, registro de las
  tareas y la guarda). Bot falso y reloj inyectado en todas; una guarda `autouse` hace fallar el test si se
  construye un `telebot.TeleBot` real (comprobada con su propia prueba).

**`pytest -m "not golden"`: 731 antes (H1) → 767 después** (+4 de R1, +32 del planificador). 0 fallos.

## Gasto

**0,00 $.** Sin API. Autorizado para la fase 3: hasta 4 $ (Josem, 2026-11-16, en la ventana del arquitecto). Por
modelo: Haiku 0, Sonnet 0. **Acumulado de la fase 3: 0,00 $.**

## Desviaciones

1. **Formato del resumen.** `test_resumen_agenda_sin_compromisos_igual_que_hoy` exige el texto de hoy, y el plan
   enseña otro encabezado («📅 Buenos días. Hoy, jueves 17:»). **Gana el test:** conservo el encabezado y el cierre
   de hoy (`📅 **Buenos días! Tu agenda de hoy:**` … `¡Que tengas un buen día!`) y meto las secciones nuevas
   entre la agenda y el cierre, con `✅ **Para hoy:**` y `⏰ **Antes del próximo resumen:**`. Un día sin agenda pero
   con compromisos abre con `📅 **Buenos días!**`. Los `**` salen literales en Telegram porque `send_message` no
   usa `parse_mode`: es lo que ya pasaba.
2. **Una conexión propia por tarea, no el singleton `get_connection()`.** `close_connection()` cierra la conexión
   de todo el proceso; llamarlo cada minuto desde el hilo del planificador podría quitársela a un manejador de
   Telegram en mitad de una consulta. Los avisos y el resumen piden una al pool (`init_pool().connection()`) y la
   devuelven. `_cleanup_conversations` sigue con el singleton, una vez al día, como antes.
3. **Cuándo se loguea un «caducado».** El plan pide una línea por cada aviso descartado, pero la tarea corre cada
   minuto: un compromiso que caducó hace una semana y nunca se avisó saldría 1.440 veces al día. La escribo **una
   vez**: en el minuto en que el aviso cruza las 2 h, o, con `arranque=True`, para todos los que un reinicio haya
   dejado atrás. Un aviso ya enviado nunca es «caducado».
4. **Los logs del resumen:** la línea de «enviado» ya no lleva el número de eventos (no hace falta), y el error solo
   lleva la clase de la excepción, no su texto (puede contener el del mensaje). Mismo criterio que los avisos.
5. **Firmas con más parámetros que el plan:** `armar_resumen(usuario, ahora, conn=None, hora_resumen=...)`:
   `conn` para las pruebas y `hora_resumen` para saber qué es «antes del próximo resumen» (la hora configurada, no
   un 08:00 fijo).
6. **La pasada de arranque es un trabajo `date`** (a los 2 s, `misfire_grace_time=60`), no un `next_run_time` del
   trabajo de cada minuto: así lleva `arranque=True` y el trabajo periódico no.

## Decisiones que necesito

1. **¿Vale el formato de la desviación 1,** o prefieres el encabezado del plan (y entonces se cambia la prueba del
   «igual que hoy», que es tuya)?
2. **Un compromiso del 17 sin hora no sale en el resumen del 16.** La tabla del caso dice «resumen del 16,
   "mañana…"» para «llevar el parte de interconsulta», pero §2.3 define «Antes del próximo resumen» solo con
   compromisos **con hora**. El parte sale el 17 a las 08:00, en «Para hoy», con la cita a las 9:30 todavía por
   delante. Lo dejo como el plan, y lo traigo por si el caso quería otra cosa.
3. **Lo que acepto como riesgo, ya implícito en D51:** si Telegram recibe el aviso pero la BD falla al escribir
   `aviso_para`, el aviso se repite al minuto siguiente. Es el orden que pide el plan (mejor repetir que perder).

## Para la revisión

- La prueba real de D48 sigue siendo el aviso de las 01:00 del 17/12; aquí solo se demuestra con reloj inyectado.
- Producción: nada nuevo. El planificador arranca con el bot, así que llegará con el reinicio de H4 (Josem).
- Siguiente paso, tras tu revisión: **H3** (planner y goldens, **[API]**). Antes del primer [API] compruebo con la
  skill `claude-api` los ids de modelo y los precios, y pido el «sí» de Josem en mi ventana.
