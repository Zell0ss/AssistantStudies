# H1d — Informe del programador (fase 4, parche D69): un dato no sustituye a otro de la misma frase

Responde a: `e77a764` (H1d-encargo, `3c863be`).
Commit en `fase-4`: `390b89c`. Suite completa: **1128 pruebas** pasan (1122 + 6), sin API. Gasto: 0 $.

## Hecho

- **R11 (`core/memoria/servicio.py`):** el `turno` de `guardar` lleva `atributos_creados`, un conjunto con los ids de los atributos que abrió esta llamada. `_procesar` añade el id cuando la resolución fue `crear`. `_resolver_atributo` recibe ese conjunto y quita esos ids de los candidatos **semánticos**, antes de calcular puntuación y margen. Por alias exacto se reutilizan igual que hoy.
- **R12 (`core/memoria/resolucion.py` y `servicio.py`):** cada candidato semántico lleva ahora su `tipo_valor`, junto a `tipos_entidad`. `resolver_atributo` recibe `tipo_valor` (opcional, por defecto `None`, así que las llamadas antiguas no cambian) y, si es distinto del del candidato, deja `fuerte=False`. Por alias no se toca. `decidir_hecho` no cambia: con `fuerte=False` ya manda el hecho a `nota`.
- **D69** está citado en un comentario en cada una de las dos costuras (`_resolver_atributo` y `resolver_atributo`), y en la que añade al turno.

## Pruebas

Seis nuevas, en `tests/test_memoria_d69.py` (BD `sebastian_test`, extractor y búsqueda semántica falsos, datos inventados). La búsqueda semántica falsa devuelve el atributo del id con 0,87 y de segunda `nota` con 0,51, es decir, margen 0,36 como en producción.

1. **El caso de producción:** `id_telegram` (numero, 700111222) y `usuario_telegram` (texto, @usuario_prueba) en una llamada. Salen 2 `crear_atributo` y 2 `anadir`, ningún `sustituir` ni `reutilizar_atributo`, y los dos valores siguen vigentes.
2. **Mismo nombre en la misma llamada:** 1 `crear_atributo` y 1 `reutilizar_atributo` con `via=alias`, y los dos valores añadidos.
3. **R12 entre turnos:** un atributo numero con valor vigente y un hecho texto que llega por semántica fuerte: va a `nota` (la decisión `reutilizar_atributo` queda con `fuerte=False`) y el id anterior sigue vigente.
4. **Control:** mismo `tipo_valor` por semántica fuerte: sustituye (`fuerte=True`), como hoy.
5. **Apoyo, R11 sola:** dos datos numero en una llamada; el segundo no sustituye al primero aunque coincida el tipo, así que R11 se prueba sin que R12 intervenga.
6. **Apoyo, `resolver_atributo` directamente:** tipo distinto por semántica es débil; mismo tipo, o sin `tipo_valor`, fuerte; por alias no cambia.

Sin el arreglo (código de `servicio.py` y `resolucion.py` apartado un momento), las pruebas 1, 3, 5 y 6 fallan y las 2 y 4 pasan, como debe ser: las dos últimas son los controles de lo que no cambia.

**La suite de memoria** (216 pruebas de memoria, resolución y fuentes) pasó **sin tocar ningún esperado**.

## Gasto

0 $. Sin API.

## Desviaciones

Ninguna. Esta vez todos los ficheros con Edit/Write. Una vez apartado el código con `git stash` para comprobar que las pruebas fallan sin él, y restaurado con `stash pop`; el árbol quedó como estaba.

## Un límite que conozco, sin retocarlo

**`retirar` por semántica con un `tipo_valor` por defecto.** Si Josem dice «olvida mi id» y el extractor no concreta el valor, `_validar` pone `tipo_valor="texto"` por defecto. Si la resolución del atributo llega por semántica (no por alias) y el atributo es numero, R12 la deja débil: `retirar_debil`, y se probaría la ruta de nota o de valor, que sin valor no cierra nada («No he encontrado qué olvidar»). Es raro, porque el prompt manda al extractor usar el nombre exacto del catálogo (alias), y el resultado es el seguro, no una sustitución mala. Si quieres cerrarlo, basta con no aplicar R12 a `retirar`, una línea en `_procesar` y su prueba. No lo he hecho: no está en el encargo.

## Despliegue (de Josem)

`main` está en `7f1593d` y es ancestro de `fase-4`, así que el merge es un avance directo. Hash para volver atrás: `7f1593d`.

Merge y reinicio:

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

Volver atrás, si hiciera falta:

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard 7f1593d && sudo systemctl start sebastian.service`

**Los datos que ya se estropearon en producción** (el id de Telegram de Josem, sustituido por el usuario el 20/11) no se arreglan con este parche: no hay migración, como dice el encargo. Si hay que recuperar el valor, es un dato que Josem puede repetir.

## Decisiones que necesito

1. ¿Aplico R12 solo a hechos que no sean `retirar`, para cerrar el límite de arriba? Mi recomendación: sí, pero en un retoque aparte, no antes de desplegar este.
