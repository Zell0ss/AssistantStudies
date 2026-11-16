# H7 — encargo (fase 3, parche): la pregunta del planner no se pierde y la madrugada tiene regla

> Responde a: 38ae801 (H6-informe). 2026-11-16, arquitecto. Contexto: `docs/fase3/H6-revision.md` §1–2.
> Josem ha subido el tope de la fase a **11 $**. Este parche no debe pasar de ≈0,8 $.

## 1. Qué arreglamos

1. **El planner cierra sin tool y su texto se pierde.** Es el bucle de `core/orchestrator.py:536`. Pasó dos veces en producción el 16/11. Alfred solo puede decir «no he podido», aunque el planner hubiera escrito una pregunta.
2. **«Esta noche a la una»** salió una vez con la fecha de hoy, 16/11 a la 01:00, que ya había pasado. `compromisos_crear` lo creó sin quejarse.

## 2. Requisitos

### R17 — el texto del planner llega a Alfred (D57)

- Cuando el bucle termina **sin ninguna tool ejecutada** (`tool_results_summary` vacío) y la última respuesta del planner trae un bloque `text` que no está vacío, ese texto llega a `_synthesize`.
- Va en el prompt, después de `_TURNO_SIN_HERRAMIENTAS` y nunca en su lugar, más o menos así: «[Nota de quien planifica este turno, no es un dato ni algo hecho: «…». Si es una pregunta para el usuario o le falta un dato, házsela tú en una frase.]». La redacción la eliges tú; el sentido es este.
- **No va al log.** Por D42, lleva texto del usuario. Lo que sí va al log es que hubo nota y cuántos caracteres tenía, por ejemplo `planner_nota=1 chars=37` en la línea `Turn end` o en una línea aparte. Así la próxima vez sabremos si pasa, sin guardar el contenido.
- Si el turno ejecutó alguna tool, no cambia nada. El cierre normal («Hecho, te recordaré…») sigue sin llegar a Alfred.
- Aplica también en `_resume_plan`, si comparte el camino. Si no lo comparte, dilo en el informe y no lo toques.
- **Pruebas sin API:**
  - Un planner falso que cierra sin tool y con el texto «¿Lo quieres esta noche o mañana por la noche?» → el prompt de Alfred contiene ese texto y `_TURNO_SIN_HERRAMIENTAS`.
  - Uno con tool y texto final → el prompt no contiene el texto.
  - Uno sin tool y sin texto → el prompt queda igual que hoy.
  - El texto no aparece en ningún registro de log (captura de loguru).

### R18 — regla de madrugada en `_REGLA_COMPROMISOS` (D58)

Una o dos frases, con el sentido siguiente:
- Una hora entre las 00:00 y las 05:59 con «esta noche» es de **la fecha de mañana**: la noche que viene.
- Si el usuario da una fecha explícita («martes 17 de noviembre»), **esa fecha manda** sobre «mañana» o «esta noche».
- En otro caso dudoso, **elige la ocurrencia más próxima que aún no ha pasado**. No preguntes: Alfred dirá la fecha entera y el usuario corrige si hace falta. Es la propuesta de Josem, en ADR §5.
- Nunca una fecha y hora que ya ha pasado.

En `_ALFRED_SYSTEM`, una línea: al confirmar un compromiso creado, Alfred dice **día de la semana, día y mes**, usando `cuando_texto` y nunca «mañana a la una» sin más. `describir` ya da «martes 17/11 a las 01:00».

### R19 — `compromisos_crear` no acepta un momento pasado (D58)

- En `CompromisosModule.crear`, con `ahora = self._ahora()`:
  - Se rechaza un compromiso cuyo `momento_efectivo` tenga `cuando` anterior a `ahora`.
  - Se rechaza uno sin `cuando` cuya `fecha_fin` sea anterior a la de hoy.
  - En los dos casos devuelve `{"status": "invalid", "indice": i, "message": "compromiso i: ese momento ya pasó (<describir>); ¿querías el <misma hora, día siguiente>?"}`. La sugerencia solo cuando hay `cuando`.
