# H1g — Informe del programador (fase 4, D72): modo depuración temporal `/debug`

Responde a: `c13e0dc` / H1f-informe (H1g-encargo, `4dfba4b`).
Commit en `fase-4`: `56ca23b`. Suite completa: **1186 pruebas** pasan (1168 + 18), sin API. Gasto: 0 $.

## Hecho

- **R17 — el comando (`bot/handlers.py`):** `/debug [min]` activa (30 por defecto, como mucho 120) y `/debug off` apaga (también `OFF`).
  - Solo para el propietario del vault (`propietario_vault(config)`). A cualquier otro: «Este comando no está disponible», sin log y sin más.
  - Con un valor que no es un entero, con menos de 1, con decimales o con más de un argumento: el mensaje de uso, y no activa nada.
  - Respuestas: «Depuración activa hasta las HH:MM. Traza en <ruta>» y «Depuración apagada». La hora es la del servidor. Si activar falla: «No he podido activar la depuración», sin dejarla activa.
  - Sale en `/ayuda`. El estado es `{user_id: caduca_en}` en la memoria del proceso: un reinicio lo apaga.
- **R18 — la traza (`core/depuracion.py`, módulo nuevo):**
  - Ruta `<logfolder>/debug/debug-<user>-<AAAAMMDD>.jsonl`. Directorio 0700 (se crea con ese modo y, si ya existía con otro, se deja en 0700). Fichero 0600 creado con `os.open(..., 0o600)`.
  - Una línea JSON `{ts, turno, etapa, datos}` escrita a mano: ni loguru ni `get_logger` para el contenido.
  - `activa(user_id)` mira la caducidad cada vez; al caducar escribe una sola vez «Depuración desactivada (caducó) | user=…».
  - A LogCentral solo van «Depuración activada | user=… | minutos=N» y «Depuración desactivada (off|caducó) | user=…».
- **R19 — qué se traza** (solo turnos de un usuario con la traza activa **al empezar el turno**):
  - `mensaje`: el texto del usuario.
  - `planner`: por cada llamada, `stop_reason`, el texto si lo hay y cada `tool_use` con `name` e `input` (los dos bucles, el normal y el de reanudar un plan).
  - `tool`: el resultado, recortado a 4000 con la marca «…[recortado: N caracteres más]»; si falla, solo «la tool falló».
  - `extractor`: el `texto` que recibe, `catalogo_chars` (no el catálogo), el `bloque.input` crudo (el extractor lo deja en `ultimo_input`) y los hechos validados; si falla, la clase de la excepción.
  - `memoria_consulta`: los parámetros y la salida.
  - `alfred`: el resumen de tools que recibe (recortado a 12000), la `nota_planner`, el `stop_reason` y el texto final. Más `alfred_pregunta` si pide aclaración.
  - **El contexto del turno:** un id de 8 caracteres que pone el orquestador y que pasa al ejecutor (`turno_debug`) y de ahí a la memoria (`turno=`). **Sin traza activa no existe, y las llamadas al ejecutor y a la memoria son exactamente las de antes** (por eso no cambia ningún esperado de `test_tool_executor.py`). El único estado nuevo de módulo es el de R17.
- **R20 — limpieza:** `limpiar()` borra los `debug-*.jsonl` con más de 24 h (por `mtime`), al arrancar (`setup_handlers`) y al activar. Registra solo «Depuración: limpieza | borrados=N». No toca otros ficheros.
- **Un fallo al escribir** la traza (o de limpieza) no rompe el turno: un `WARNING` con usuario y clase de la excepción, sin contenido.
- **D72** está citado en un comentario en cada costura (el módulo, el orquestador, el ejecutor, el servicio, el extractor y el comando).

## Pruebas (18 nuevas en `tests/test_depuracion.py`, bot y reloj falsos, datos inventados)

