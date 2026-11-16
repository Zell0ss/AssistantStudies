# H3 — informe (fase 3): planner, goldens y escenario E10

> Responde a: 30b9f34 (H2-revision, «Para el programador»). Programador, 2026-11-16. Rama `fase-3`, commits
> `5b9ab9a`, `977beda`, `8b8d412`, `3b267da`, `ee230f5` y `1604f0e` (más tres de `TOMORROW.md`).
> **H3 no cumple su criterio:** los goldens nuevos están en 5/10, la pasada completa en 68/76 (cae un golden
> antiguo, #62) y E10 en 1/3. Paro aquí, como pide la revisión, con las causas y lo que propongo.

## Hecho

- **Docstring** de `armar_resumen` (R1 de tu nota de la H2-revision): `conn=None` usa el singleton y lo cierra.
- **Comprobación de modelos** (skill `claude-api`, tabla en caché de 2026-11-03, sin llamada en vivo): `claude-haiku-4-5-20251001`
  (1 $ / 5 $) y `claude-sonnet-4-6` (3 $ / 15 $) siguen activos, con los mismos precios.
- **Goldens #67–#76** copiados al `goldens.yaml` (76 en total) con **datos inventados** (ver desviación 1).
- **Retoques de descripciones y del planner** (desviaciones 2 a 4), para que «lo que hay que hacer» vaya a `compromisos_crear`,
  el lugar y el acompañante a la nota del evento y un resultado médico a ninguna parte.
- **E10** en `tests/golden/test_escenarios_compromisos.py`: los 5 turnos del plan con datos inventados; el criterio es la BD
  (un solo evento, movido al 29 a las 9:30; compromisos pendientes **todos con `evento_id`** del mismo evento; lugar y
  acompañante en la nota; nada del resultado en memoria, compromisos ni nota) y el texto de `armar_resumen` el día −3 de la
  fecha nueva (trae la dieta) y de la vieja (no la trae).
- `pytest -m "not golden"`: **767 pasan**, sin cambios respecto a H2.

## Resultados [API]

| Paso | Resultado | Coste |
|---|---|---|
| Línea base #67–#76 | 3/10 (pasan 70, 72, 75) | 0,31 $ |
| Diagnóstico #67, 68, 69, 73, 74, 76 | 1/6 | 0,20 $ |
| Tras retocar descripciones (`3b267da`) | 3/10 (70, 73, 75) | 0,29 $ |
| Tras la regla del planner (`ee230f5`) | **5/10** (69, 70, 73, 74, 75) | 0,28 $ |
| Pasada completa #1–#76 | **68/76** | 2,04 $ |
| #62 ×3 | **0/3** | 0,08 $ |
| E10 ×3 | **1/3** | 0,51 $ |

**Fallan en la pasada completa:** #62 (antiguo), #67, #68, #71, #72, #76, y #73 y #74 (que habían pasado en la prueba anterior).

### Los goldens nuevos que fallan (los goldens son tuyos; no los toco)

- **#67** («El lunes empiezo la dieta blanda, tres días»): hoy, 2026-11-16, es lunes y el modelo pregunta qué lunes. Depende del día
  en que se lance; el runner usa la fecha real, sin reloj fijado.
- **#68, #71, #72** (y a veces #69): su `historia` es solo texto y la BD de test no tiene el evento ni los compromisos que esa
  historia da por hechos. El modelo busca el evento, lo crea o lo pregunta, y la secuencia no es la aceptada.
- **#74:** hace `calendar_search_events` y dos `compromisos_crear` seguidos; la lista aceptada no lo prevé.
- **#76:** pregunta en texto en vez de llamar a `request_clarification`.
- **#73** («el test… me salió positivo»): pasó tras el primer retoque y volvió a `salud` en la pasada completa. Es intermitente.

### #62 («Olvida lo de las camisetas UV») no es el intermitente de la fase 2

Hace `search_memory` (la memoria base de los goldens no tiene las camisetas) y contesta «no me consta nada, no hay nada que
retirar»: **0 de 3** repeticiones, con el mismo texto. En la fase 2 pasaba 3 de 3 al repetirlo. Lo más probable es que lo cause
mi retoque (la descripción de `mark_as_memorable` o `_REGLA_COMPROMISOS`); no lo he aislado, porque eso cuesta API.

### E10: 1 de 3

- **Ejecución 1 (pasa):** pero el turno 3 (lugar y acompañante) se quedó en una pregunta sobre el año y la nota solo se escribió
  al mover la cita en el turno 5. Pasa por la BD final, no por un camino limpio.
- **Ejecución 2:** en el turno 2 llamó a `calendar_add_event` en vez de buscar → **dos eventos** «Endoscopia»; los compromisos
  quedaron atados al duplicado y la nota al original.
- **Ejecución 3:** al mover la cita, `calendar_update_event` no encontró nada y creó **un evento nuevo en 2026** (año pasado) con
  los cinco compromisos repetidos, mientras el original seguía el 28/01/2027.
- **En las tres,** el turno del resultado no llamó a ninguna tool (D52 se cumple), pero **en dos Alfred ofreció apuntarlo**
  («¿Desea que lo apunte en memoria o como nota?»).
- **Calidad del troceado:** «tres días antes y la mantengo hasta la víspera» salió como dos o tres compromisos solapados
  («Empezar dieta blanda» desde −3 y «Mantener dieta blanda» de −3 a −1), y el resumen del día −3 los lista los dos.

## Gasto

**Autorizado por Josem el 2026-11-16: hasta 4 $ en la ventana del arquitecto (PLAN) y, en mi ventana, un «Si» a cada paso [API];
tras la pasada completa subió el tope en 2 $ más («Si, otros 2 $», mi ventana), es decir, 6 $ en total** (el arquitecto no lo ha visto).

**Gastado en la fase 3: ≈ 3,71 $** (quedan ≈ 2,29 $ del tope de 6 $). Por modelo, de lo que guardé:
Haiku ≈ 2,76 $, Sonnet ≈ 0,64 $, embeddings OpenAI ≈ 0 $ (la primera línea base, 0,31 $, no la guardé por modelo).
La pasada completa costó 2,04 $ (Haiku 1,657, Sonnet 0,386): más que los 1,5 $ del plan, porque el prompt del planner ya lleva
las cuatro tools nuevas.

## Desviaciones

1. **Datos de prueba inventados** (Josem lo confirmó, 2026-11-16: «Y si a lo de inventar datos equivalentes para las pruebas.
   Nombres, hospitales, pruebas, etc»). En los goldens #67–#76, mis tests de fase 3 y el ejemplo de `compromisos_tools.py`:
   colonoscopia → endoscopia, «dieta sin residuos» → «dieta blanda», «sangre oculta» → «test de la gota seca», aspirina → látex,
   hierro → zinc, Rebeca → Marta, hospital real → «Hospital Ejemplo». La cita de los goldens es «jueves 28 de enero a las 9:30»
   y se mueve «al 29». Los tests unitarios conservan las fechas del plan (17/12/2026). **No he tocado** #64–#66, `migrar_sprint3`,
   `test_orchestrator`, `test_cuaderno_despertar` ni `deploy/PASOS-CON-SUDO.md` (ahí van datos reales de la migración de la alergia).
2. **`mark_as_memorable`** (`3b267da`): la descripción excluye lo que el usuario tiene que hacer con día u hora (→ `compromisos_crear`),
   el lugar o acompañante de una cita (→ nota del evento) y los resultados o diagnósticos (D52).
3. **`salud`** (`3b267da`): añade «ni resultados de pruebas médicas (D52)». Quedó en 494 caracteres: `test_la_descripcion_es_corta`
   (fase 1) pone el tope en 500.
4. **Regla nueva en el prompt del planner** (`ee230f5`, `_REGLA_COMPROMISOS` en `core/orchestrator.py`): lo que hay que hacer con un día,
   hora o condición es compromiso (o `request_clarification`), y un resultado médico no va a ninguna tool. Pasó los goldens
   de 3/10 a 5/10, y es el cambio con más riesgo para los antiguos (probablemente toca #62).
5. **`E10` en un fichero propio** (`test_escenarios_compromisos.py`) y no en `test_escenarios_memoria.py`; reutiliza sus ayudas y
   se imprime con los demás escenarios. Usa los 5 turnos del plan (cita, preparación, lugar, resultado, cambio de día) y comprueba
   el resumen con relojes fijados; el planner sigue viendo la fecha real de hoy.

## Decisiones que necesito

1. **#62 (antiguo, falla 3/3):** propongo aislar cuál de los dos retoques lo causa (≈ 0,1 $ por prueba) y reformularlo sin romper
   #67–#76. Necesito el «sí» de Josem al gasto y, si prefieres otra salida (p. ej. aceptar `search_memory` antes de `mark_as_memorable`
   en #62), tu criterio.
2. **Goldens #67, #68, #71, #72, #74, #76** (tuyos): ¿los cambio yo o prefieres hacerlo tú? Propuesta: **#67** con fecha explícita
   («el lunes 14 de diciembre…») para que no dependa del día; **#68, #71, #72** o bien sembrar el evento y los compromisos en la BD
   antes (el harness necesita una función nueva) o bien aceptar las secuencias que empiezan por `calendar_search_events` o
   `request_clarification`; **#74** aceptar dos `compromisos_crear`; **#76** aceptar la pregunta en texto o reescribir la frase.
3. **E10 1/3: ¿qué arreglo?** Propongo dos retoques de descripción, sin reglas nuevas en el planner: que `calendar_add_event` diga que
   se busque antes si la cita ya existe, y que `calendar_update_event` y `calendar_add_event` digan qué año tomar cuando el usuario
   da solo el día («al 29»: el de la cita existente). Y en `compromisos_crear`: «un intervalo es un solo compromiso con
   `dias_inicio` y `dias_fin`». Después, para no gastar otra pasada entera: #56–#76 (memoria y compromisos, ≈ 0,6 $) y E10 ×3
   (≈ 0,5 $), y la pasada completa **una sola vez al final** si todo lo anterior pasa (≈ 2 $). Las tres cosas juntas (≈ 3,1 $)
   **superan lo que queda (2,29 $)**; sin la pasada final entran.
4. **Alfred ofrece guardar un resultado médico** (E10, ejecuciones 2 y 3): D52 se cumple en la BD, pero la síntesis lo sugiere. ¿Una línea
   en `_ALFRED_SYSTEM` («no ofrezcas guardar resultados ni diagnósticos»)? Es tu prompt.
5. **El tope:** gastado 3,71 $ de 6 $, y el arquitecto no ha confirmado la subida de 4 a 6 $. Con los retoques de arriba la
   pasada completa final no cabe: **¿la hace Josem con otro tope, o la damos por cubierta con #56–#76 + E10?** Si no se llega a
   3/3 en E10, **¿paro y lo dejas como riesgo para H4**, o se sube el tope otra vez?

## Para la revisión

- **No recomiendo desplegar H4 con este estado:** #62 es una regresión de un golden antiguo y E10 duplica eventos en 2 de 3.
  La prueba real (Josem dictando por Telegram) llegaría a esos mismos fallos. H4 sigue siendo de Josem, con fecha límite el 10/12.
- Nada que toque producción. Todos los pasos [API] corrieron contra `sebastian_test` y sus colecciones, sin Telegram real.
- Salidas completas de cada ejecución en el scratchpad de mi sesión (`diag1.txt`, `base2.txt`, `base3.txt`, `pasada1.txt`, `g62_*.txt`,
  `e10_*.txt`), por si quieres ver los turnos.

---

# Anexo H3b — segunda vuelta

> Responde a: 4ba8413 (H3-revision, «Para el programador»). Programador, 2026-11-16. Commits `f7e910c` (R2–R5 y espacios de
> `salud`), `761bd57` (harness `estado:`, goldens de §4, E10) y `7deb3bb` (R6). **Paro sin pasada completa y con E10 en 0/3**, como
> pedías: no hay tercera vuelta sin pasar por ti.

## Hecho

- **R2:** `calendar_update_event` admite `event_id` (prioritario, solo del propio usuario) y su `not_found` dice «pregunta al usuario,
  no lo crees de nuevo». `title` ya no es obligatorio. Pruebas: `test_update_event_por_id`, `…_sin_titulo`,
  `…_de_otro_usuario_no_toca_nada`, `test_update_not_found_dice_que_no_lo_cree_de_nuevo`, y `test_evento_movido_por_id_mueve_compromisos`
  (D50, con id).
- **R3:** `calendar_add_event` devuelve `status: 'exists'` con `event_id` y `time` si hay un evento del usuario ese día con ese título
  (sin mayúsculas). Pruebas: mismo día y título, otro día u otro título (inserta), otro usuario (inserta) y todo el día.
- **R4:** «Busca antes si la cita ya existe» y el año en `calendar_add_event`; el año en `new_date` de `calendar_update_event`; «un
  intervalo es **un solo compromiso**» en `compromisos_crear`. **R5:** tu línea en `_ALFRED_SYSTEM`, con «Resultados médicos (D52).» delante.
  Los dos espacios de `salud`, arreglados. Una prueba por cada texto.
- **Goldens de §4 tal cual:** #67 (fecha explícita), #68, #69, #71, #72 y #74 con `estado:`, y `[]` en #76. **#72** ya traía
  `[calendar_search_events, calendar_update_event]`: solo he añadido el estado. #62 y las listas de #74 no cambian
  (`test_el_golden_62_sigue_exacto_y_el_74_no_cambia_sus_listas`).
- **Harness `estado:`** (`tests/golden/estado.py`, `test_estado_se_siembra_y_se_limpia` y otras 11 en `tests/test_golden_estado.py`).
  **Desviación:** limpia **solo lo que sembró** (por id), no toda la agenda del usuario de goldens: ese usuario comparte agenda con
  la fixture de sesión `golden_fixtures` (el «teatro» y su entrada), y una limpieza total habría roto goldens antiguos. Por lo mismo,
  **E10 va con el usuario B** (`USUARIO_B`), cuya agenda sí se vacía entera.
- **E10** anota si el `calendar_update_event` del turno 5 lleva `event_id`, sin que falle por eso.
- **`pytest -m "not golden"`: 799 pasan** (767 en H3 → +32). Sin fallos.

## Resultados [API] y gasto

| Paso | Resultado | Coste |
|---|---|---|
| #62 ×3 con R2–R5 | **0/3** (`search_memory`) | 0,083 $ |
| #62 ×3 sin «ante uno, no la llames» en `mark_as_memorable` (tu 1.ª sospecha) | 0/3 | 0,083 $ |
| #62 ×3 más «pedir que se olvide algo sigue siendo `mark_as_memorable`» en la regla (tu 2.ª) | 0/3 | 0,083 $ |
| #62 ×3 en el worktree de la fase 2 (código aprobado) | **3/3** → es regresión de la fase 3 | 0,077 $ |
| Aislar, una ejecución cada una: A (`mark_as_memorable` de la fase 2) · B (sin `_REGLA_COMPROMISOS`) · C (A+B) · D (sin tools de compromisos) · E (A+B+D) | A, B, C, D fallan; **E pasa** | 0,122 $ |
| **R6:** #62 ×3 con la descripción nueva de `compromisos_borrar` | **3/3** | 0,092 $ |
| #7, #8, #9, #40, #50 y #56–#76 | **21/26** | 0,785 $ (Haiku 0,649, Sonnet 0,136) |
| E10 ×3 | **0/3** | 0,462 $ |

**Gasto de H3b: ≈ 1,79 $. Acumulado de la fase 3: ≈ 5,50 $ de 6 $** (autorizado por Josem: 4 $ en la ventana del arquitecto el
2026-11-16, y «Si, otros 2 $» en mi ventana el mismo día; cada paso, con su «Si» en mi ventana. Quedan ≈ 0,50 $). Los retoques de las
dos sospechas y las variantes A–E eran temporales: **no están commiteados** y el árbol quedó limpio.

### R6 (#62): la causa era `compromisos_borrar`

Quitar la descripción de `mark_as_memorable` (A) o la regla (B) no bastaba, y quitar las tools sin más (D) tampoco, porque la regla y la
descripción nombran tools que entonces no existen. **Solo revertirlo todo (E) lo arregló.** Las tools de compromisos, con las otras dos
piezas o sin ellas, bastan para romper #62. La pista estaba en `compromisos_borrar`: decía «cuando el usuario dice **'olvida** ese
compromiso' o 'borra eso'», y «olvida lo de las camisetas UV» competía con él. Ahora dice qué **es** un compromiso (algo que se hace con
día u hora) y que un dato se retira con `mark_as_memorable`; test `test_descripcion_de_borrar_manda_los_datos_a_mark_as_memorable`.
**Ni tu frase en `mark_as_memorable` ni la regla eran la causa.** `_REGLA_COMPROMISOS` se queda, porque ayuda a los goldens nuevos.

### Los 21/26: lo que falla

- **Antiguos que caen: #40 y #50** (ninguno es de los intermitentes conocidos: #62, #43, #28). No los he aislado (no hay presupuesto).
  - **#40** («recuérdame comer a las 2»): `request_clarification` («¿qué día?»), que no está en sus listas. Puede ser la R16 de la fase 2
    (el planner pregunta si falta el día) y no H3b; **#28** se amplió con esa respuesta y #40 no.
  - **#50** («¿y mañana?» tras «¿Qué tengo hoy?»): el planner **no llama a ninguna tool** y Alfred dice «no he podido crear el aviso».
    Es el mismo modo de fallo que #67 y que la variante C.
- **Nuevos de §4 que caen:** **#67** (sin tool, mismo modo), **#74** (`calendar_search_events` y **dos** `compromisos_crear`: el fallo
  real que decías que no cambia) y **#76** (solo `calendar_search_events`, y Alfred pregunta en texto cuándo es la cita).
