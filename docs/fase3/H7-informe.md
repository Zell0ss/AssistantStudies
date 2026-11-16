# H7 — informe (fase 3, parche): la nota del planner no se pierde y la madrugada tiene regla

> Responde a: 46f1a67 (H7-encargo). Programador, 2026-11-16. Rama `fase-3`, commits `b19226b` (R17–R19, goldens) y `4d20165`
> (criterio de #80). Sin migración. No he fusionado, reiniciado ni tocado producción. `main` está en `12ec219`, antecesor de
> `fase-3`: el `ff-only` es posible.

## Hecho

- **R17 (D57).** Si el bucle del planner termina **sin ninguna tool ejecutada** y su última respuesta trae texto, ese texto llega a
  `_synthesize` como nota, **después** de `_TURNO_SIN_HERRAMIENTAS` (que no se toca): «[Nota de quien planifica este turno, no es un dato
  ni algo hecho: «…». Si es una pregunta para el usuario o le falta un dato, házsela tú en una frase.]». Tope de 600 caracteres.
  - Con tool ejecutada, el cierre normal del planner no llega. Sin tool y sin texto, el prompt queda igual que antes.
  - `_resume_plan` comparte el camino de síntesis, así que también lo recibe (con prueba).
  - **Log:** una línea aparte, `Planner cerró sin tool y con nota | user=… | planner_nota=1 chars=N`. Nunca el texto (D42; hay prueba
    con captura del logger). No cambié la línea `Turn end`: el arnés de goldens envuelve `_log_turn_end` con tres parámetros y una cuarta
    columna lo habría roto.
- **R18 (D58).** Regla de madrugada en `_REGLA_COMPROMISOS` con los cuatro sentidos del encargo (00:00–05:59 con «esta noche» es de la
  fecha de mañana; la fecha explícita manda; en lo dudoso, la ocurrencia más próxima que no ha pasado, sin preguntar; nunca una fecha y
  hora pasadas). **Añadí un matiz mío:** «solo si ya es de madrugada y esa hora aún no ha llegado, es la de hoy» (a las 00:30, «esta noche
  a la una» es dentro de media hora, no mañana). Y en `_ALFRED_SYSTEM`, la línea de `cuando_texto`: día de la semana, día y mes.
- **R19 (D58).** `CompromisosModule.crear` rechaza, **antes de escribir nada** (sigue siendo todos o ninguno), un compromiso con `cuando`
  anterior a ahora, o sin `cuando` y con `fecha_fin` anterior a hoy: `{"status": "invalid", "indice": i, "message": "compromiso i: ese
  momento ya pasó (lunes 16/11 a las 01:00); ¿querías el martes 17/11 a las 01:00?"}` (la sugerencia, solo con `cuando`). R13
  (`ya_existe`) se comprueba antes y no cambia: un pendiente que ya existe se devuelve aunque su momento haya pasado (con prueba). Borré
  la línea sobrante `existente.update(...)` que marcó la revisión de H4.
- **Pruebas sin API:** 20 nuevas (`tests/test_compromisos_module.py` ×9 de R19, `tests/test_orchestrator.py` ×8 de R17/R18,
  `tests/test_golden_estado.py` ×3 de los goldens y su criterio). Las vi fallar antes del código (9 en rojo; las otras 8 eran guardas de
  no regresión). **900 pasan** en total. Los ocho casos del encargo para R19 están, con el reloj en el lunes 2026-11-16 a las 16:30.
- **Goldens #79 y #80**, con el contenido del encargo, **adaptados al formato del arnés**:
  - **El arnés no fijaba la hora** (usaba `datetime.now()`): lo digo como pedía el encargo. Ahora un golden con `ahora:` la fija solo
    para él (la que ve el planner y la que juzga `compromisos_crear`); el resto sigue con el reloj real. #79 y #80 llevan
    `ahora: 2026-11-16T16:30`.
  - El encargo describe «tools_o_pregunta»: es el modo `crea_con_fecha_o_pregunta` (`tests/golden/criterios.py`, función pura con
    pruebas). El arnés registra la entrada de cada `compromisos_crear` (`creaciones`) y la imprime en el informe de la pasada.

## Resultados [API]

| Paso | Resultado | Coste |
|---|---|---|
| #79 ×3 | **3 de 3**: siempre `compromisos_crear` 2026-11-17 01:00; Alfred dice «martes 17/11» | |
| #80 ×3 | **2 de 3** (ver abajo) | |
| (subtotal paso 1) | | 0,1704 $ |
| #40, #49, #67, #71, #76 una vez | **5 de 5** | |
| #73 una vez | **cae** (ver abajo) | |
| E10 una vez | **cae en el turno 5** (ver abajo) | |
| (subtotal paso 2) | | 0,3416 $ |
| **Total H7** | | **0,5120 $** (tope 0,8 $) |

**Gasto de la fase 3: ≈ 10,53 $ de 11 $.** Autorizado por Josem en mi ventana: «Si» a cada uno de los dos pasos, pedidos por separado
(2026-11-16). El tope de 11 $ me lo dio el arquitecto en el encargo; Josem lo confirmó al dar el «Si».

**#80, ejecución 2 (el fallo de producción, reproducido).** Sin ninguna tool. El planner no escribió una pregunta sino una
**confirmación como si estuviera hecho**: «Anotado, señor. Le aviso mañana martes 17 de noviembre a las 01:00.» Alfred recibió esa nota
(R17), y contestó «no he podido crear el recordatorio en este turno. ¿Lo intento de nuevo?», que es lo honesto (D44: no se creó nada).
**R17 solo arregla el caso en que el planner pregunta; aquí no preguntó.**
Un aviso sobre mi propio criterio: esa ejecución salió **PASS** en la pasada porque yo daba por pregunta cualquier texto con `?`, y esa
frase lleva uno. Lo corregí en `4d20165` (prueba en rojo antes): una frase con «no he podido» no cuenta como pregunta, aunque acabe en
«¿lo intento de nuevo?». Con el criterio corregido, #80 es 2/3. No repetí la pasada: el resultado se juzga con la salida guardada.

**#73 (aceptado en H3, riesgo conocido), esta vez peor:** llamó a `salud` y luego a `notes_create`: **guardó una nota** con el resultado
(«nota #3154») y Alfred dijo «He dejado una nota con el resultado». En H3d solo llamó a `salud` (y Tristras no respondió). En esta
pasada, E10 sí lo hizo bien en su turno 4 (ninguna tool; Alfred: «Los resultados de pruebas no los guardo»).

**E10, turno 5 (cambio de día):** el planner hizo `calendar_search_events` y **cerró sin `calendar_update_event`** (el patrón
«busca y se para» de H3c, R9). Alfred lo contó bien («No lo he modificado todavía… ¿confirma que muevo la endoscopia al viernes 29?»).
La cita queda el 28/01 y los tres pasos intactos; R12 sigue bien (segunda toma, día 0). No es del código de H7: ese turno ejecutó
una tool, así que R17 no interviene.

## Desviaciones

- El arnés no tenía hora fija ni el modo «crea o pregunta»: los añadí como lo más pequeño posible (arriba).
- Matiz en R18 («solo si ya es de madrugada…»).
- No repetí #73 ni E10 (sin «sí» para ello): cada uno costaría ≈ 0,03–0,1 $.

## Decisiones que necesito

1. **#80 y el planner que «confirma» sin llamar a la tool (1 de 3).** Opciones: (a) aceptarlo: Alfred ya dice la verdad y ofrece
   reintentar, y `planner_nota=1` en los logs dirá con qué frecuencia pasa en uso real; (b) una defensa en el bucle: si el planner
   cierra sin tool y el mensaje del usuario es un encargo, **un reintento automático** con un mensaje al planner («no has llamado a
   ninguna tool; hazlo o pregunta»); costaría una llamada de Haiku más en esos turnos y un golden. **Mi recomendación: (a) primero** y
   mirar los logs unos días; (b) solo si se repite.
2. **#73 guardó una nota.** El riesgo estaba aceptado con la regla de uso «Josem no le cuenta resultados médicos a Sebastian». Si quieres
   una guardia en código (p. ej. que `notes_create` y `salud` rechacen texto con un resultado clínico), es una fase 4; no la he hecho.
3. **Despliegue** (de Josem, tras tu revisión; no hay migración y los compromisos y la cita no cambian):

   ```bash
   cd /data/AssistantStudies && git status        # debe estar limpio y en main
   git rev-parse HEAD                              # APUNTA este hash: es la vuelta atrás (hoy 12ec219)
   git merge --ff-only fase-3
   sudo systemctl restart sebastian.service
   bash /data/AssistantStudies/sebastian2/deploy/comprobar_fase3.sh      # debe terminar con «Todo bien.»
   ```

   Vuelta atrás: `sudo systemctl stop sebastian.service; cd /data/AssistantStudies && git reset --hard <el hash apuntado>; sudo systemctl
   start sebastian.service`. Después, por Telegram, con una cita **inventada** (no la 4946): «Recuérdame esta noche a la una de la
   madrugada que me duerma ya» tiene que contestar con **«martes 17/11»** (o el día que toque) y la 01:00, no con la de hoy ya pasada. Y
   «Recuérdame hoy a las 08:00 que X», dicho por la tarde, tiene que **negarse y proponer mañana**.