1. Otro usuario: `/debug`, `/debug 30` y `/debug off` dan «no disponible», no activan nada, no crean directorio y no escriben ni un log.
2. `/debug 30` activa (hasta las 15:30, con la ruta), `/debug off` apaga, `/debug` da 30, `/debug 500` se queda en 120; `abc`, `0`, `-5`, `2.5` y `10 20` dan el uso. `/debug` sale en `/ayuda`, y a LogCentral solo van los dos avisos.
3. Caducidad con reloj falso: a los 29 min sigue activa, a los 31 da `False` y «caducó» sale una sola vez; después no se escribe nada.
4. **Un turno completo** (planner → `mark_as_memorable` → extractor real con cliente falso → planner → Alfred, con ejecutor y servicio reales contra `sebastian_test`) deja `mensaje, planner, extractor, tool, planner, alfred`, con un solo id de turno y todos los campos de R19. La marca `ZZDEBUG` **está en el fichero y no está** en ningún logger del código (orquestador, ejecutor, servicio, extractor, repositorio, depuración) **ni en stdout/stderr** (`capfd`, que recoge loguru).
5. Consulta de memoria con parámetros y salida; resultado de una tool de 6000 caracteres recortado con marca; `recortar` en los bordes (4000 y 4001).
6. **Sin traza activa:** no se crea ni el directorio, el turno sale igual y el ejecutor llama a la memoria como antes (`guardar.assert_called_once_with('99999', 'x', mensaje=None)`).
7. **Solo el usuario activado:** con la traza activa para otro, un turno de este no escribe nada.
8. **Permisos:** directorio 0700 y fichero 0600 **con `umask(0)`**, así que el modo lo pone el código y no el umask; y un directorio que ya existía con 0755 queda en 0700.
9. **Limpieza:** un fichero de 25 h se borra, uno de 1 h y uno ajeno (`otra-cosa.txt`, 48 h) se quedan; corre al activar y al arrancar; sin directorio no hace nada.
10. **Fallos:** con el directorio de trazas imposible de crear, el turno sale igual y solo hay `WARNING`s sin contenido; si `activar` falla, el comando lo dice y no queda activa; y un fallo del extractor deja su línea de traza sin romper.

Sin el cableado (`orchestrator.py`, `servicio.py`, `handlers.py` apartados un momento), fallan 10 de las 18. **La suite** pasó sin tocar ningún esperado: no se ha editado ninguna prueba existente.

## Gasto

0 $. Sin API.

## Desviaciones

1. **Un detalle de más sobre el encargo:** recorto el resumen de tools que recibe Alfred a 12000 caracteres (el encargo solo fija 4000 para cada tool). Sin tope, un turno con varias tools grandes haría ficheros enormes.
2. Todos los ficheros con Edit/Write. De nuevo, `git stash` un momento para comprobar que las pruebas fallan sin el arreglo, y `stash pop` después. Y un comando de Bash sin efecto (un `cat` vacío a un fichero de mi carpeta temporal), sin tocar el repo.

## Comprobado de forma solo lectura

LogCentral (`/data/logcentral/vector/vector.toml`) lee **solo** `/data/AssistantStudies/sebastian2/logs/sebastian.log` (ruta exacta, sin comodín), así que `logs/debug/` no entra en LogCentral.

## Cosas que conviene saber

1. **Ya había contenido en los logs, en `bot/handlers.py`, fuera de este parche.** `handle_text` escribe `Processing text from …: {message.text[:50]}...` (nivel INFO, va a LogCentral) y `logger.debug(f"Orchestrator response: {response_text[:100]}")`. Es lo que D42 quiere evitar, y es anterior a H1g. No lo he tocado. Lo señalo porque hace que «el contenido no sale de la traza» solo sea cierto para lo que escribe este módulo, no para esos dos logs de siempre. Se arreglaría con un encargo de dos líneas.
2. **La limpieza corre solo al arrancar y al activar (como pide R20).** Un fichero de hoy no se borra a las 24 h por sí solo: se borra la próxima vez que se reinicie el servicio o que se active `/debug`, cuando ya tenga más de 24 h. Si prefieres que se borre a su hora, basta con llamar a `limpiar()` también desde el planificador cada 15 minutos o al caducar. Mientras tanto, se puede borrar a mano (abajo).
3. **Se traza el turno que empieza con la traza activa.** Si `/debug` se activa mientras un turno está en curso, ese turno no se traza.
4. **El plan pendiente** (`request_clarification`) también se traza al reanudarlo, porque comparte el planner y las tools.

## Despliegue (de Josem)

`main` está en `0ba236a` (H1e); **H1f (D71), aprobado, todavía no está desplegado**, así que este merge trae también el H1f. Hash para volver atrás: `0ba236a`.

Merge y reinicio:

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

