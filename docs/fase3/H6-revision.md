# H6 — revisión (fase 3, diagnóstico)

> Responde a: 38ae801 (H6-informe). 2026-11-16, arquitecto.

**Veredicto: H6 queda cerrado sin las dos filas con historial. El arreglo va en H7.**

## 1. Lo que añadí, sin coste: los logs de producción

`logcentral query --source sebastian`, 16/11. Las horas van en UTC, así que 15:03Z son las 16:03 de Josem.

| Turno | Historial | iterations | tokens_in | tokens_out |
|---|---|---|---|---|
| 15:03:29 «Recuérdame está noche…» (falló) | 6 | 1 | 14 553 | 92 |
| 15:05:52 «Recuérdame el 17…» (creó) | 6 | 2 | 27 265 | 187 |
| 15:12:26 «Recuérdame mañana martes 17…» (falló), 17 s después de un borrado | 6 | 1 | 14 469 | 78 |
| 15:21:26 «Crea un compromiso para el martes 17…» (creó) | 6 | 2 | 27 018 | 164 |

- En los dos fallos el planner hizo **una sola llamada**. Una llamada son ≈12 000 tokens de entrada, más ≈2 000 de Alfred.
- Escribió un texto corto: ≈30–40 tokens, si a los 78–92 se les quita lo de Alfred. Después cerró con `end_turn`.
- En `core/orchestrator.py:536` ese texto se descarta. Alfred recibe `_TURNO_SIN_HERRAMIENTAS` y dice «no he podido».
- El texto no está en el log (D42), así que no puedo saber si era una pregunta. Es coherente con tu hipótesis del historial, pero no la prueba.

## 2. Por qué no pago las dos filas con historial

Saldría lo mismo fuera cual fuera la causa. Pase lo que pase, el planner a veces cierra sin tool y con un texto, y ese texto se pierde. El arreglo es que **no se pierda** (R17). La fila 1×b que encontraste, la 01:00 del 16 con la hora ya pasada, pide además **una regla de madrugada y una red en el código** (R18 y R19).

## 3. Lo que acepto

- Los textos de «planner sin tool» que salen después de una tool no son fallos, tal como dices. R17 lo tiene en cuenta: solo cuenta el cierre **sin ninguna** tool.
- **Gasto:** 0,1178 $, que pasa del tope en 0,018 $. Aceptado: paraste en cuanto lo viste y lo dijiste. Josem ha subido el tope de la fase a **11 $** para H7.

## Para el programador

Responde a: 38ae801 (H6-informe)

H6 cerrado. Tienes el encargo de H7 en `docs/fase3/H7-encargo.md`.
