# H9 — informe (fase 3, parche): las fechas por el día de la semana y la búsqueda por palabras

> Responde a: 5671de2 (H9-encargo). Programador, 2026-11-19. Rama `fase-3`, commits `b7df750` (R22–R24), `fcfb56a` (goldens #81–#85 y
> arnés), `c49944c` (limpieza de eventos en los goldens de calendario) y `c9b188b` (criterio de palabras completas). Sin migración. No
> he fusionado, reiniciado ni tocado producción; el evento 4947 sigue donde estaba. `main` está en `b735ca6` (la revisión de H8, que ya lo
> contiene): el `ff-only` es posible.

## Hecho

- **R22 (D60).** `_contexto_fecha(ahora=None)` sustituye a `_now_str()` en sus tres usos (`system` del planner y las dos síntesis de
  Alfred). Da `Hoy es jueves 2026-11-19 y son las 08:06.` y `Próximos días: hoy jueves 19/11, mañana viernes 20/11, sábado 21/11, …,
  miércoles 2/12.` (14 días, d/m sin ceros). Los nombres de los días son la tupla `_DIAS_SEMANA`, sin `locale`. El reloj sale de
  `_reloj()` (un solo punto que fijar en pruebas y goldens). `_REGLA_FECHAS` va justo después de `_REGLA_COMPROMISOS` en el `system`.
  `_PLANNER_TOOLS` no lleva la fecha (hay prueba): D59 sigue en pie.
- **R23 (D61).** `CalendarModule.search_events` normaliza (minúsculas, NFD sin diacríticos, troceo por lo que no es letra ni dígito), quita
  las palabras vacías de la lista del encargo y las de menos de 2 caracteres, y busca en dos niveles. Con ninguna palabra útil, queda el
  `LIKE '%…%'` de antes (`search_events("")` devuelve todos).
  - **Filtro en Python**, sobre todos los eventos del usuario (una consulta por usuario, sin `LIKE`).
  - **Forma:** el primer nivel **no lleva clave** nueva; el segundo lleva `coincidencia: "parcial"`. Elegí no marcar el primero para no
    tocar la forma que ya conocen las pruebas y los consumidores.
  - Detalle: si el único evento del primer nivel es un recurrente que ya no tiene próxima ocurrencia, no cuenta y se pasa al segundo nivel.
  - **Log INFO:** `Búsqueda de eventos | user=… | query_chars=22 palabras=3`; el texto no va (prueba con captura de loguru). **Ojo:** la
    línea DEBUG que ya existía en el orquestador (`Tool … | input=…`) sí lleva la consulta; no la toqué (es DEBUG, no INFO).
  - Descripción de `calendar_search_events` con el texto del encargo (también en el `description` del parámetro `query`).
- **R24 (D62).** La línea de Alfred está en `_ALFRED_SYSTEM`, tal cual el sentido del encargo. Nada más en Alfred.
- **`bot/ticket_handler.py:166`: SÍ le afecta, no lo he tocado.** Hace `events = cal.search_events(caption)` y, si hay alguno, asocia los
  códigos **directamente** a `events[0]`, sin mirar `coincidencia`. Antes, una leyenda como «cena con Ana» solo casaba si esa frase estaba
  tal cual en el título; ahora, sin «Cena con Ana», casa por «cena» con la primera cena parcial (la de más palabras y más próxima) y le
  guarda los códigos sin preguntar. Probado con la prueba de «cena con Ana» de R23 (devuelve el evento parcial). Lo arreglaría ignorando
  los `parcial` (y caer en el flujo de preguntar); decide el arquitecto.
- **Arnés (lo mínimo, como `crea_con_fecha`):**
  - Modo nuevo `calendario` en `tests/golden/criterios.py` (`evaluar_calendario`, función pura con pruebas): las tools (`expected` exacta
    o `expected_any`, solo de esa lista), `entrada` (todas las llamadas a `calendar_add_event`), `entrada_update` (a
    `calendar_update_event`), `alfred_menciona` y `alfred_no_menciona`. El arnés registra la entrada de esas dos tools
    (`entradas_calendario`) y la imprime en el informe de la pasada.
  - **`ahora` ahora fija `_reloj`** y no `_now_str` (que ya no existe): la fecha que ve el planner es la del golden, con su día de la semana.
  - **`estado`:** el encargo usa `inicio: "2026-11-27T20:30"`; el sembrador usa `fecha` y `hora`, así que los goldens las llevan.
  - **#85, «no da la de BNP por la de la uni»:** lo juzgo con `alfred_no_menciona: "su cena con los de la uni es"` y
    `"la cena con los de la uni es"` (objetivo, sin leer el texto). Cada frase casa como **palabra completa** (ver abajo).
  - **Limpieza (no estaba en el encargo, hizo falta):** los goldens de `calendario` borran al acabar los eventos que el turno creó (y los
    sembrados), con `ids_de_eventos` y `borrar_eventos_nuevos` en `tests/golden/estado.py`, solo en `sebastian_test`.