Volver atrás, si hiciera falta:

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard 0ba236a && sudo systemctl start sebastian.service`

## Cómo leer la traza (sin sudo)

Tras `/debug 30` en Telegram, el bot contesta con la ruta. Suele ser `/data/AssistantStudies/sebastian2/logs/debug/debug-<tu id>-AAAAMMDD.jsonl`. Solo la lee el usuario `ubuntu`.

- Todo, una línea por etapa: `jq -c '[.ts, .turno, .etapa, .datos]' <fichero>`
- Solo lo que devolvió el extractor: `jq 'select(.etapa=="extractor") | .datos' <fichero>`
- Lo que mandó el planner: `jq 'select(.etapa=="planner") | .datos.tools' <fichero>`
- El último turno entero: `jq -s 'group_by(.turno) | last' <fichero>`
- Para leerlo despacio: `jq . <fichero> | less`
- Apagar: `/debug off` en Telegram. Borrar a mano: `rm /data/AssistantStudies/sebastian2/logs/debug/debug-*.jsonl`

## Decisiones que necesito

1. ¿Quieres que arregle, en un encargo aparte, los dos logs con contenido de `handle_text` (punto 1 de arriba)?
2. ¿Llamo a `limpiar()` también desde el planificador, para que las trazas se borren a las 24 h sin depender de un reinicio (punto 2)?

---

# Anexo — H1h: R21 (logs de `handle_text`) y R22 (limpieza periódica)

Responde a: `9c2b97c` (H1g-revision).
Commit en `fase-4`: `67cc115`. Suite completa: **1190 pruebas** pasan (1186 + 4), sin API. Gasto: 0 $.

## Hecho

- **R21 (`bot/handlers.py`, D42):** `handle_text` ya no escribe el texto del usuario ni la respuesta en el log.
  - `Processing text from <usuario> | chars=N` en lugar de los 50 primeros caracteres.
  - `Orchestrator response | chars=N` en lugar de los 100 primeros.
  - Busqué otros logs con el texto del usuario o de la respuesta en `bot/`: no hay más.
- **R22 (`core/depuracion.py` y `bot/scheduler.py`, D72):**
  - **Planificador:** tarea nueva `limpiar_depuracion`, cada hora, con `max_instances=1` y `coalesce`, que llama a `depuracion.limpiar`.
  - **Al apagar** (`apagar`) y **una sola vez al caducar** (`activa`), `limpiar()` también corre. Con lo que ya había (arrancar y activar), las trazas se borran a las 24 h sin depender de un reinicio.

## Pruebas (4 nuevas en `tests/test_depuracion.py`)

1. **R21, con marca `ZZDEBUG`:** un mensaje con la marca, y una respuesta con la marca, pasan por `handle_text` con orquestador falso. El usuario recibe la respuesta; la marca **no está** en ninguna llamada del logger (`bot.handlers.logger` parcheado), y las líneas son exactamente las nuevas, con `chars=`. Segunda pasada con el logger de verdad: nada en stdout ni stderr.
2. **R22, planificador:** la tarea está registrada, cada 3600 s, `max_instances=1`, `coalesce`, y su función es `limpiar`; al ejecutarla se borra la traza de 30 h y se queda la de 1 h.
3. **R22, al apagar:** `/debug off` borra una traza de 30 h.
4. **R22, al caducar, con reloj falso:** a los 29 min no limpia; a los 31, limpia **una sola vez** aunque se llame dos veces a `activa`, y borra la traza vieja.

Sin el cambio, las 4 fallan. **La suite**, salvo un esperado, pasó sin tocar nada.

## Un esperado que cambia

`test_23_y_25_registrar_jobs_deja_la_tarea_de_vigilancias_y_las_que_ya_existian` (`tests/test_vigilancias_ronda.py`) comparaba con `==` el conjunto exacto de tareas del planificador. Con R22 hay una más, `limpiar_depuracion`, así que la he añadido a ese conjunto, con un comentario que lo explica. El resto de lo que comprueba (intervalos, `max_instances`, `coalesce`, argumentos) no cambia. `test_las_tareas_se_registran_en_el_planificador_del_bot` usa `<=` y no se ve afectado.

## Gasto

0 $. Sin API.

## Desviaciones

Ninguna. Todos los ficheros con Edit/Write. De nuevo, `git stash` un momento para comprobar que las pruebas fallan sin el cambio, y `stash pop` después.

## Despliegue (de Josem)

`main` sigue en `0ba236a` (H1e): **H1f y H1g, aprobados, todavía no están desplegados**, así que este merge trae H1f, H1g y H1h. Hash para volver atrás: `0ba236a`.

Merge y reinicio:

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

Volver atrás, si hiciera falta:

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard 0ba236a && sudo systemctl start sebastian.service`

## Decisiones que necesito

Ninguna.
