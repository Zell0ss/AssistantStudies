# H1e — Informe del programador (fase 4, parche D70): el valor tiene que encajar con el tipo del atributo

Responde a: `390b89c` / H1d-informe (H1e-encargo, `fcf5494`).
Commit en `fase-4`: `00707de`. Suite completa: **1155 pruebas** pasan (1128 + 27), sin API. Gasto: 0 $.

## Hecho

- **R13 (`core/memoria/resolucion.py`):** `valor_encaja(valor, tipo_valor) -> bool`, función pura.
  - `numero`: `^[+-]?\d[\d.,]*(\s*\S.*)?$`, el patrón del encargo.
  - `fecha`: `AAAA-MM-DD` o `--MM-DD`.
  - `booleano`: sí, si, no, true, false, verdadero, falso, sin distinguir mayúsculas.
  - `texto`, o un tipo que no conozco: todo encaja.
  - Un valor vacío tampoco se juzga, y devuelve `True`. Solo `retirar` lo trae vacío, y `retirar` no pasa por aquí.
- **Dónde se aplica (`servicio.py`, `_procesar`):** después de resolver el atributo y de leerlo, y antes de `decidir_hecho`. Solo si el atributo se **reutilizó** (por alias o por semántica) y la operación no es `retirar`. Si el valor no encaja con el `tipo_valor` del atributo, `fuerte` pasa a `False`: con un valor vigente va a `nota`; sin vigente se añade, como hoy.
- **Registro:** la decisión lleva `"tipo_no_encaja": true` en sus `senales`, solo en ese caso. Nunca el valor (D42): una prueba comprueba que `@usuario_prueba` no aparece en la decisión.
- **Lo recién creado no se juzga:** un atributo nuevo toma el tipo del propio hecho, así que no hay contra qué comparar.
- **D70** está citado en el comentario de `_procesar`.
- **Retoques pendientes de H1d:**
  - **R12 no se aplica a `retirar`** (`_resolver_atributo` pasa `tipo_valor=None`).
  - **Trozos vacíos:** `_partir_en_trozos` descarta los trozos vacíos o de solo espacios (`if t.strip()`). El texto de un solo trozo no se toca, así que `_partir_en_trozos("") == [""]` se mantiene.
  - **El espacio** de `atributo =self._repo…`, arreglado.

## Pruebas (27 nuevas, datos inventados)

En `tests/test_memoria_d70.py` (BD `sebastian_test`, extractor y búsqueda semántica falsos) y una en `tests/test_send_markdown.py`.

1. **El caso de producción, por alias:** `telegram_id` (numero) con `700111222` vigente, y un hecho `telegram_id = @usuario_prueba` por alias. Va a `nota`, el id sigue vigente y la decisión lleva `tipo_no_encaja: true`.
2. **Corrección legítima por alias:** `telegram_id = 700999888` sustituye al anterior (`corregir`), sin `tipo_no_encaja`.
3. **`valor_encaja`:** 21 casos parametrizados. Los del encargo (`2,4 bar`, `-3.5`, `815566372` sí; `@usuario`, `unos 30` no; `--03-12` sí, `12 de marzo` no; `sí` sí, `quizá` no; texto, todo) más signo `+`, fecha completa, `2026-11`, mayúsculas, `Verdadero`, valor vacío y un tipo desconocido.
4. **Sin valor vigente y sin encaje:** tras retirar el id, `telegram_id = @usuario_prueba` se añade, con `tipo_no_encaja`. No pisa nada.
5. **`retirar`:** por alias y con valor vacío funciona (se usa en la 4). Por semántica, con `tipo_valor` texto por defecto contra un atributo numero, ya no se debilita: se retira y la decisión sale `fuerte=True`.
6. **Apoyo:** lo recién creado no se juzga por tipo, aunque el valor parezca raro.
7. **Trozos vacíos:** tres textos con una línea en blanco antes de una línea de más de 4000 caracteres no devuelven trozos vacíos, y por `_send_markdown` salen dos mensajes (4000 y 500), ninguno vacío.

Sin el arreglo (`servicio.py` y `handlers.py` apartados un momento), fallan las pruebas 1, 4, 5 y la de trozos vacíos; las demás son los controles de lo que no cambia.

**La suite de memoria** pasó **sin tocar ningún esperado**: no se ha editado ninguna prueba existente, solo se han añadido.

## Gasto

0 $. Sin API.

## Desviaciones

Ninguna. Todos los ficheros con Edit/Write. De nuevo, `git stash` un momento para comprobar que las pruebas fallan sin el arreglo, y `stash pop` después; el árbol quedó como estaba.

## Límites que conozco, sin retocarlos

- **`numero` es de forma, no de significado.** El patrón del encargo deja pasar «12 de marzo» o «1234 ABC» como número (empiezan por cifra y tienen algo detrás, como una unidad). Para el `@usuario` y los textos que no empiezan por cifra, que es el caso de producción, basta.
- **Un atributo `varios` con tipo numero** que reciba un texto lo añade igualmente (en `varios`, `decidir_hecho` siempre añade), con `tipo_no_encaja` en la señal. Hoy los atributos semilla `varios` son de texto, así que no se da.

## Despliegue (de Josem)

`main` está en `4c044fc` y es ancestro de `fase-4`, así que el merge es un avance directo. Hash para volver atrás: `4c044fc`.

Merge y reinicio:

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

Volver atrás, si hiciera falta:

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard 4c044fc && sudo systemctl start sebastian.service`

Los datos que ya se estropearon en producción no se recuperan con este parche (no hay migración).

## Decisiones que necesito

Ninguna.
