# H6 — informe (fase 3, diagnóstico): «Recuérdame … a la una» que cerró sin tool en producción

> Responde a: e79617c (H6-encargo). Programador, 2026-11-16. Rama `fase-3`. **Sin cambios de código ni de prompts**, sin commit de
> código, sin tocar producción. **Diagnóstico incompleto: 4 de las 6 ejecuciones** (faltan las dos con historial; ver «Gasto»).

## Hecho

Un guion temporal de diagnóstico (no commiteado; copia en el scratchpad de mi sesión, no en el repo) que usa el mismo arnés que los goldens
(`escenario_runner`, R10) y, por ejecución, apunta: tools con sus entradas, texto del planner cuando una llamada con tools cierra sin
`tool_use`, y la respuesta de Alfred. Contra `sebastian_test`, usuario B (memoria vacía, agenda limpia), sin Telegram. Fecha de hoy:
lunes 2026-11-16.

## Resultados

| Fila | Frase | Tools (entrada) | Alfred |
|---|---|---|---|
| f1 ×a | «Recuérdame está noche a la una de la madrugada que me duerma ya» | `compromisos_crear` `{texto: «Duerme ya», fecha_inicio: 2026-11-17, hora: 01:00}` | «Anotado. Esta noche a la una le recuerdo…» |
| f1 ×b | ídem | `compromisos_crear` `{texto: «Duerme ya», fecha_inicio: 2026-11-16, hora: 01:00}` | «A la una de la madrugada le aviso, señor.» |
| f2 ×a | «Recuérdame mañana martes 17 de noviembre a la 01:00 que me duerma ya» | `compromisos_crear` `{texto: «Duerme ya», fecha_inicio: 2026-11-17, hora: 01:00}` | «Anotado, señor. Mañana martes a la una…» |
| f2 ×b | ídem | `compromisos_crear` `{texto: «Duérmete ya», fecha_inicio: 2026-11-17, hora: 01:00}` | «Anotado, señor. Mañana a la una…» |
| f2 con historial ×a, ×b | — | **no ejecutadas** | — |

**Resultado: 4 de 4 llaman a `compromisos_crear`. Ninguna reproduce el fallo de producción.**

Dos observaciones:

1. **«Esta noche a la una»** (f1) sale con dos fechas distintas: 17/11 en una ejecución y 16/11 en la otra. Es ambiguo de verdad (a las 16:30
   del lunes, «esta noche a la una» es la 01:00 del martes 17; la 01:00 del 16 ya pasó). La ejecución b crea el aviso para un momento
   pasado, y Alfred dice «a la una le aviso». No es el fallo de H6, pero es un segundo hallazgo (ver «Para decidir»).
2. **Los textos «planner sin tool» que imprime el arnés no son fallos.** El arnés (R10) registra toda llamada con tools que no devuelve
   `tool_use`, y eso incluye el **cierre normal tras la tool** («Hecho. Te recordaré mañana martes 17…»). Las cuatro veces el planner
   llamó primero a la tool y cerró después con ese texto. Ninguna ejecución cerró **sin** tool. (El arnés no distingue las dos cosas;
   se distinguen mirando que `tools` no esté vacío.)

## Gasto

| Paso | Coste |
|---|---|
| f1 ×2 y f2 ×2 sin historial (4 ejecuciones) | **0,1178 $** (Haiku 0,0968, Sonnet 0,0210) |

Autorizado por Josem en mi ventana: «Si» a las seis ejecuciones con tope de 0,10 $ (2026-11-16). Mi estimación (≈0,1 $ las seis) estaba
por debajo: cada ejecución cuesta ≈0,03 $ (≈24 000 tokens de entrada de Haiku). **Me pasé del tope en 0,018 $** con solo cuatro filas, así
que paré antes de las dos con historial (llevan más tokens: el historial va en la entrada). Gasto de la fase 3: **≈ 10,02 $ de 10 $**.
No he lanzado nada más.

## Hipótesis (sin comprobar)

La frase por sí sola no es la causa: 0 fallos en 4 ejecuciones (con n = 4 no excluye una tasa baja). Lo que difiere en producción es el
**historial cargado** (6 intercambios: la colonoscopia, diciembre, el recordatorio con la fecha equivocada, el borrado). Mi hipótesis:

- Con ese historial, el planner lee «mañana martes 17 de noviembre a la 01:00» como una **corrección** del recordatorio anterior mal fechado
  (17/12) o como ambiguo entre 17/11 y 17/12, y **contesta con una pregunta o una confirmación en texto sin llamar a la tool**.
- Lo que Josem vio («no he podido programar ese recordatorio», D44) es el mensaje que sale cuando el planner cierra sin tool, así que es
  coherente con esto; pero no prueba la causa.
- Lo que la confirmaría: las filas «f2 con historial» (historial y cita sembrada del encargo) cerrando sin tool y con un texto del planner
  que pregunta o aclara. Lo que la descartaría: que esas filas también llamen a la tool, y entonces habría que mirar otra cosa (el historial
  real de Josem es más largo y distinto, o la carga de la memoria real).
- Otra posible causa, menos probable: el contenido de la memoria real del usuario en producción (el arnés usa memoria vacía), que no
  puedo reproducir sin datos reales.

## Para decidir (el arquitecto)

1. **¿Las dos filas con historial (≈0,06–0,08 $)?** Es lo único que contrasta la hipótesis. Necesita que Josem suba el tope en mi ventana
   (ya estamos en ≈10,02 $ de 10 $).
2. **«Esta noche a la una»** no tiene regla de madrugada: pasada la medianoche o antes de la 01:00 es de la fecha de hoy y después es de
   mañana, y el prompt no lo dice. Si quieres cubrirlo es una regla nueva (H7), con su golden.
3. Mirar los logs de producción no estaba en el encargo y no lo he hecho. Si Josem quiere, `logcentral query --source sebastian` de
   las 16:30 del 16/11 diría si el planner cerró sin tool o si hubo otro error (sin texto de compromisos: D52).
