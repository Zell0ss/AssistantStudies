# H2 — revisión (fase 3)

> Responde a: 2d11459 (H2-informe). 2026-11-16, arquitecto. La revisé contra el código de la rama
> `fase-3` en `2d11459`.

**Veredicto: aprobado, sin retoques.** Sigue H3.

## 1. Lo que comprobé

- **Pruebas sin API:** `pytest -m "not golden"` da **767 en verde**, lo mismo que el informe; 32
  de ellas son del planificador.
- **D51 al pie de la letra:** en `enviar_avisos` la ventana es `ahora − 2 h < m ≤ ahora`, se
  comprueba `aviso_para ≠ m`, y `registrar_aviso` (con commit) va **después** de
  `send_message`. Si el envío falla, sigue sin marca.
- **Lecturas frescas en cada pasada:** cada tarea saca su propia conexión del pool y la cierra.
  `PooledDB` trae `reset=True`, así que cada devolución hace rollback. Una pasada no puede
  arrastrar la foto de una transacción vieja y dejar de ver un compromiso recién creado desde un
  manejador. Era lo que más me preocupaba de usar un planificador dentro del bot, y está bien.
- **Que no se solapen:** `max_instances=1` y `coalesce=True` en la tarea de cada minuto. La
  pasada de arranque corre a los 2 s y la primera periódica a los 60 s, así que no coinciden.
- **Logs sin el texto** de los compromisos, ni en los avisos ni en los errores (solo la clase de
  la excepción).

## 2. Decisiones que pedía

| # | Decisión |
|---|---|
| 1 | **Vale tu formato.** La prueba de «igual que hoy» manda sobre mi ejemplo: el resumen de siempre no cambia para quien no tiene compromisos. Los `**` literales ya salían antes, y no los toco en esta fase |
| 2 | **Se queda como dice el plan.** «Llevar el parte» sale el 17 a las 08:00, con la cita a las 9:30 y tiempo de sobra. Me equivoqué en la tabla del caso y la corrijo yo. Si en el uso real un paso sin hora del día de una cita temprana llega tarde, pasa a la fase 4 como «mañana:» en el resumen de la víspera |
| 3 | Aceptado, es lo que dice D51: mejor repetir un aviso que perderlo |

## 3. Desviaciones

Las seis quedan **aprobadas**. La 2 (conexión propia y no el singleton) y la 3 (un «caducado»
una sola vez) mejoran el plan.

Una nota sin cambio: `armar_resumen` con `conn=None` sigue usando el singleton y
`close_connection()`. El planificador nunca entra por esa rama, porque siempre le pasa su
conexión. Si alguien la llama desde un manejador, tendría el problema que tú mismo describes en
la desviación 2. Déjalo escrito en el docstring cuando toques el fichero.

## 4. Gasto

**0,00 $.** Llevamos 0 de los 4 $. H3 es el primer hito con [API].

## Para el programador

Responde a: 2d11459 (H2-informe)

H2 aprobado. Sigue con **H3** (§3 del plan):
1. Antes del primer [API], comprueba con la skill `claude-api` los ids y los precios (§4).
2. Copia #67–#76 tal cual en `goldens.yaml`. Haz su línea base con `-k` e ids exactos, y ×3 en
   los intermitentes. Después, una pasada completa (#1–#76).
3. Escenario E10 ×3. El criterio es la BD y `armar_resumen`: los compromisos tienen que tener
   `evento_id` (riesgo §5).
4. Cada [API] se confirma con Josem en tu ventana. El tope son 4 $. Si cae un golden antiguo,
   para y cuéntalo.
5. **Para** con `docs/fase3/H3-informe.md`.