- **Pasan:** #7, #8, #9, #56–#66 (con #62 incluido), #68, #69, #70, #71, #72, #73 y #75. **De los diez nuevos (#67–#76), 7.**

## E10: 0 de 3

Lo que **sí** se cumple en las tres: **un solo evento** (R3 funciona), **todos los compromisos con `evento_id`** del mismo evento (D50),
y **nada del resultado médico** en memoria, compromisos ni nota (D52).

Lo que falla:

- **Turno 3 (lugar y acompañante), 3/3:** el planner hace `calendar_search_events` y **termina el turno** (`iterations=2`) sin llamar a
  `calendar_add_note`. Alfred dice «actualizo la cita con los datos…» y no ha escrito nada. Dos ejecuciones fallan por eso (la nota
  queda vacía); la tercera la ve en el criterio 3.
- **Turno 5 (mover al 29):** en dos ejecuciones hace solo `calendar_search_events` (o nada) y **no mueve la cita**; Alfred dice «muevo la
  endoscopia…». En la tercera sí mueve, pero **`calendar_update_event` va SIN `event_id`**: R2 no se ejerció (cae al título, que acertó).
- **Troceado del intervalo:** 2 de 3 siguen con «Empezar» + «Mantener dieta blanda»; en la tercera, un solo compromiso con `dias -3..-1`.

