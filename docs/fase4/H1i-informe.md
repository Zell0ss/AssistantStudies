# H1i — Informe del programador (fase 4, D73): una consulta solo con `query` busca por sus palabras

Responde a: `578a048` (H1i-encargo, `fd49190`).
Commit en `fase-4`: `0c0bc59`. Suite completa: **1203 pruebas** pasan (1190 + 13), sin API. Gasto: 0 $.

## Hecho

Todo en `core/memoria/servicio.py` (`consultar`), más una frase en `core/orchestrator.py`.

- **R23 — los términos de la `query` buscan hechos:** sin `entidad` ni `atributo` y con una `query`, `consultar` devuelve los hechos **vigentes** del usuario cuya entidad o cuyo atributo comparten una palabra con la `query`.
  - **Términos:** `normalizar(query)`, troceado por espacios y `_`, de 4 letras o más, sin `yo`. Es el mismo criterio de D71, ahora en un solo sitio (`_terminos`).
  - **Coincide** un hecho si algún término es igual al nombre normalizado de su entidad, a uno de sus alias, **o** a una pieza del nombre de su atributo (`telegram_id` → `telegram`, `id`). El atributo `nota` queda fuera, porque las notas van por palabra.
  - **Salida:** como mucho 20 hechos (`_MAX_HECHOS_POR_PALABRAS`), los más recientes primero, y `"por_palabras": true`. La clave solo está si salió algún hecho por palabras, así que la salida de los demás casos no cambia.
  - Con `entidad` o `atributo`, todo sigue como en D71, incluido «entidad que no se resuelve = 0 hechos».
- **R24 — los mismos términos buscan notas:** `_notas_para` busca por palabra con los términos de la `query` además de los de la `entidad` y el `atributo` (se unen, sin repetir; las semánticas van primero; el tope sigue en 3). La búsqueda de notas por palabra recibe ahora el conjunto de términos.
- **Alfred (`_ALFRED_SYSTEM`):** una frase en «Memoria (consulta)»: con `por_palabras`, los hechos salen por coincidencia de palabras con la pregunta; contesta solo con los que vienen a cuento (D73).
- **R16:** el log `memoria.consultar` añade `por_palabras=N` (cuántos hechos salieron por palabras, sin contenido). **Lo he puesto al final de la línea**, después de `notas_palabra=`, para no mover lo que ya estaba: así no cambia ningún esperado de H1f (que busca `notas_sem=0 notas_palabra=1` seguido).
- **D73** está citado en un comentario en cada costura (`consultar`, `_notas_para`, `_hechos_por_palabras`, el log y el prompt).

## Pruebas (13 nuevas en `tests/test_memoria_d73.py`, BD `sebastian_test`, embedder falso, datos inventados)

1. **El caso de la traza:** `yo · telegram_id = 700111222` y la nota «Mi usuario de Telegram es @usuario_prueba» (con su punto en Qdrant, por debajo del umbral). Con solo `query="Telegram"` sale el hecho con `por_palabras`, sale la nota, y el log dice `por_palabras=1` y `notas_sem=0 notas_palabra=1`. (El encargo escribe `por_palabras=1 notas_palabra=1` seguido; con el orden que he elegido son dos fragmentos de la misma línea.)
2. **Pregunta larga:** `¿qué datos tienes de mí en Telegram?` da el mismo resultado: «datos» y «tienes» no coinciden con nada.
3. **Por entidad:** `query="Paco"` saca los dos hechos vigentes de Paco, el más reciente primero. También por pieza del atributo (`alergia`) y por alias de la entidad.
4. **Otro usuario** y **hechos cerrados** (con `historial=True`): nunca salen.
5. **Con `entidad` o `atributo`:** entidad que no se resuelve → 0 hechos; entidad sí y atributo no → R14, sin `por_palabras`; atributo sin entidad que no se resuelve → 0 hechos; ambos resueltos → lo de siempre.
6. **Términos cortos y `yo`:** `de mi`, `yo`, `mi yo de` y `¿y a mí?` no buscan nada.
7. **Marca `ZZQUERY`** en la query, en una entidad y en una nota: sale en el resultado y no sale en ningún log.
8. **Tope de 20:** con 25 hechos de una entidad salen 20, del 24 al 05.
9. **R24:** la query busca notas aunque haya `entidad`, y se unen a las del atributo sin repetir.
10. El orden del log y la frase del prompt de Alfred.

Sin el cambio, fallan 12 de las 13; la que pasa es un control de lo que no cambia.

**La suite** (303 pruebas de memoria, consulta, D71 y depuración) pasó **sin tocar ningún esperado**: no se ha editado ninguna prueba existente.

## Gasto

0 $. Sin API.

## Desviaciones

Una pequeña: el orden de `por_palabras=N` en el log (arriba), para no tocar esperados de H1f. Todos los ficheros con Edit/Write. De nuevo, `git stash` un momento para comprobar que las pruebas fallan sin el cambio, y `stash pop` después.

## Límites que conozco, sin retocarlos

- **Una entidad de varias palabras** («coche azul») no coincide con un término suelto («coche»): se compara el nombre normalizado entero o un alias. Es lo que dice el encargo. Si hiciera falta, se partiría el nombre en piezas.
- **Palabras muy comunes en la pregunta** pueden coincidir con una nota que las contenga («datos», «tienes», si alguna nota las dijera). Con el tope de 3 notas y 20 hechos, y la frase para Alfred, no debería molestar; la próxima traza de `/debug` lo dirá.
- **Singular y plural** siguen sin igualarse (D71).

## Despliegue (de Josem)

`main` está en `dc0ca28` (H1f + H1g + H1h ya desplegados) y es ancestro de `fase-4`, así que el merge es un avance directo. Hash para volver atrás: `dc0ca28`.

Merge y reinicio:

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

Volver atrás, si hiciera falta:

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard dc0ca28 && sudo systemctl start sebastian.service`

Para ver el efecto, tras repetir «¿Qué datos tienes de mí en Telegram?» (sin `sudo`): `logcentral query --source sebastian --grep "memoria.consultar" --pretty`, o la traza de `/debug`.

## Decisiones que necesito

Ninguna.
