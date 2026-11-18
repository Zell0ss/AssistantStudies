# H8 — informe (fase 3, parche): el planner cachea sus herramientas

> Responde a: d6abff1 (H8-encargo). Programador, 2026-11-19. Rama `fase-3`, commit `c4fa88a` (R20 y R21). Sin migración. No he
> fusionado, reiniciado ni tocado producción. `main` está en `c543917`, antecesor de `fase-3`: el `ff-only` es posible.

## Hecho

- **R20 (D59).** `_PLANNER_TOOLS` en `core/orchestrator.py`: copia de `ALL_TOOLS` en la que solo el último dict lleva
  `"cache_control": {"type": "ephemeral"}` (TTL de 5 min, sin `ttl`). `_llamar_planner` pasa `tools=_PLANNER_TOOLS`; no toqué el
  `system`, los `messages`, `_PLANNER_EXTRA`, `_is_plan_reply`, Alfred ni el extractor. `ALL_TOOLS` no se muta (se copia el último dict).
  `D59` citado junto a la constante.
- **R21 (D59).** `_track_usage` acumula `cache_read` y `cache_creation` (`getattr(..., 0) or 0`). La línea `Turn end` los lleva como
  campos de `bind` y en el texto (`cache_read=… | cache_creation=…`); `tokens_in` sigue siendo solo `input_tokens`. Para no repetir el
  diccionario de contadores en tres sitios añadí `_uso_vacio()` (lo usan `__init__` y `_handle_inner`).
- **Pruebas sin API:** 7 nuevas en `tests/test_orchestrator.py`, las cuatro de R20 y las tres de R21 del encargo. Vi fallar 5 antes
  del código; las otras 2 (`ALL_TOOLS` no se muta, tools idénticas entre llamadas) son guardas de no regresión y pasaban ya.
  **907 pasan** en total (antes 900).

## Resultados [API]

**Paso 3.1, recuento con `messages.count_tokens` (no se factura).** Restando el coste del mensaje base («hola», 9 tokens):

| Pieza | Modelo | Tokens |
|---|---|---|
| `ALL_TOOLS` (42 tools; igual con el marcador) | Haiku 4.5 | **10 560** |
| `system` del planner | Haiku 4.5 | 1 227 (**sin índice de memoria**: ver nota) |
| `_ALFRED_SYSTEM` | Sonnet 4.6 | 1 416 |
| Prompt del extractor + `TOOL_REGISTRAR_HECHOS` (catálogo vacío) | Haiku 4.5 | 2 008 |

Las tools son ~10,5 mil tokens, no ~7000 como estimaba el encargo por los bytes. Nota: el usuario de pruebas (`golden_test_user`) no tiene
índice de memoria, así que el `system` del planner en uso real será mayor que 1227; no lo medí con un índice típico. Ninguna de las otras
tres piezas llega por sí sola a 4096 tokens (el mínimo de Haiku 4.5 del encargo); para Sonnet no comprobé su mínimo.

**Paso 3.2, dos turnos reales de solo lectura** (BD `sebastian_test`, 2026-11-19 00:55–00:56, en menos de 10 s), uso por llamada:

| Turno | Llamada | Modelo | `input` | `output` | `cache_creation` | `cache_read` |
|---|---|---|---|---|---|---|
| «¿Qué tiempo hace mañana en Madrid?» | 1 (planner) | Haiku 4.5 | 1569 | 63 | **10240** | 0 |
| | 2 (planner) | Haiku 4.5 | 1711 | 21 | 0 | **10240** |
| | Alfred | Sonnet 4.6 | 1646 | 77 | 0 | 0 |
| «¿Y en Gijón?» | 1 (planner) | Haiku 4.5 | 1659 | 76 | 0 | **10240** |
| | 2 (planner) | Haiku 4.5 | 1819 | 50 | 0 | **10240** |
| | Alfred | Sonnet 4.6 | 1740 | 58 | 0 | 0 |

