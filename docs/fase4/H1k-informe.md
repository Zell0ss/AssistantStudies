# H1k — Informe del programador (fase 4, D59): el log de fin de turno separa el uso por papel

Responde a: `0b7d605` (H1k-encargo, `ff1c18a`).
Commit en `fase-4`: `49828c9`. Suite completa: **1222 pruebas** pasan (1215 + 7), sin API. Gasto: 0 $.

## Hecho

Todo en `core/orchestrator.py`.

- **R26 — el uso por papel:** `_track_usage(response, model, papel="otro")`, con `papel` en `planner`, `extractor`, `alfred` u `otro` (un papel desconocido cuenta como `otro`). Por cada papel se acumulan `in`, `out`, `cr` (`cache_read`) y `cc` (`cache_creation`), en `_turn_usage["por_papel"]`. Un papel cuenta desde su primera llamada, aunque la respuesta no traiga `usage`. Los totales de siempre no cambian.
  - Planner: la llamada normal del bucle (`_llamar_planner`).
  - Extractor: el `on_usage` del ejecutor pasa `extractor`.
  - Alfred: la síntesis y la pregunta de aclaración.
  - Otro: la llamada SI/NO de «¿es una respuesta al plan pendiente?» (`_is_plan_reply`).
- **R27 — el log:**
  - `Turn end` **se queda exactamente igual**: el mismo texto y los mismos campos de `bind`, sin ninguno nuevo.
  - Detrás va una segunda línea `INFO`: `Turn uso | user=… | planner=in/out/cr/cc | extractor=… | alfred=… | otro=…`, en ese orden y solo con los papeles que tuvieron llamadas.
  - Los mismos datos van en `bind` como `uso_por_papel` (un dict).
  - Sin contenido.
  - **Un detalle de orden:** el logger de `Turn uso` se crea (con su `bind`) *antes* de emitir `Turn end`, y la línea se escribe después. Así el último `bind` del turno sigue siendo el de `Turn end`, y la prueba que ya existía sobre él (R21: `bind.call_args_list[-1]`) pasa sin tocarla.
- **D59** está citado en un comentario en cada costura.

Ejemplo de lo que saldrá en `logcentral` para un turno con memoria:

`Turn uso | user=… | planner=110/25/10100/0 | extractor=300/40/0/0 | alfred=900/60/0/0`

## Pruebas (7 nuevas en `tests/test_uso_por_papel.py`, cliente falso)

1. **Un turno completo** (planner → `mark_as_memorable` → extractor, cuyo uso llega por `on_usage` → planner → Alfred): sale `Turn uso` con los tres papeles y **las sumas cuadran con `Turn end`** (tokens_in 1310, tokens_out 125, cache_read 10100, cache_creation 0). Los mismos datos están en el `bind`.
2. **Un turno sin tools:** solo `planner` y `alfred`, con `cache_creation` incluida.
3. **`Turn end` igual que antes:** el mismo texto y el mismo conjunto de campos de `bind` (sin `uso_por_papel`), el último `bind` es el suyo, y `Turn uso` sale detrás.
4. **Ninguna marca (`ZZUSO`)** en ningún log del turno.
5. **Papel por defecto `otro`**, papel desconocido a `otro`, una llamada sin `usage` cuenta, y los totales de siempre no cambian.
6. **La llamada SI/NO** de un plan pendiente va a `otro`.
7. **Cada turno empieza con el reparto vacío.**

Sin el cambio, fallan las 7. **La suite** pasó **sin tocar ningún esperado**: no se ha editado ninguna prueba existente.

## Gasto

0 $. Sin API.

## Desviaciones

Ninguna. Todos los ficheros con Edit/Write. Una comprobación con `git stash` un momento (y `stash pop` después) para ver que las pruebas fallan sin el cambio.

## Para leerlo (D59, ≈ 26/11), sin sudo

`logcentral query --source sebastian --grep "Turn uso" --pretty`

El `bind` lleva `uso_por_papel`, así que en el JSON de LogCentral se puede agrupar por papel. Lo que importa para saber quién gasta sin caché: en cada papel, `in` (no cacheado) frente a `cr` (leído de caché) y `cc` (escrito en caché). Alfred no lleva `cache_control` (como decías): sus `cr` y `cc` saldrán en 0, y su `in` será todo el prompt.

## Despliegue (de Josem), H1j y H1k juntos

`main` está en `9f64780` (H1i ya desplegado) y es ancestro de `fase-4`, así que el merge es un avance directo. Hash para volver atrás: `9f64780`.

Merge y reinicio:

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

Volver atrás, si hiciera falta:

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard 9f64780 && sudo systemctl start sebastian.service`

## Decisiones que necesito

Ninguna.
