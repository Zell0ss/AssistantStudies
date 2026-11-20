# H1j — encargo (fase 4, parche D74): con historial, las consultas también pasan por `search_memory`

> Responde a: 563370b (H1i-informe). 2026-11-20, arquitecto. Decisión: **D74** (ADR-MEMORIA §4, tentativa). Josem autoriza **≤ 0,10 $** de API para los goldens (Haiku 4.5).

## 1. Qué enseña la traza (16:43, con H1i desplegado)

Josem preguntó: «¿Qué datos tienes de mí en Telegram?». El historial traía 13 mensajes en los que se hablaba de su id.

- **El planner:** `stop_reason=end_turn`, sin tools. Contestó en texto «Su `telegram_id` es …», sacándolo del historial. Eso va contra D26.
- **Alfred:** recibió `tool_results_summary=""` y contestó bien: «No me ha llegado ningún resultado de memoria… ¿Quiere que lo consulte?».
- **El turno siguiente («Sí»):** el planner llamó a `search_memory({"query": "Telegram"})`, y D73 dio el id y la nota.

Es el mismo fallo de D43, pero en las consultas.

## 2. Requisito (D74)

- **R25 — ampliar `_REGLA_ACCIONES_CON_HISTORIAL`** (`core/orchestrator.py:154`) con una frase sobre las consultas, en la misma regla y en el mismo sitio, al final del prompt. Más o menos:

  > «Si el usuario pregunta qué consta de él, de su gente, de sus cosas o de sus proyectos («¿qué sabes de…?», «¿qué datos tienes de…?», «¿cuál es mi…?»), tu respuesta de este turno tiene que ser una llamada a `search_memory`, aunque el historial parezca tener el dato: lo que se dijo en otro turno no es fuente (D26).»

  - Actualiza el comentario de D43 para citar también D74.
  - No toques lo que dice ya la regla sobre guardar.
- **Una prueba sin API:** la frase está en el system del planner, al final, después de la regla de acciones.

## 3. Goldens ([API], ≤ 0,10 $; datos inventados)

Planner real, con el prompt y las tools de producción, y un índice inventado: `- yo (tú): telegram_id, nota`.

Para G1–G3, un historial inventado de unos 6 intercambios en el que el asistente ya ha dicho el valor, por ejemplo «Su telegram_id es 700111222».

1. **G1:** «¿Qué datos tienes de mí en Telegram?». Tiene que llamar a `search_memory`.
2. **G2:** «¿Cuál es mi id de Telegram?». Tiene que llamar a `search_memory`.
3. **G3:** «¿Qué sabes de Paco?», con Paco en el índice y su alergia ya dicha en el historial. Tiene que llamar a `search_memory`.
4. **Control G4:** «Recuerda que mi color favorito es el verde». Tiene que seguir llamando a `mark_as_memorable`, como pide D43.
5. **Control G5:** «¿Qué tiempo hace en Madrid?». **No** tiene que llamar a `search_memory`.

**Cuántas veces:**
- 2 pasadas de G1–G3 y 1 de G4 y G5: 8 llamadas en total;
- **criterio:** 6/6 en G1–G3 y 2/2 en los controles;
- si el gasto llega a 0,10 $, para y dilo.

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No.
- **¿Llama a una API externa?** Sí: Haiku 4.5, 8 llamadas, ≤ 0,10 $ (autorizado por Josem: «A por él»). Precio según la skill `claude-api`: 1 $ / 5 $ por MTok.
- **¿Toca producción?** Solo al desplegar, con merge y reinicio, que hace Josem.

## Para el programador

Responde a: 563370b (H1i-informe)

1. Haz R25 y su prueba sin API. Pasa la suite.
2. Lanza los goldens del §3, dentro del tope.
3. Escribe `docs/fase4/H1j-informe.md`, corto, con:
   - el resultado de cada pasada;
   - el gasto real;
   - las órdenes de despliegue.
4. Para.
