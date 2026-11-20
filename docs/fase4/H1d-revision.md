# H1d — revisión (fase 4, parche D69)

> Responde a: 390b89c / H1d-informe. 2026-11-20, arquitecto. Revisado contra `3c863be..HEAD` y la suite.

**Veredicto: aprobado. Josem lo despliega.**

- **R11:** el conjunto `atributos_creados` se llena solo con `accion == "crear"` y se filtra **antes** de puntuar. Así, un atributo recién creado tampoco le quita margen a otro candidato. Por alias se sigue reutilizando. Bien.
- **R12:** `tipo_valor` es opcional, así que las llamadas antiguas no cambian, y por alias no se toca. Bien.
- **Pruebas:** el caso de producción está, con margen 0,36. Fallan sin el arreglo y pasan con él, y los dos controles se mantienen. La suite de memoria pasa sin tocar ningún esperado.
- **Suite:** la he ejecutado yo: **1128 pasan**. `main` (`7f1593d`) es ancestro de `fase-4`.
- **Gasto:** 0 $.
- **Detalle de estilo:** en `servicio.py` falta un espacio en `atributo =self._repo…`. Arréglalo la próxima vez que toques el fichero.

## Tu decisión 1: R12 y `retirar`

**Sí, pero en un retoque aparte y no ahora.**

El límite que señalas existe. Su resultado es el seguro: no se olvida nada y se avisa, y no se borra nada que no tocaba. Además, solo pasa por semántica y sin valor, y el prompt manda al extractor usar el nombre exacto del catálogo.

Lo junto con el hallazgo de los trozos vacíos de `_partir_en_trozos` (H1b §4). Los dos van en el próximo encargo que toque esos ficheros: H2 o un parche si hiciera falta.

## Para el programador

Responde a: H1d-informe (390b89c)

H1d aprobado. Para hasta que te escriba. Pendientes para el próximo encargo:
- R12 no se aplica a `retirar`;
- descartar los trozos vacíos en `_partir_en_trozos`;
- el espacio que falta en `servicio.py`.
