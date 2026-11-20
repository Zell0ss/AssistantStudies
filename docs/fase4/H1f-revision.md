# H1f — revisión (fase 4, parche D71)

> Responde a: c13e0dc (H1f-informe). 2026-11-20, arquitecto. Revisado contra `5b69614..c13e0dc` y la suite.

**Veredicto: aprobado. Josem lo despliega.**

- **R14:** la ampliación solo se hace con la entidad resuelta y el atributo no. Los otros tres casos siguen dando 0. Devuelve solo lo vigente y la clave aparece solo en ese caso. Bien.
- **El esperado que cambia** (`test_memoria_consulta.py`) es justo el caso que D71 cambia. Está comentado y ampliado con los casos que siguen igual. Lo acepto.
- **R15:** solo notas vigentes y del usuario, con palabra completa normalizada. La semántica va primero, sin repetir y con tope 3. Funciona sin `query`. Bien.
- **R16:** solo estados y conteos. `ZZCONS` queda fuera del log. Bien.
- **El prompt de Alfred:** la frase está y cita D71.
- **Suite:** la he ejecutado yo: **1168 pasan**. `main` (`0ba236a`) es ancestro de `fase-4`.
- **Gasto:** 0 $.
- **Los límites que señalas los acepto como están:** que la ñ no se pliegue, singular y plural, y que Alfred vea más hechos. El último se mide en producción (D71, indicador).

**Un caso que no cubre, para leer el log:** si el planner manda `entidad="Telegram"` en lugar de `yo`, la entidad no se resuelve. Saldría solo la nota por palabra, sin el hecho del id. R16 lo dirá: `entidad=no_resuelta`. Si pasa, el remedio va al planner, no a la memoria.

## Para el programador

Responde a: c13e0dc (H1f-informe)

H1f aprobado. Para hasta que te escriba. Lo siguiente probablemente sea un modo de depuración temporal, si Josem lo aprueba.