**La causa que veo no es el título ni los duplicados, sino que el planner da por hecho el paso siguiente tras una búsqueda.** Con R3,
los duplicados desaparecen, pero queda **«busca, y se para»**, y la síntesis cuenta como hecho lo que no se hizo. Eso es la clase de fallo
de D26/D44 (afirmar una acción sin resultado de tool) en un camino nuevo: D44 solo vigila turnos **sin ninguna** tool, y aquí sí hubo una
(la búsqueda).

## Decisiones que necesito

1. **E10 0/3: ¿qué cambio de diseño?** Las descripciones solas no lo han arreglado dos veces. Opciones, de menos a más código:
   - **(a)** `calendar_add_note` acepta título y día como `calendar_update_event` (y `event_id` sigue valiendo), para que no dependa de
     encadenar dos llamadas;
   - **(b)** extender D44: si el turno solo ejecutó tools de lectura y el usuario pedía una acción, a Alfred se le dice que **no se hizo**;
   - **(c)** que el bucle del planner no cierre el turno tras una búsqueda cuando el mensaje pedía escribir (cambio en `orchestrator.py`).
   Recomiendo **(b)**, que protege la promesa de honestidad en cualquier camino, y **(a)**, que acorta la cadena que más falla. No hago
   nada sin tu criterio.
