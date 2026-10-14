# H0 (fase 2) — Revisión del arquitecto

Responde a: 5c3b69b (H0-informe)

**Veredicto: aprobado con retoques.**
- **SDK y Python (§6): aprobado.**
- **D28: todavía no se adopta.** Hay una pasada más, con esfuerzo `medium` y el mismo criterio
  (Josem, 2026-10-14, opción B).

## 1. Comprobado

- **SDK y Python** (`126fd2f`, `46ea349`):
  - el inventario de la guía está completo y no hay nada que cambiar en el código;
  - `requirements.txt` solo cambia en la línea de `anthropic`;
  - 417 tests en verde en los dos entornos;
  - la comprobación con `-k` da los mismos resultados que con 0.79;
  - los pasos de despliegue tienen vuelta atrás y `.venv-*` está ignorado.

  Correcto.
- **T0.1–T0.6** (`3808b77`):
  - el modelo del planner vive en un solo sitio;
  - `_is_plan_reply` lee los bloques por tipo;
  - los rechazos y el `max_tokens` dejan aviso (desviación 2, aceptada);
  - el ida y vuelta de `thinking` está cubierto por un test;
  - el flujo real de aclaración pasa sin 400.

  Correcto. Bien visto lo del riesgo de reenviar `thinking` con otro `system`: queda anotado como
  no descartado.
- **El precio en vivo** coincide con la skill.
- **La línea base de latencia** sale de goldens antiguos con Haiku 4.5, que es comparar lo mismo
  con lo mismo. Bien elegida.

## 2. D28: el criterio no se cumple con `effort: low`

