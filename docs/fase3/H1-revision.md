# H1 — revisión (fase 3)

> Responde a: fffd7dc (H1-informe). 2026-11-16, arquitecto. La revisé contra el código de la rama
> `fase-3` en `532689b`.

**Veredicto: aprobado.** Hay un retoque pequeño (R1), que va dentro de H2 sin otra vuelta.

## 1. Lo que comprobé

- **Pruebas sin API:** `pytest -m "not golden"` da **731 en verde**, lo mismo que el informe.
- **Esquema:** `013_compromisos.sql` es el SQL de §2.1 tal cual, sin `USE`.
- **Forma y momento:** `validar_forma` cubre las cinco reglas de §2.1. `momento_efectivo` suma
  días como fechas del calendario (D50).
- **Usuarios aislados:** `_evento`, `completar`, `borrar` y `cancelar_por_eventos_borrados`
  filtran todos por `user_id`.
- **Borrado de eventos:** los únicos dos `DELETE FROM events` del código pasan antes por
  `cancelar_por_eventos_borrados`, en la misma transacción.

## 2. Decisiones que pedía

| # | Decisión |
|---|---|
| 1 | **Vale el código, sin `ON DELETE SET NULL`.** Bien cazado: el plan se equivocaba, porque una fila cancelada también bloquea la FK. El resultado es el mismo, y el SQL del contrato no cambia. **Consecuencia que hay que respetar:** una fila hecha o cancelada de un evento borrado queda con `evento_id = NULL` y su `dias_*` o `minutos`, así que ya no cumple la forma. Por eso **`momento_efectivo` solo se llama sobre pendientes**, como hoy (`pendientes`, `listar`). Pon esa regla en el docstring de `momento_efectivo` |
| 2 | **Vale rechazar los eventos recurrentes.** Atar a «la próxima ocurrencia» sería otro contrato, y el caso no lo necesita. Si sale en el uso real, irá a la fase 4 |
| 3 | De acuerdo con vigilarlo. Si #67 cae en `tasks_create`, se arregla en la descripción de las dos tools, nombrando qué es cada una, no prohibiendo |

## 3. Desviaciones

| # | Valoración |
|---|---|
| 3 (sin texto en los logs de las cuatro tools) | **Aprobado.** Es lo correcto por D52 y por R12 |
| 4 (`conftest.py` de los goldens) | Aprobado. Se comprueba en la primera pasada [API] de H3 |
| 5 (`pendientes` y `Momento.problema`) | **Aprobado.** Que un paso que no se puede calcular salga siempre, con el motivo, es mejor que perderlo en silencio |
| 6 (descripciones) | Aprobado lo de buscar antes el evento. Sobre `calendar_remove_event`, mira R1 |

## 4. Hallazgos (arquitecto)

- **R1. Borrar una cita cancela su preparación sin que Alfred lo sepa.**
  `cancelar_por_eventos_borrados` devuelve cuántos compromisos ha cancelado, pero ese número se
  pierde: `remove_event` y `remove_event_by_id` no lo devuelven.
  - **Qué pasaría:** si Josem borra la colonoscopia, Alfred contesta «borrada» y nada más, y
    los pasos de la preparación desaparecen del resumen sin que nadie lo haya dicho.
  - **Arreglo:** el resultado de `calendar_remove_event` lleva `compromisos_cancelados: n`
    cuando `n > 0`. La descripción de la tool no se toca: Alfred ve el campo y lo cuenta, y los
    goldens de calendario no se mueven.
  - **Prueba:** `test_remove_event_informa_compromisos_cancelados`.
- **Nota, sin cambio de código:** `minutos` se suma en hora local sin zona. La noche del cambio
  de hora, «3 horas antes» es en hora de reloj, no en tiempo real. Pasa dos noches al año, entre
  las 2 y las 3, y lo acepto. Déjalo dicho en una línea del docstring de `momento_efectivo`.

## 5. Gasto

**0,00 $.** Llevamos 0 de los 4 $.

## Para el programador

Responde a: fffd7dc (H1-informe)

H1 aprobado. Sigue con **H2** (§3 del plan), y mete en él:
1. **R1:** que `calendar_remove_event` devuelva `compromisos_cancelados`, con su prueba.
2. Los dos apuntes de docstring de §2.1 y §4 en `momento_efectivo`: solo se llama sobre
   pendientes, y `minutos` va en hora de reloj.
3. **Para** con `docs/fase3/H2-informe.md`. H2 sigue siendo sin API, y ninguna prueba manda nada
   a Telegram de verdad (§4 del plan).
