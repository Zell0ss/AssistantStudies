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