- Se mantiene «todos o ninguno»: si uno cae, no se crea ninguno, igual que con los demás `invalid`.
- **Ojo con los atados a una cita:** un paso de una cita cuyo rango empezó ayer y acaba mañana (`fecha_fin` futura) **sí** vale. R13 (`ya_existe`) se comprueba antes y no cambia.
- **Pruebas sin API, con `reloj` fijado en el lunes 2026-11-16 a las 16:30:**
  - 16/11 01:00 → `invalid`, y el mensaje sugiere el 17/11 01:00.
  - 17/11 01:00 → `created`.
  - Hoy sin hora → `created`.
  - Un rango 15–17/11 → `created`.
  - Un rango 10–15/11 → `invalid`.
  - Un paso atado a una cita del 18/11 con `dias_inicio -3`, `dias_fin -1` → `created`.
  - El mismo paso con la cita el 16/11 a las 09:00 y `minutos -60` → `invalid`.
  - Un lote de dos con uno pasado → no se crea ninguno.

## 3. Goldens nuevos (cópialos tal cual)

La hora del arnés debe estar fijada en el lunes 2026-11-16 a las 16:30. Si el arnés no la fija ya, dilo antes de gastar.

```yaml
- id: 79
  mensaje: "Recuérdame esta noche a la una de la madrugada que me duerma ya"
  esperado:
    tools: [compromisos_crear]
    entrada: {fecha_inicio: "2026-11-17", hora: "01:00"}
    alfred_menciona: ["17"]
- id: 80
  mensaje: "Recuérdame mañana martes 17 de noviembre a la 01:00 que me duerma ya"
  historia:
    - {user: "¿Qué tengo el mes que viene?", bot: "En diciembre: la endoscopia del jueves 17 a las 9:30 y pilates martes y jueves a las 19:00."}
    - {user: "Recuérdame el 17 a la una de la madrugada que me duerma ya", bot: "Anotado, señor. Le aviso el jueves 17 a la 1:00."}
    - {user: "Borra el recordatorio «Duérmete ya» del 17 de diciembre", bot: "Borrado, señor."}
  estado: {eventos: [{titulo: "Endoscopia", inicio: "2026-12-17T09:30"}]}
  esperado:
    # Pasa si crea el 17/11 a la 01:00, o si no crea nada pero Alfred pregunta (R17).
    # Falla si crea el 17/12, o si Alfred solo dice «no he podido».
    tools_o_pregunta: {tools: [compromisos_crear], entrada: {fecha_inicio: "2026-11-17", hora: "01:00"}}
```

Adapta la forma del YAML a la del arnés: es lo que pide el `#80`. Si el arnés no tiene «tools o pregunta», añádelo de la forma más pequeña que puedas y cuéntalo.

## 4. [API] y gasto (cada paso, con el «sí» de Josem en tu ventana)

| Paso | Veces | Estimación |
|---|---|---|
| #79 y #80 | ×3 cada uno | ≈0,25 $ |
| Los de `compromisos_crear` y `request_clarification` que ya existen (#40, #49, #67, #71, #73, #76 y E10), una vez | ×1 | ≈0,35 $ |

Si te vas a pasar de **0,8 $** en total, para y dilo. Cada ejecución sale a ≈0,03 $, con historial algo más.

## 5. Lo que no se toca

- D56 y las frases de «no se guarda» se quedan para la fase 4.
- `calendar_list_events` con compromisos, también fase 4.
- Producción, los datos de Josem y la cita 4946.

## Para el programador

Responde a: 38ae801 (H6-informe)

**H7:**
1. R17, R18 y R19, con sus pruebas sin API vistas en rojo primero.
2. Goldens #79 y #80 tal cual.
3. Los pasos [API] de §4, cada uno con el «sí» de Josem. El tope de este parche es 0,8 $.
4. **Para** con `docs/fase3/H7-informe.md`: resultados, gasto y los pasos de despliegue, como en H5.
