# H8 — revisión (fase 3, parche): el planner cachea sus herramientas

> Responde a: 93f3350 (H8-informe). 2026-11-19, arquitecto. Revisado contra `c4fa88a` (diff `c543917..c4fa88a`) y la suite.

**Veredicto: aprobado.** Listo para el despliegue de Josem.

## 1. Contra el código

- **R20:** `_PLANNER_TOOLS = [*ALL_TOOLS[:-1], {**ALL_TOOLS[-1], "cache_control": {...}}]` (`core/orchestrator.py:47`). Copia la lista y solo el último dict. `ALL_TOOLS` queda intacta, y `_llamar_planner` es el único sitio que la cambia. No tocaste el `system`, los `messages` ni las demás llamadas. D59 está citado. Bien.
- **R21:** los dos contadores, con `getattr(..., 0) or 0`. `tokens_in` sigue siendo solo lo no cacheado, y `Turn end` lleva los dos campos en `bind` y en el texto. He buscado otros consumidores de `_turn_usage` y de la línea `Turn end` (en el repo, en sereno y en glasspannel) y no hay ninguno: añadir campos no rompe nada.
- **`_uso_vacio()`:** la desviación es buena, porque quita un diccionario repetido. La acepto.
- **Suite:** la he ejecutado yo: **907 pasan**, igual que en el informe.

## 2. Resultados [API]

- La caché se comporta como decía el encargo. La primera llamada escribe 10 240 tokens y las tres siguientes los leen. La lectura sigue funcionando al cambiar de turno, aunque la hora del `system` cambie. Queda probado el supuesto de D59: lo que va después de `tools` no invalida la caché.
- **Mi estimación se quedó corta, y es un fallo mío (del encargo).** Calculé ~7000 tokens a partir de los bytes, y son ~10 500. El ahorro es mayor del que preveía.
- **Los ~320 tokens que no entran en caché (10 560 frente a 10 240):** no hay que investigarlos. Mi hipótesis, sin comprobar, es que `count_tokens` cuenta también el texto de sistema que la API añade cuando hay tools, y ese texto no forma parte del prefijo de `tools`. No cambia nada de lo que decidimos.
- **Gasto:** 0,036 $, con el «sí» de Josem registrado en la ventana del programador. La fase queda en **≈ 10,57 $ de 11,50 $**.

## 3. Lo que queda fuera (para mí, no para ti)

- **Alfred:** son 1416 tokens. Sonnet 4.6 cachea a partir de 1024 (lo he comprobado con la skill `claude-api`), así que podría cachearse. Pero se llama una sola vez por turno, y solo ahorraría cuando dos mensajes caen a menos de 5 minutos, unos 0,004 $ cada vez. No lo encargo ahora. Lo decidiré cuando haya una semana de `cache_read` en producción.
- **El extractor:** son 2008 tokens, por debajo del mínimo de Haiku 4.5. No se cachea.
- **El `system` del planner con índice real:** sin medir. Solo importaría si se reordena el `system`, que toca D36. Queda para la fase 4, si llega.

## 4. Decisiones

Ninguna nueva. D59 se mantiene en tentativa hasta tener una semana de producción, con su indicador: si `cache_read` es menos del 30 % de la entrada del planner, la reviso.

## Para el programador

Responde a: 93f3350 (H8-informe)

H8 aprobado. No queda nada más: para hasta que te escriba. El despliegue lo hace Josem con los pasos de tu informe.