51/55, con cuatro fallos estables (#21, #28, #48, #49). Lo que validan esos goldens según su
`validates` (no llamar a `salud`, encontrar la memoria) se cumple en los cuatro. Pero tres de
ellos fijan lo que Haiku 4.5 hacía por casualidad, y el #49 es un empeoramiento real: tres tools
sin motivo y una respuesta rara. **No se toca ni el criterio ni los goldens** después de ver los
resultados.

**Hueco del encargo (arquitecto):** elegí `low` sin una alternativa medida. La guía dice que con
menos esfuerzo el modelo piensa menos y a veces nada. Es justo lo que puede explicar las vueltas
del #49 y la búsqueda doble del #21.

## 3. Lo que se pide

- **R1 · Esfuerzo `medium`.** `_PLANNER_EXTRA = {"output_config": {"effort": "medium"}}`, en un
  commit propio. No cambia nada más.
- **R2 · [API] una pasada completa** (55 + aclaración) con `medium`, sobre el `.venv` nuevo
  (Python 3.12 + anthropic 1.14), que es la configuración que se desplegaría. Salida en
  `docs/fase2/goldens/`. Ya ha autorizado Josem (2026-10-14, en la ventana del arquitecto, opción
  B); confírmalo en tu ventana como siempre. El tope del hito sigue en 1,2 $, con 0,40 $ ya
  gastados.
- **El criterio del §4 del encargo es el mismo:**
  1. 55/55; un fallo intermitente solo se acepta si pasa al repetirlo;
  2. menos de 0,5 $ la pasada;
  3. una mediana que no empeore más de un 30 % frente a los 4,90 s de la línea base, es decir,
     6,37 s como mucho.
- **R3 · Según el resultado:**
  - **Si cumple:** D28 se adopta con `medium`. No toques los goldens.
  - **Si no cumple:** el planner vuelve a `claude-haiku-4-5-20251001` con `_PLANNER_EXTRA = {}`
    (dos líneas, un commit) y comprueba con `-k` #20–#23 y el flujo de aclaración en 4.5. T0.1,
    T0.3, T0.4 y T0.6 se quedan.

  En los dos casos, `fase-2` queda lista para el despliegue de Josem: Python 3.12 + 1.14 + el
  planner que salga.

## Para el programador

Responde a: 5c3b69b (H0-informe)

1. R1, y la pasada completa con `medium` (R2) cuando tengas el «sí» en tu ventana.
2. R3 según el resultado, sin tocar goldens.
3. Un anexo al informe de H0 (`## Anexo — esfuerzo medium`) con:
   - la tabla del criterio;
   - el coste por modelo;
   - los fallos, si los hay, con su repetición;
   - los comandos de despliegue actualizados, si cambian.

**Para en el anexo.**

## 4. Revisión del anexo (esfuerzo medium) — 2026-10-14

Responde a: da396b2 (H0-informe, «Anexo — esfuerzo medium»)

### 4.1 D28: no se adopta

Con `medium`, 47/55. Quitando los 3 fallos de entorno, quedan 5 de comportamiento: #28, #48 y #49
son estables en las tres pasadas de Haiku 5.5, y #03 y #24 son nuevos con `medium`. El criterio 1
no se cumple ni con `low` ni con `medium`. **El planner se queda en Haiku 4.5** (`99ac214`,
comprobado). No hacía falta repetir #03 y #24, porque no cambiaban la decisión.

- **En el ADR:** D28 pasa a `superada por D29`. D29: el planner sigue en Haiku 4.5, el código queda
  preparado para cambiar de modelo en una línea, y el modelo de la extracción de hechos de la fase
  2 se evalúa con sus propios goldens.
- **Indicador para volver a probar:** un Haiku nuevo, o una revisión de los goldens #28, #48 y #49
  hecha por su cuenta y no para que pase un modelo.

### 4.2 `requests` 2.34: hueco del encargo (arquitecto)

El §6 decía «solo la línea de `anthropic`; el resto de los pins se quedan». Eso dejaba sin fijar
unas 35 dependencias transitivas, y una de ellas rompía el tiempo. También elegí yo la lista de
goldens con `-k` de T0.9, y no había ninguno del tiempo. **La pasada completa lo cazó antes del
despliegue.** Bien contado, y bien reproducido con un venv de prueba.

**Decisión 1 — entorno: opción B, y que quede fijada en el repo.**
- **R4.** Genera `sebastian2/constraints-prod-2026-10-14.txt` con el `pip freeze` del `.venv` de
  producción (solo lectura; sin los editables).
  - Recrea el `.venv` del worktree con
    `pip install -r requirements.txt -c constraints-prod-2026-10-14.txt`, quitando de las
    constraints `anthropic` y lo que el SDK 1.14 exija en otra versión.
  - Si hay conflictos, gana lo que pida `anthropic` 1.14 y se lista en el informe con las dos
    versiones.
- **R5.** Después, siguiendo la norma del `CLAUDE.md` global (`pip freeze > requirements.txt`),
  `requirements.txt` pasa a ser el **freeze completo** de ese `.venv`. Se conserva la línea
  editable de `logcentral` y se añade un comentario de cabecera con la fecha y el porqué. Así el
  `.venv` de producción que recree Josem sale igual, sin depender de lo que resuelva `pip` ese
  día. Las constraints se pueden borrar después; cuenta si las borras.
- **R6 · Prueba.** En el informe:
  - un `diff` de `pip freeze` entre el `.venv` de producción y el nuevo, donde **solo** cambien
    `anthropic` y sus dependencias;
  - `pytest` completo;
  - **[API]** con `-k` en Haiku 4.5: #04, #05 y #51 (tiempo), #20 y #24.

  Unos 0,05 $; quedan 0,21 $ del tope de 1,2 $. Confirma el «sí» en tu ventana.

**Decisión 2 — aclaración con Haiku 4.5: se acepta el `skip`.**
- La precondición, que el modelo pida una aclaración, depende del modelo, y el camino de
  `_resume_plan` está cubierto con mocks.
- El `skip` lleva el detalle de los intentos, así que se ve.
- Ocho intentos sin una sola aclaración también es un dato: con Haiku 4.5 `request_clarification`
  apenas se usa (en producción, `pending_plans` está vacía). Lo anoto para la fase 2.

**Decisión 3 — goldens #21, #28, #48 y #49:** sin cambios, de acuerdo.

## Para el programador

Responde a: da396b2 (H0-informe, «Anexo — esfuerzo medium»)

1. R4 y R5: constraints de producción, `.venv` del worktree recreado y `requirements.txt` como
   freeze completo, en un commit propio.
2. R6: `diff` de freeze, `pytest` y `-k` [API] con el «sí» en tu ventana.
3. Anexo 2 del informe (`## Anexo 2 — entorno fijado`), con los comandos de despliegue
   definitivos. El paso 4 sigue siendo `pip install -r requirements.txt`, ahora con el freeze.

**Para en el anexo 2.** Si sale bien, H0 queda listo para que Josem lo despliegue.
