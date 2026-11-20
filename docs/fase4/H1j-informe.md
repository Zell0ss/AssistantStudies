# H1j — Informe del programador (fase 4, D74): con historial, las consultas también pasan por `search_memory`

Responde a: `563370b` / H1i-informe (H1j-encargo, `1ee757c`).
Commit en `fase-4`: `2aa1969`. Suite completa: **1210 pruebas** pasan (1205 + 5), sin API en las pruebas.

## Resultado en una línea

**Goldens: G1–G3 4/6 (no llega a 6/6), controles 2/2. NO APROBADO.** G1 y G3 aciertan las dos veces; **G2 falla las dos veces**. No he tocado la frase después de ver el resultado: decides tú.

## Hecho

- **R25 (`core/orchestrator.py`):** `_REGLA_ACCIONES_CON_HISTORIAL` lleva ahora, en la misma regla y justo después de lo de guardar, la frase del encargo:
  > «Si el usuario pregunta qué consta de él, de su gente, de sus cosas o de sus proyectos («¿qué sabes de…?», «¿qué datos tienes de…?», «¿cuál es mi…?»), tu respuesta de este turno tiene que ser una llamada a `search_memory`, aunque el historial parezca tener el dato: lo que se dijo en otro turno no es fuente (D26).»

  El comentario de D43 cita ahora D43 y D74. Lo que decía la regla sobre guardar no cambia (una prueba lo comprueba con el texto entero).
- **Pruebas sin API** (`tests/test_regla_consultas.py`): la frase está en el system del planner, después de la regla de guardar y antes de las reglas siguientes (compromisos); y forma parte de la misma regla. **La suite** pasó sin tocar ningún esperado.
- **Script de goldens** `scripts/memoria/golden_consultas.py` (+ `tests/test_golden_consultas.py`, 5 pruebas con cliente falso): planner real de producción (prompt, tools, modelo y techo), índice inventado (`- yo (tú): telegram_id, nota`, y `- Paco (persona): alergia` para G3) e historial inventado de 6 intercambios en el que el asistente ya ha dicho el valor.

## Goldens ([API], Haiku 4.5)

| Caso | Pasada | Qué llamó el planner | Resultado |
|---|---|---|---|
| G1 «¿Qué datos tienes de mí en Telegram?» | 1 | `search_memory({"query": "Telegram"})` | acierta |
| G1 | 2 | `search_memory({"query": "Telegram"})` | acierta |
| **G2 «¿Cuál es mi id de Telegram?»** | 1 | **ninguna tool**, `end_turn`; texto: «Su telegram_id es 700111222, señor.» | **falla** |
| **G2** | 2 | **ninguna tool**, `end_turn`; el mismo texto | **falla** |
| G3 «¿Qué sabes de Paco?» | 1 | `search_memory({"query": "Paco", "entidad": "Paco"})` | acierta |
| G3 | 2 | `search_memory({"query": "Paco", "entidad": "Paco"})` | acierta |
| G4 control «Recuerda que mi color favorito es el verde» | 1 | `mark_as_memorable({"texto": "Mi color favorito es el verde"})` | acierta |
| G5 control «¿Qué tiempo hace en Madrid?» | 1 | `weather_get({"city": "Madrid"})`, sin `search_memory` | acierta |

**G1–G3: 4/6. Controles: 2/2.** Salida completa guardada fuera del repo (scratchpad, `f4_h1j.txt`).

## Qué creo que pasa con G2

- **La respuesta del planner es, palabra por palabra, la del historial** («Su telegram_id es 700111222, señor.»). Es el mismo fallo de D43, y la frase nueva no basta en este caso.
- **Se parece al caso de producción, y es duro:** el historial de G2 contiene la misma pregunta («¿Cuál es mi id de Telegram?») ya contestada en texto. G3 también tiene su misma pregunta contestada en el historial («¿Qué sabes de Paco?») y aquí sí consulta, así que lo que cambia es la forma de la pregunta.
- **Mi lectura:** «¿cuál es mi id…?» pide *un dato concreto* que el planner ve en el historial, y lo trata como una pregunta de conversación. «¿Qué datos tienes de…?» y «¿qué sabes de…?» suenan a «consulta tu memoria». Es una hipótesis con 2 pasadas.

## Gasto