- **Pruebas sin API:** 32 nuevas (`test_orchestrator.py` ×9, `test_calendar_module.py` ×14, `test_golden_estado.py` ×9). Vi fallar antes
  del código las de R22–R24 (17 en rojo en la primera pasada) y las de limpieza y de palabras completas; las del criterio `calendario`
  y las de la forma de los goldens las escribí antes del código pero **no las vi en rojo**. **939 pasan** en total (antes 907). Las
  pruebas que ya existían en `test_calendar_module.py` pasan sin tocarlas.

## Resultados [API]

**Paso 1: #81–#85 ×3 (con un fallo mío del arnés).** 0,1795 $ (Haiku 0,0789 + Sonnet 0,1006). Resultado literal: #82 3/3, #85 3/3,
#83 2/3, #81 0/3, #84 0/3. **Los de #84 y #85 no valen:** #81–#83 dejaban su evento en la agenda de pruebas y #84 encontraba dos
«Cena de Navidad BNP» (la nota del planner lo cuenta: «ya está programada para el viernes 20 de noviembre a las 20:30»), así que se
paraba a preguntar. Lo vi en la salida, lo comprobé en la BD (eventos 10375–10377 de `golden_test_user`), los borré a mano de
`sebastian_test` (dejé el «teatro» de la fixture, 10374) y arreglé el arnés (`c49944c`).

**Paso 2: 17 goldens con `calendar_*` o `crea_con_fecha*`, una vez: 17/17** (#7, #8, #9, #40, #50, #64, #65, #68, #69, #70, #72, #74,
#76, #77, #78, **#79 y #80** entre ellos). 0,1904 $ (Haiku 0,0872 + Sonnet 0,1032).
**#81–#85 otra vez, una vez, con el arnés arreglado** (decisión mía, dentro del tope; el paso 2 los incluye por definición): 0,0589 $
(Haiku 0,0280 + Sonnet 0,0308). #82 PASS, #83 PASS, **#84 PASS** (`calendar_search_events` → `calendar_update_event` con
`event_id` 10561 y `new_date: 2026-11-20`; Alfred sin «no se guardó»), **#81 FAIL** y **#85 FAIL** (ver abajo).

| Golden | Fecha escrita (D60) | Tools | Resultado |
|---|---|---|---|
| #81 «Este viernes… 20:30» (jueves 19/11) | **2026-11-20 20:30 en las 4 ejecuciones** | `calendar_add_event` + **`calendar_add_note`** (la dirección) en 4 de 4 | FAIL literal 0/4 |
| #82 «El lunes a las 10» | 2026-11-23 10:00 en las 4 | `calendar_add_event` | 4/4 |
| #83 «El miércoles a las 9» (sábado 21/11) | 2026-11-25 09:00 en las 4 | `calendar_add_event`; en 1 de 4 con `calendar_find_by_datetime` antes | 3/4 |
| #84 mueve la cena | (limpio) 2026-11-20 | `search` → `update` | 1/1 limpio (los 3 primeros, contaminados) |
| #85 «cena con los de la uni» | n/a | `calendar_search_events` | ver abajo |

- **D60 funciona:** las cuatro ejecuciones de #81 escribieron el **20/11**, y #82 y #83 acertaron el lunes 23 y el miércoles 25 las 4 veces.
- **#81 falla por el criterio, no por la fecha.** La frase trae una dirección («calle de las Huertas 41, Madrid») y el planner la guarda con
  `calendar_add_note` después de crear el evento: 4 de 4. El encargo pide la secuencia exacta `[calendar_add_event]`; no he cambiado
  el golden (es normativo). **Decisión que necesito (1).**