Lo esperado se cumple: la primera llamada escribe la caché y las otras tres la leen, también al cambiar de turno (la hora del `system`
cambia en cada llamada y no la invalida, como decía el encargo). El `turn_usage` acumulado coincide con la suma de las llamadas
(turno 1: `cache_read=10240`, `cache_creation=10240`, `tokens_in=4926`; turno 2: `cache_read=20480`, `cache_creation=0`,
`tokens_in=5218`). Una observación sin explicar: la caché es de **10240** tokens y el recuento de las tools es 10560; los ~320 de
diferencia salen en `input_tokens`. No lo investigué.

**Gasto (precios del 2026-11-16: Haiku 4.5 1/5 $, escritura de caché ×1,25, lectura ×0,1; Sonnet 4.6 3/15 $ por millón):**

| Modelo | Coste |
|---|---|
| Haiku 4.5 (4 llamadas del planner) | 0,0237 $ |
| Sonnet 4.6 (2 llamadas de Alfred) | 0,0122 $ |
| **Total H8** | **≈ 0,036 $** (tope 0,30 $) |

El paso 3.1 no se factura. Sin caché, esas 4 llamadas del planner habrían leído 40 960 tokens de entrada más a precio completo
(≈ 0,041 $ contra ≈ 0,016 $ con caché por la parte de las tools). La escritura se amortiza a partir de la segunda llamada dentro de 5 minutos.

**Gasto de la fase 3: ≈ 10,57 $ de 11,50 $.** Autorizado por Josem el 2026-11-19, en mi ventana: «Si» a los pasos 3.1 y 3.2 a la vez (le
había preguntado por los dos, o solo por el primero). El tope de 11,50 $ lo fijó Josem y consta en el encargo.

## Desviaciones

- **BD:** el encargo pide «la BD de desarrollo del `.env`». El `config.yaml` de este worktree apunta a `sebastian_test` y usé esa
  (con `SEBASTIAN_DB_NAME=sebastian_test` y un `assert` en el guion), nunca producción. Los dos turnos dejaron dos intercambios en
  `conversations` de `golden_test_user`.
- **`_uso_vacio()`** (arriba): una función que no pedía el encargo, para no tener el diccionario de contadores en tres sitios.
- Los guiones de §3 están en el scratchpad de la sesión, sin commit: `…/scratchpad/h8_recuento.py` y `…/h8_comprobacion.py` (se ejecutan
  desde `sebastian2/` con `PYTHONPATH=.`).

## Decisiones que necesito

Ninguna. Tres datos por si sirven para lo que viene fuera de H8: (1) `_ALFRED_SYSTEM` (1416 tokens) y el extractor (2008) están por
debajo de 4096; si el mínimo de Sonnet 4.6 es 2048, tampoco llegaría Alfred (no lo he comprobado). (2) El `system` del planner con índice
real no está medido. (3) Alfred no cachea nada hoy y cada turno lo llama una vez.

**Despliegue** (de Josem, tras tu revisión; no hay migración):

```bash
cd /data/AssistantStudies && git status        # debe estar limpio y en main
git rev-parse HEAD                              # APUNTA este hash: es la vuelta atrás (hoy c543917)
git merge --ff-only fase-3
sudo systemctl restart sebastian.service
bash /data/AssistantStudies/sebastian2/deploy/comprobar_fase3.sh      # debe terminar con «Todo bien.»
```

Vuelta atrás: `sudo systemctl stop sebastian.service; cd /data/AssistantStudies && git reset --hard <el hash apuntado>; sudo systemctl
start sebastian.service`. Comprobación en producción, sin gasto extra: tras dos mensajes seguidos por Telegram, `logcentral query --source
sebastian` tiene que mostrar en `Turn end` `cache_read=` distinto de 0 (≈ 10240) a partir de la segunda llamada al planner en 5 minutos.