2. **#40 y #50 (antiguos):** ¿los aislamos antes de nada? No hay presupuesto para eso y para E10: con ≈ 0,50 $, solo cabe una de las dos cosas.
3. **#67, #74, #76:** ¿aceptas `[calendar_search_events]` solo en #76 (preguntar tras buscar vale), y qué hacemos con el modo «el planner
   no llama a ninguna tool» (#67, #50, variante C)? Aparece solo en esta fase, así que puede ser sensibilidad del planner al tamaño del prompt
   de tools, que ya es de 11 familias.
4. **Gasto y pasada completa:** ≈ 5,50 $ de 6 $. La pasada completa (≈ 2 $) **no se ha lanzado**; con los fallos de arriba, correrla ahora
   solo confirmaría lo ya visto. **Decide Josem** el tope, **después de tu revisión**.
5. **Lección para el ADR** (la apunto, es tuya): una familia nueva de tools puede capturar los verbos de otra («olvida», en #62).
   Cada descripción de una familia nueva debería decir **qué cosas no son suyas**, no solo qué hace. Lo decía el plan, y aquí costó 0,6 $ verlo.

## Para la revisión

- **Producción:** nada que la toque. Todos los [API] corrieron contra `sebastian_test`; ninguno mandó nada a Telegram.
- **No recomiendo desplegar H4 con este estado.** Hay dos goldens antiguos en rojo (#40, #50, sin aislar) y E10 en 0/3 con el fallo
  «busca, y se para». La prueba real (Josem dictando por Telegram) caería en el turno 3, el del lugar y el acompañante.

---

# Anexo H3c — tercera vuelta

> Responde a: c3fa487 (H3-revision, «Segunda revisión», «Para el programador»). Programador, 2026-11-16. Commits `23f21d0`
> (R7–R9, R10 en el harness y goldens de §9) y `fd0851d` (la línea de R10). **E10 pasa 3 de 3 por su criterio; la tanda no está verde
> (#67 y #71) y no he lanzado la pasada completa.** Paro con las salidas, como pedías.

## Hecho (sin API; 833 pruebas)

- **R7 (D54):** `_TOOLS_DE_LECTURA` y `_TOOLS_DE_ESCRITURA` en `core/orchestrator.py` y la nota «[En este turno solo has consultado (…): no has
  guardado, cambiado, borrado, apuntado ni creado nada…]» en `_synthesize`, después del mensaje y de los datos. Con una búsqueda sola, está; con
  una búsqueda y una escritura, no; sin ninguna tool, sigue la de D44. `test_toda_tool_esta_clasificada_lectura_o_escritura` obliga a clasificar
  toda tool nueva. **Una decisión mía:** `request_clarification` va con las de lectura (no cambia nada, y el orquestador la intercepta).
- **R8:** `calendar_add_note` admite `title` y `date` (`event_id` opcional y prioritario); con varios eventos devuelve `ambiguous` con los
  candidatos y no escribe; con `not_found`, el mismo texto que R2; devuelve el `event_id`. Pruebas: por id, por título y día, sin día, ambiguo,
  `not_found`, de otro usuario y «el id manda». El esquema de la tool y su descripción, actualizados (la nota sigue sin aceptar resultados, D52).
- **R9:** `_REGLA_BUSCAR_NO_TERMINA`, al final del prompt del planner, con tu frase.
- **R10, código:** el texto que el planner dice cuando cierra una llamada sin `tool_use` sale en el informe del test («Planner sin tool»), nunca
  en el log (D42). **Aviso para leerlo:** también sale el cierre normal de cualquier turno que sí usó tools (la última iteración no lleva tool).
- **Goldens de §9 tal cual:** #40 (`[calendar_add_event]`, `[]`, `[compromisos_crear]`, `[request_clarification]`) y #76 (`[calendar_search_events]`).

## Resultados [API] y gasto

| Paso | Resultado | Coste |
|---|---|---|
| R10: #50 y #67 ×3 | #50 **3/3**; #67 **1/3** | 0,148 $ |
| Tanda #40, #50, #56–#76 | **21/23** (caen #67 y #71) | 0,701 $ (Haiku 0,581, Sonnet 0,120) |
| E10 ×3 | **3/3** | 0,531 $ |
| Pasada completa #1–#76 | **no lanzada** | — |

**Gasto de H3c: ≈ 1,38 $. Acumulado de la fase 3: ≈ 6,88 $ de 8 $** (autorizado por Josem: 4 $ en la ventana del arquitecto el 2026-11-16; en
mi ventana, «Si, otros 2 $» y «Subo 2 más y doy si», con un «Si» por cada paso). Quedan ≈ 1,12 $.

## La tanda: lo que falla

- **#50 pasa 3/3** y **#40 pasa**: eran los antiguos en rojo del anexo anterior. #50 era intermitente.
- **#62 pasa** (R6 se mantiene) y todo #56–#76 salvo dos:
  - **#67** («El lunes 14 de diciembre empiezo la dieta blanda, tres días»): **1 de 3 en R10 y 0 de 1 en la tanda**, también con la línea que
    añadí a `compromisos_crear` («el día de inicio cuenta; no preguntes cuál es el último», `fd0851d`). **La causa es clara, pero una línea no la
    arregla:** el planner **no llama a nada y contesta en texto** con preguntas («¿a qué hora empiezas la dieta?», «¿dura tres días o cuatro,
    incluido el 17?»); otras veces usa `request_clarification` con la misma pregunta. Cuando es en texto, el turno acaba en `[]` y Alfred
    (D44) dice «no he podido registrar nada». Es el modo «sin tool» de #50 y de la variante C, ahora con texto: **el planner pregunta cosas que no
    hacen falta**. Según tu criterio, no sigo con prompts: traigo las salidas.
  - **#71** («Ya he hecho la primera toma»): `compromisos_listar → compromisos_completar → compromisos_listar`. Marca bien el compromiso y vuelve a
    leer al final; esa secuencia no está en sus listas. Pasaba en la tanda anterior: es variación, no una regresión de H3c.

## E10: 3 de 3 por el criterio, con cuatro matices

El criterio (BD y resumen) se cumple las tres veces: **un solo evento** movido al 29 a las 9:30, **todos los compromisos con `evento_id`**, la
nota con el lugar y el acompañante, **nada del resultado médico** en ninguna parte (D52), y el resumen del día −3 trae la dieta (el del día −3 de
la fecha vieja, no). Lo que el criterio no ve:

1. **`event_id` en el turno 5:** **2 de 3 CON** (R2 se ejerce); en la primera ejecución, **SIN** (cae al título, que acertó).
2. **«Busca y se para» en el turno 3 (lugar y acompañante): 2 de 3.** R8 y R9 no lo eliminan: el planner hace `calendar_search_events` y cierra, aunque
   `calendar_add_note` ya acepta título y día. **D54 hace su trabajo:** en la ejecución 2 Alfred dice «en este turno solo he consultado el calendario:
   no he añadido a Marta ni la ubicación» (antes decía «actualizo la cita…»); en la 3 dice «dos cosas que añadir», sin afirmar que lo hizo. La nota
   se escribió **después**, en el turno 5, cuando el planner añadió `calendar_add_note` al mover la cita. Por eso el criterio pasa, pero **por un
   camino que no es el limpio**.
3. **La segunda toma sale un día antes en 2 de 3.** «…y el mismo día a la una de la madrugada la segunda»: en las ejecuciones 1 y 2 quedó con
   `dias_inicio = -1` y `hora = 01:00` (la madrugada del día **anterior** al de la cita), y solo en la 3, con `dias_inicio = 0`. **E10 no lo comprueba.**
   Si el caso real saliera así, el aviso de la 01:00 del 17/12 (el indicador de D48) llegaría 24 horas antes. Puede ser también que la frase de E10
   sea ambigua; no lo he cambiado: es tu criterio.
4. **Troceado:** una ejecución sigue partiendo la dieta en dos compromisos solapados (los de «Empezar» y «Mantener», `-3..` y `-3..-1`); las otras
   dos, uno solo con `-3..-1`.

## Decisiones que necesito

1. **#67:** ¿aceptas `[]` y `[request_clarification]`, o lo dejamos como riesgo conocido? Mi recomendación: aceptarlos. Preguntar de más es molesto
   pero inofensivo, y D44/D54 impiden que Alfred diga que lo hizo. Arreglarlo del todo exigiría código (hacer algo con el texto del planner cuando
   cierra sin tool), y lo descartaste. Si prefieres arreglarlo, es otra vuelta, que ya dijiste que no.
2. **#71:** ¿aceptas `[compromisos_listar, compromisos_completar, compromisos_listar]`? Leer otra vez al final no cambia nada.
3. **La segunda toma (matiz 3):** ¿añado a E10 una comprobación de que `Segunda toma` lleva `dias_inicio = 0` y `01:00`? **Hoy fallaría 2 de 3**,
   y sería la prueba más cercana al caso real. No la añado sin tu decisión (es tu criterio), pero **lo propongo antes de H4**, no después.
4. **La pasada completa:** no se lanza, porque la tanda no está verde. ≈ 2,1 $ con ≈ 1,12 $ de margen: **decide Josem el tope, tras tu revisión de
   las decisiones 1 y 2.**
5. **H4:** E10 3/3 cumple el criterio de cierre, pero la tanda y la pasada no. **No recomiendo desplegar hasta tener la pasada completa**, que es lo que
   cazó #62. H4 es de Josem y vence el 10/12.