**0,0385 $** de los 0,10 autorizados (8 llamadas de Haiku 4.5: 0,0152 la primera, con la escritura de caché, y entre 0,0031 y 0,0035 las demás). Autorizó Josem: «A por él» (en la ventana del arquitecto, por el encargo) y «adelante» en mi ventana. Fase 4 acumulada ≈ 0,136 $ de 3 $. Quedan 0,0615 $ de la autorización.

## Desviaciones

1. **G4 y G5 llevan el mismo historial que G1** (6 intercambios). El encargo solo pide historial para G1–G3. Lo puse para que los controles sean tan exigentes como producción, y los dos aciertan.
2. Todos los ficheros con Edit/Write. De nuevo, ninguna comprobación con `git stash` esta vez: no hacía falta (la prueba de R25 comprueba la presencia de la frase).

## Qué propongo (sin aplicar)

La frase, tal como está, deja pasar G2. Tres opciones, de más a menos recomendable:

1. **Reforzar la frase con el caso concreto**, en la misma regla: añadir algo como «También si te piden un dato suyo concreto («¿cuál es mi id de Telegram?», «¿cuándo es mi cumpleaños?») y en el historial ya lo dijiste o lo contestaste: se consulta igual, con `entidad` `yo`». Repetir G2 (2 pasadas) y, para no perder lo ganado, G1 y G3 (2 cada una) y un control: 8 llamadas, ≈ 0,04 $, dentro de lo que queda de la autorización pero **con tu «sí» de nuevo** y con la frase nueva aprobada por el arquitecto.
2. **Aceptar el límite.** Alfred ya contesta bien («No me ha llegado ningún resultado de memoria… ¿quiere que lo consulte?», lo vimos en la traza de las 16:43): cuesta un turno de ida y vuelta, no da un dato falso a Josem.
3. **Guarda en código** (por ejemplo: si el planner cierra sin tools y con un texto que contiene el valor de algo que está en el índice…). No lo recomiendo: es una heurística frágil y D26 pide que lo resuelva el prompt.

## Despliegue (de Josem)

`main` está en `dc0ca28` y es ancestro de `fase-4`. **Si no se aplica la opción 1, el despliegue de R25 parece seguro** (los controles G4 y G5 pasan y G1 y G3 aciertan), pero deja G2 sin resolver. No he medido los mismos casos sin R25, así que no puedo decir cuánto mejora G1 y G3 respecto a antes. Hash para volver atrás: `dc0ca28`.

Merge y reinicio:

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

