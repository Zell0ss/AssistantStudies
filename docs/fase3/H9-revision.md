# H9 — revisión (fase 3, parche): las fechas por el día de la semana y la búsqueda por palabras

> Responde a: ee7a0a3 (H9-informe). 2026-11-19, arquitecto. Revisado contra `b7df750..c9b188b` y la suite.

**Veredicto: aprobado con retoques.** Son dos, ninguno con API, y los dos van **antes** del despliegue: el primero evita un fallo que H9 introduce.

## 1. Contra el código

- **R22 (D60):** `_contexto_fecha` y `_reloj` (`core/orchestrator.py`). Los días van en una tupla sin `locale`, son 14 (hoy y los 13 siguientes) y se usan en los tres sitios. `_REGLA_FECHAS` va después de `_REGLA_COMPROMISOS`, y hay prueba de que `_PLANNER_TOOLS` no lleva la fecha. Bien.
- **R23 (D61):** `_normalizar_titulo` usa NFD y quita los diacríticos («ñ» pasa a «n», tanto en la consulta como en el título, así que casa). Las palabras vacías son las del encargo. Los dos niveles están bien, y con una consulta vacía se mantiene lo de antes. El log va sin texto, y la línea DEBUG que ya existía sigue igual: es DEBUG, así que está bien. Acepto las tres desviaciones:
  - filtrar en Python;
  - marcar solo los parciales;
  - que un recurrente sin próxima ocurrencia no cuente para el primer nivel.
- **R24 (D62):** la línea de `_ALFRED_SYSTEM` está, y la respuesta de #85 que copias es exactamente lo que buscaba.
- **Suite:** la he ejecutado yo: **939 pasan**.
- **Arnés:** acepto el modo `calendario`, la limpieza de eventos y el criterio de palabras completas. Lo de la contaminación entre goldens lo cazaste por la salida y lo dijiste. Bien.
- **Proceso:** has editado dos ficheros con `python3` en Bash. Lo apunto y nada más.

## 2. Resultados [API]

- **D60 funciona:** 12 de 12 fechas bien en #81–#83, y en #81 el 20/11 las 4 veces. La regresión de calendario y fechas da 17/17, incluidos #79 y #80.
- **R23 en el caso real:** #84 da 1 de 1 limpio. Es poca evidencia, como dices. La prueba buena es la de producción, cuando Josem mueva el evento 4947.
- **#83 da 3/4:** la ejecución que falla añade un `calendar_find_by_datetime` antes de crear. La fecha es correcta y la tool extra es de solo lectura. No lo toco.
- **Gasto:** 0,429 $, con el «sí» de Josem registrado. La fase va por **≈ 11,00 $ de 11,50 $**.

## 3. Decisiones que pedías

| # | Decisión |
|---|---|
| 1 | **#81: opción (a).** El hueco es mío (arquitecto): puse una dirección en la frase y pedí la secuencia exacta. Guardar la dirección como nota es lo correcto. #81 acepta `[calendar_add_event]` o `[calendar_add_event, calendar_add_note]`, siempre con la `entrada` de fecha y hora en el `add_event` |
| 2 | **`ticket_handler`: se arregla ahora, en este retoque.** Lo introduce D61, y no se despliega un fallo nuevo. La asociación directa solo vale para los del primer nivel. Si solo hay parciales, se sigue el flujo de preguntar |
| 3 | Despliegue: con tus pasos, después de los retoques. Lo hace Josem |

## 4. Retoques (sin API)

- **R25 — `bot/ticket_handler.py:166`:** antes de coger `events[0]`, descarta los que llevan `coincidencia == "parcial"`. Si no queda ninguno, `event_id` se queda en `None` y sigue el flujo de preguntar, como hoy. Cita D61 en un comentario. **Pruebas:** con solo «Cena de Navidad BNP» en la agenda, la leyenda «cena con Ana» no asocia y pregunta; con la leyenda «BNP», asocia. Cada una con el doble de `bot` que ya usen las pruebas del handler. Si no hay ninguno, el mínimo.
- **#81:** cambia el golden según la decisión 1. Vuelve a juzgar las 4 salidas guardadas con el criterio nuevo, sin repetir la pasada, y da el resultado. Espero 4/4.

## Para el programador

Responde a: ee7a0a3 (H9-informe)

1. Haz R25 con sus dos pruebas.
2. Cambia #81 y vuelve a juzgar las salidas guardadas (sin API).
3. Pasa la suite.
4. Escribe un anexo corto al final de `H9-informe.md` con los commits y los dos resultados, y para.

Sin gasto. El despliegue lo hace Josem después de que yo revise el anexo.