- **#85, último resultado: falso positivo mío, corregido sin API.** El planner solo buscó (`calendar_search_events`), y Alfred dijo: «Con
  esa búsqueda solo encuentro una cena de Navidad BNP (pendiente de confirmar) el viernes 20/11 a las 20:30. No sé si es la que busca, o
  si la cena con los de la uni está anotada con otro nombre. ¿Prefiere que busque con otro término?». No da la de BNP por la de la uni, no
  dice que algo no se guardó ni ofrece crear nada. El criterio lo marcó FAIL porque «la cena con los de la uni **es**» casaba dentro de
  «…de la uni **es**tá anotada». Lo arreglé (`c9b188b`, palabras completas, con prueba que usa ese texto): con el criterio corregido
  ese resultado es PASS. Lo juzgué sobre la salida guardada, sin repetir la pasada.
- **Honestidad sobre #84:** la evidencia limpia de R23 es **una** ejecución, no tres. Las tres primeras no demuestran nada en un sentido ni en otro.

**Gasto de H9: 0,4288 $** (tope 0,45 $; Haiku 4.5 0,1941 $, Sonnet 4.6 0,2346 $; embeddings 0): paso 1 0,1795 + paso 2 0,1904 + #81–#85
0,0589. **Gasto de la fase 3: ≈ 11,00 $ de 11,50 $.** Autorizado por Josem el 2026-11-19, en mi ventana: «Si a todo hoy» (los pasos 1 y 2 del
§4). El tope de 11,50 $ es el del encargo.

## Desviaciones

- **Limpieza de eventos en los goldens de calendario** (arriba): no estaba, y sin ella #84 y #85 no se pueden juzgar.
- **El paso 2 sin #81–#85 y luego solo ellos una vez:** para no pasar de 0,45 $ (los 22 de golpe habrían costado ≈ 0,5 $).
- **`estado` con `fecha`/`hora`** en vez de `inicio` (el sembrador no entiende `inicio`).
- **`coincidencia` solo en los parciales** (el encargo dejaba elegir).
- **Un fallo mío de proceso, sin consecuencias:** edité dos ficheros de pruebas con `python3` en Bash en vez de con Edit; el resto, con Edit.
- Los guiones de §4 no existen como tal: se corrió `pytest -m golden -k …`. La salida de las cuatro pasadas está en el scratchpad de
  la sesión (`…/scratchpad/h9_paso1_{1,2,3}.txt`, `h9_paso2.txt`, `h9_paso2b.txt`).

## Decisiones que necesito

1. **#81 y `calendar_add_note`.** El golden pide `[calendar_add_event]` exacto y el planner, con una dirección en la frase, añade
   `calendar_add_note` (4 de 4). La fecha es la buena. Opciones: (a) aceptar `[calendar_add_event]` y `[calendar_add_event,
   calendar_add_note]`; (b) quitar la dirección de la frase del golden. **Mi recomendación: (a)**: guardar la dirección como nota es lo que
   se espera. Mientras tanto #81 queda FAIL en el informe.
2. **`ticket_handler`.** ¿Lo arreglo (ignorar `parcial` y preguntar) en otro hito o lo dejas hasta la fase 4? Sin arreglo, una foto con
   leyenda «cena con Ana» puede guardar sus códigos en otra cena.
3. **Despliegue** (de Josem, tras tu revisión; no hay migración). Ojo: cambia el texto de las descripciones de las tools, así que la caché
   de las tools de D59 se reescribe una vez:

   ```bash
   cd /data/AssistantStudies && git status        # debe estar limpio y en main
   git rev-parse HEAD                              # APUNTA este hash: es la vuelta atrás (hoy b735ca6)
   git merge --ff-only fase-3
   sudo systemctl restart sebastian.service
   bash /data/AssistantStudies/sebastian2/deploy/comprobar_fase3.sh      # debe terminar con «Todo bien.»
   ```

   Vuelta atrás: `sudo systemctl stop sebastian.service; cd /data/AssistantStudies && git reset --hard <el hash apuntado>; sudo systemctl
   start sebastian.service`. Prueba de producción (la que pide el encargo): el evento 4947 sigue el 27/11; Josem lo mueve por Telegram con
   «Mueve la cena de Navidad de BNP al viernes 20…» y tiene que encontrarlo (`search` → `update`) sin decir que «no llegó a guardarse».
