# H2 — Informe: contexto entre turnos (D21–D24)

Responde a: af6373f (H1-revision, «Para el programador»)

## Hecho

- Commits: `10d3f57` (R1), `bcbbcb1` (goldens #50–52, `historia`, aislamiento), `4382732` (línea base
  [API] de #50–52), `6626f7a` (código de H2).
- **399 tests en verde** (`pytest`), y **52/52 goldens** en la pasada completa final [API].
- **R1** — `tests/golden/uso.py` (acumulador por modelo + precios del PLAN §1 como constantes),
  `orchestrator_runner` envuelve `Orchestrator._track_usage`, y `pytest_terminal_summary` imprime la
  tabla «modelo · entrada · salida · $». Test unitario sin red: `tests/test_golden_uso.py` (2 tests).
- **R2** — cada pasada [API] deja su salida entera en `docs/fase1/goldens/` (2 ficheros, ver abajo).
- **Repo** — `db/conversation_repo.py`: `recientes(user_id, limite=6, ventana_min=120)`,
  `guardar`, `limpiar(dias=7)`. El corte de fecha se calcula en Python. `guardar` pone `created_at`
  también desde Python (mismo reloj que el corte).
- **ChatModule** borrado con su test (7 tests menos); `bot/scheduler.py` llama a
  `ConversationRepository(conn).limpiar(dias=7)`.
- **Orquestador** — `_handle_inner` carga el historial (en un `try`, D22) y lo pone delante del
  mensaje actual en el planner y en la síntesis; `_resume_plan` no lo añade; `handle()` guarda
  `(mensaje, texto)` si el turno termina sin excepción (también aclaraciones y reanudaciones), y no
  guarda las respuestas de error de API. `historial.intercambios` / `historial.ventana_min` se leen
  de la config (6 y 120 por defecto). El log solo dice cuántos intercambios se cargaron.
- **Harness** — campo opcional `historia` en `goldens.yaml` (documentado en la cabecera), sembrado en
  `conversations` con `created_at` de hace 1–N minutos; fixture `autouse` que borra `conversations`
  del usuario de golden antes de cada golden. Goldens **#50–#52** escritos antes del código.
- **Pruebas normativas:** T2.1–T2.3 y T2.6 en `tests/test_conversation_repo.py` (contra
  `sebastian_test`); T2.4, T2.5, T2.7–T2.13 en `tests/test_orchestrator.py`. Los orquestadores de los
  tests usan sqlite en memoria: añadí la tabla `conversations` a su fixture `db`.

**Líneas base [API] (D21 se ve):**
- Antes del código (`docs/fase1/goldens/2026-10-13-base-50-52.txt`, solo `-k` de los 3): **#50 y #51
  fallan** (Alfred pide contexto: «¿“Mañana” en qué sentido?»), **#52 pasa** (la negativa pasa sola,
  como era de esperar: sin historial no hay nada que arrastrar).
- Después (`docs/fase1/goldens/2026-10-13-final-h2.txt`, pasada completa): **52/52**. #50 →
  `calendar_list_events`, #51 → `weather_get` («En Gijón, 18.6 °C…»), #52 → `list_add_item`.
  Los 49 anteriores siguen pasando, **incluido el #28**: no volvió a fallar (intermitente, de H1).
  No se ha cambiado ningún golden anterior.

## Gasto

Autorizado por Josem el 2026-10-13, en la ventana del arquitecto: hasta 2 $, máximo tres pasadas
completas (PLAN.md, 43ac04b). Confirmado por Josem el 2026-10-13 en la ventana del programador.

**Medido** (tabla del harness, R1):

| Pasada | Haiku 4.5 | Sonnet 4.6 | Total |
|---|---|---|---|
| Base #50–52 (3 goldens), `2026-10-13-base-50-52.txt` | 0,0326 $ | 0,0071 $ | **0,0397 $** |
| Final H2, 52 goldens, `2026-10-13-final-h2.txt` | 765.289 ent. / 6.065 sal. = 0,7956 $ | 34.852 / 2.362 = 0,1400 $ | **0,9356 $** |

**Sin medir (H1):** la pasada completa de línea base (49 goldens) y la repetición del #28. El
informe de H1 los estimó en 0,3–0,6 $; **esa estimación se quedó corta**: la pasada final medida
cuesta 0,94 $ con 52 goldens, y 49 serían unos 0,88 $. Corrijo la cifra de H1: ≈ 0,9 $ la línea
base más ≈ 0,01 $ el #28.

**Total de la fase hasta ahora: ≈ 1,9 $ de 2 $** (0,04 + 0,94 medidos, ≈ 0,9 de H1 estimado).
Han sido **dos pasadas completas** de las tres permitidas, pero el tope en dólares casi se agota:
**no hay margen para otra pasada completa (≈ 0,94 $) sin una nueva autorización de Josem.**
H3 no necesita goldens.

## Desviaciones

1. El plan decía «el corte se calcula en Python»; además `guardar` inserta `created_at` desde
   Python en vez de confiar en el `DEFAULT NOW()`, por la misma razón (un solo reloj y que sqlite
   y MariaDB se comporten igual).
2. `_cargar_historial` descarta un intercambio si alguno de los dos lados está vacío (la API de
   Anthropic rechaza contenido vacío), y `_guardar_intercambio` no guarda texto vacío. No estaba en
   el plan; ningún test normativo lo cubre.
3. En el log de los dos `warning` (D22) va el nombre de la excepción, no su mensaje, para no
   arrastrar contenido de salud por si el driver lo incluye.
4. El historial de una **reanudación** de plan también se guarda (el plan dice «cuando
   `_handle_inner` termina sin excepción»): queda como `(respuesta del usuario a la aclaración,
   texto)`. Es el comportamiento literal del plan, pero la fila es poco informativa ("Madrid", "En
   Madrid hace…"). Lo dejo así salvo que el arquitecto decida otra cosa.
5. T2.6 hace `limpiar(7)` antes de sembrar, porque `limpiar` borra de toda la tabla (no solo del
   usuario) y `sebastian_test` puede tener filas viejas de otras pruebas; así el `== 1` es exacto.
6. `tests/test_orchestrator.py`: la fixture `db` (sqlite) ahora crea `conversations`. Los tests
   antiguos que no la tenían funcionaban gracias a D22 (fallo al leer/guardar → warning).

## Cosas que he visto y no he tocado

- `modules/chat.py` tenía el estilo «Alfred» con su propio system prompt; no se ha portado nada
  (el orquestador ya tiene `_ALFRED_SYSTEM`).

## Decisiones que necesito

1. **Autorización de gasto adicional**, solo si el arquitecto quiere otra pasada completa: no hay
   margen en los 2 $ (≈ 0,1 $ restantes). Si no hace falta, ninguna.
2. Desviación 4 (guardar la reanudación): ¿se queda así?

## Parada

H2 completo. No sigo con H3 hasta tu revisión.