Volver atrás, si hiciera falta:

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard dc0ca28 && sudo systemctl start sebastian.service`

## Decisiones que necesito

1. ¿Qué opción de «Qué propongo»? Si la 1, ¿con esa frase u otra? Y un «sí» de Josem para otras 8 llamadas (≈ 0,04 $).
2. ¿Se despliega R25 tal cual mientras tanto (G1 y G3 aciertan, controles intactos) o se espera a resolver G2?

---

# Anexo — R25b y segunda vuelta de goldens

Responde a: `5e172b1` (H1j-revision).
Commit en `fase-4`: `baaf6c8`. Suite completa: **1213 pruebas** pasan (1210 + 3), sin API en las pruebas.

## Resultado en una línea

**G2 sigue fallando (0/2 otra vez, 0/4 entre las dos vueltas). G2b, el caso nuevo, acierta. G1, G3 y G4 sin regresión.** Criterio (3/3 en G2 y G2b): **1/3, NO APROBADO.** Paro, como pedías, y no he retocado la frase.

## Hecho

- **R25b (`core/orchestrator.py`):** la frase de R25 está sustituida por la tuya, en el mismo sitio de `_REGLA_ACCIONES_CON_HISTORIAL`, con un comentario que explica el cambio. **Una sola diferencia con tu texto:** el prompt va sin los asteriscos de negrita (`**nunca contestes…**`), porque el resto del prompt del planner no usa markdown; las palabras son las tuyas.
- **Prueba de la frase** actualizada (`tests/test_regla_consultas.py`). Lo que dice la regla sobre guardar no cambia.
- **Script de goldens:** `--vuelta 2` lanza la segunda vuelta (G2 ×2, G2b, G1, G3, G4), con G2b (índice `yo (tú): cumpleanos, telegram_id, nota`, historial de 6 intercambios con «Su cumpleaños es el 12 de marzo, señor.») y su propio criterio. 3 pruebas nuevas con cliente falso.

## Goldens, segunda vuelta ([API], Haiku 4.5)

| Caso | Pasada | Qué llamó el planner | Resultado |
|---|---|---|---|
| **G2** «¿Cuál es mi id de Telegram?» | 1 | **ninguna tool**, `end_turn`; «Su telegram_id es 700111222, señor.» | **falla** |
| **G2** | 2 | **ninguna tool**, `end_turn`; el mismo texto | **falla** |
| **G2b** «¿Cuándo es mi cumpleaños?» | 1 | `search_memory({"query": "cumpleaños", "entidad": "yo", "atributo": "cumpleanos"})` | acierta |
| G1 «¿Qué datos tienes de mí en Telegram?» | 1 | `search_memory({"query": "telegram"})` | acierta |
| G3 «¿Qué sabes de Paco?» | 1 | `search_memory({"query": "Paco", "entidad": "Paco"})` | acierta |
| G4 «Recuerda que mi color favorito es el verde» | 1 | `mark_as_memorable({"texto": "Mi color favorito es el verde"})` | acierta |

**G2 y G2b: 1/3. G1, G3 y G4: 3/3 (sin regresión).** Salida completa fuera del repo (scratchpad, `f4_h1j_v2.txt`).

## Qué enseña

- **La regla generaliza:** G2b, con la misma estructura que G2 (la misma pregunta ya contestada en el historial, un dato concreto), consulta, y con `entidad` y `atributo` bien puestos. Así que la frase no es un parche a medida de Telegram; funciona para otro dato.
- **G2 es el caso que no cede, con la frase vieja y con la nueva, y siempre con la misma respuesta literal del historial.** Entre G2 y G2b lo único que cambia es el dato: **«mi id de Telegram».**
- **Mi hipótesis (sin comprobar):** «mi id de Telegram» es algo que el propio bot conoce por la conversación (existe `/id_me`), y el planner lo trata como un dato del contexto, no como memoria. Con otro dato (G2b) no pasa. Si es así, no es un fallo de la regla sino de ese dato concreto. Una pasada de G2 con otro dato «del contexto» lo comprobaría.
- **Otra pista, de posición:** el comentario de D43 dice que la regla funcionó «al final, justo antes de decidir», pero en `_planner_system` la regla va **antes** de compromisos, fechas y «buscar no termina el turno». No está al final. Probar a moverla (o la frase de consultas sola) al final del system es una variable distinta que aún no se ha medido.

## Gasto

**0,0203 $** (6 llamadas de Haiku 4.5, entre 0,0032 y 0,0036 $ cada una). Dentro de lo ya autorizado por Josem (≤ 0,10 $ para este hito; «A por él» y «adelante»). H1j acumula **0,0588 $** de 0,10; fase 4 ≈ **0,157 $** de 3 $. Quedan 0,0412 $ de la autorización.

## Desviaciones

Los asteriscos de la frase (arriba). Todos los ficheros con Edit/Write.

## Qué propongo (sin aplicar)

1. **Probar la posición:** mover la frase de consultas a una constante propia al final del system del planner (después de `_REGLA_BUSCAR_NO_TERMINA`), y repetir G2 ×2 y G2b, G1 y G3 (6 llamadas, ≈ 0,02 $, cabe en lo que queda).
2. **Aceptar el límite** de ese dato concreto: G2b generaliza, Alfred compensa pidiendo permiso para consultar, y no se da un dato falso.
3. **Quitar G2 de los criterios** o sustituirlo por otro dato concreto que no sea «del contexto del bot» (si la hipótesis es cierta, G2 mide otra cosa).

## Despliegue (de Josem), si aprueba

`main` está en `dc0ca28` y es ancestro de `fase-4`. R25b parece seguro: G1, G3 y G4 aciertan, y G2b generaliza. Hash para volver atrás: `dc0ca28`.

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard dc0ca28 && sudo systemctl start sebastian.service`

## Decisiones que necesito

1. ¿Qué opción de «Qué propongo»? Para la 1 hace falta tu OK a la frase en su nueva posición; el gasto cabe en lo autorizado.
2. ¿Se despliega R25b tal cual (G2 sin resolver) o se espera?

---

# Segundo anexo — prueba de posición y cierre

Responde a: `740c6f4` (H1j-revision §2).
Commit en `fase-4`: `ff859f5` (script y pruebas de la tercera vuelta). Suite completa: **1215 pruebas** pasan, sin API en las pruebas.

