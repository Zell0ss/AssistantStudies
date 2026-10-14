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