## Resultado

**La posición nueva no mejora G2 (0/2) y empeora G2b (de acierta a falla). Vuelve R25b a su sitio anterior**, como decías, sin volver a ti. **H1j queda con R25b en `_REGLA_ACCIONES_CON_HISTORIAL`, tal como estaba en `baaf6c8`, y G2 como límite conocido de D74.**

## Qué se hizo

1. La frase de consultas, idéntica, se movió a una constante propia `_REGLA_CONSULTAS` al final del system del planner, después de `_REGLA_BUSCAR_NO_TERMINA`. La parte de guardar se quedó donde estaba.
2. Goldens (tercera vuelta, G2 ×2, G2b, G1 y G3: 5 llamadas).
3. Resultado: no mejora, así que se **ha deshecho el cambio de posición** (el código de `core/orchestrator.py` y `tests/test_regla_consultas.py` están otra vez como en `baaf6c8`, sin tocar a mano). Lo que se queda del experimento es el script (`--vuelta 3`, con su resumen y 2 pruebas con cliente falso), como registro y para repetirlo si hiciera falta.

## Tabla (tercera vuelta, [API], Haiku 4.5)

| Caso | Pasada | Qué llamó el planner | Resultado |
|---|---|---|---|
| **G2** «¿Cuál es mi id de Telegram?» | 1 | **ninguna tool**; «Su telegram_id es 700111222, señor.» | **falla** |
| **G2** | 2 | **ninguna tool**; el mismo texto | **falla** |
| **G2b** «¿Cuándo es mi cumpleaños?» | 1 | **ninguna tool**; «Su cumpleaños es el 12 de marzo, señor.» | **falla** (en la posición anterior acertaba) |
| G1 «¿Qué datos tienes de mí en Telegram?» | 1 | `search_memory({"query": "telegram"})` | acierta |
| G3 «¿Qué sabes de Paco?» | 1 | `search_memory({"query": "Paco", "entidad": "Paco"})` | acierta |

**G2: 0/2. G2b, G1 y G3: 2/3.** Salida completa fuera del repo (scratchpad, `f4_h1j_v3.txt`).

## La versión que se queda: R25b en su sitio de siempre

Con la posición anterior, en la segunda vuelta: G2b 1/1, G1 1/1, G3 1/1, G4 1/1 y G2 0/2. Con la nueva: peor en G2b. Una advertencia de honestidad: son 1 y 2 pasadas por caso con Haiku, así que la diferencia en G2b (1/1 contra 0/1) es una señal débil, pero la regla era «si empeora otra cosa, vuelve».

**Acumulado de G2 con R25 y R25b: 0/6** (2 + 2 + 2). El dato concreto «id de Telegram» no responde a ninguna versión de la frase. G2b (un dato concreto distinto) sí acertó una vez con R25b en su posición anterior.

## Gasto

**0,0165 $** (5 llamadas de Haiku 4.5, entre 0,0032 y 0,0035 $). Dentro de lo autorizado por Josem (≤ 0,10 $ para el hito). **H1j acumula 0,0753 $ de 0,10; fase 4 ≈ 0,173 $ de 3 $.** Quedan 0,0247 $ de la autorización.

## Una prueba existente que habría cambiado

`test_el_planner_dice_que_buscar_no_termina_el_turno` (`tests/test_calendar_descripcion.py`) exige que la regla «buscar no termina el turno» sea lo último del system del planner. Con la frase de consultas al final (la posición de la prueba), esa prueba fallaba. **Como el cambio se ha deshecho, no hay esperado que tocar.** Lo dejo apuntado por si algún día se vuelve a probar esa posición.

## Desviaciones

Ninguna. Los ficheros, con Edit/Write; para deshacer la posición usé `git checkout` de las dos rutas a `baaf6c8`.

## Despliegue (de Josem), H1j y H1k juntos

`main` está en `9f64780` (H1i ya desplegado) y es ancestro de `fase-4`, así que el merge es un avance directo. Hash para volver atrás: `9f64780`. **H1k se entrega después, en su propio informe; las órdenes de abajo valen para los dos, una vez que H1k esté aprobado** (el merge trae todo lo que haya en `fase-4`).

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard 9f64780 && sudo systemctl start sebastian.service`

## Decisiones que necesito

Ninguna. Queda aprobado con G2 como límite conocido, según tu regla.
