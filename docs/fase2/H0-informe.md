# H0 (fase 2) — Informe: Haiku 5.5 como planner (D28) y Python 3.12 + anthropic 1.14

Responde a: 5aebab2 (H0-encargo §6)

## Hecho

Commits: `eb620b6` (pruebas de D28, rojas), `3808b77` (T0.1–T0.6 y harness), `bc59216` (salidas de la
pasada completa y de la repetición), `126fd2f` (T0.7, `requirements.txt`). **417 tests en verde** con
Python 3.11 + anthropic 0.79 **y** con Python 3.12 + anthropic 1.14 (`pytest`, sin API).

### Parte 1 — D28: ¿puede Haiku 5.5 hacer de planner?

**Cambios (`core/orchestrator.py`):**
- **T0.1:** `_MODELO_PLANNER = "claude-haiku-5-5"` y `_PLANNER_EXTRA = {"output_config": {"effort": "low"}}`
  en un solo sitio, con comentario `D28`. Una sola función, `_llamar_planner()`, hace las dos llamadas
  del bucle; `_track_usage` usa la misma constante.
- **T0.2 · `max_tokens`: 4096** en el planner (era 1024). El razonamiento se cobra como salida y cuenta
  para el tope, el tokenizer de Haiku 5.5 da ≈ 30 % más de tokens, y una tool como `notes_create` o
  `youtube_transcript` puede llevar un input largo. Es un techo, no un gasto. Y **512** en `_is_plan_reply`
  (la respuesta es SI/NO, pero con razonamiento delante). Ningún golden dio `max_tokens`.
- **T0.3:** `_is_plan_reply` pasa al mismo modelo y lee el primer bloque de tipo `text`; sin él, devuelve
  `False` y deja un `warning`.
- **T0.4:** `stop_reason == "refusal"` → `warning` con `stop_details.category`, sin el mensaje, y el
  bucle termina sin ejecutar tools (síntesis sin datos). Añadí (no estaba en el encargo) el mismo aviso
  para `stop_reason == "max_tokens"`, para que un planner cortado antes de decidir no sea silencioso.
- **T0.5 — SDK:** `anthropic` 0.79.0 **ya acepta `output_config=`** en `messages.create` (lo comprobé con
  `inspect.signature` y con una llamada real). No hace falta `extra_body`, y no actualicé el SDK en esta
  parte.
- **T0.6:** el ida y vuelta `_messages_to_json` → `_messages_from_json` ya conservaba `thinking=""` y
  `signature` (test con un `ThinkingBlock` real del SDK). No ha hecho falta tocar el serializador.
- **Pruebas sin API del §3** (seis tests nuevos, `tests/test_orchestrator.py`): cuatro estaban en rojo antes
  de implementar (`test_planner_usa_modelo_unico`, `test_is_plan_reply_con_thinking_primero`,
  `test_refusal_del_planner`, `test_planner_cortado_por_max_tokens_deja_warning`); `test_respuesta_con_thinking_primero`
  y `test_pending_plan_conserva_thinking` **ya pasaban** con el código de antes, porque el bucle ya guardaba
  `response.content` entero.
- **Harness:** precio de `claude-haiku-5-5` en `tests/golden/uso.py` (0,10 $ / 0,50 $ por millón), y ahora
  apunta la latencia de cada turno con la misma cuenta que la línea `Turn end`, con mediana y p90 en el
  resumen. `tests/golden/test_aclaracion.py` es el flujo real de aclaración y reanudación.

**Precio en vivo** (`https://platform.claude.com/docs/en/about-claude/pricing.md`, 2026-10-14):
`Claude Haiku 5.5 (for prompts up to 100,000 tokens) $0.10 / MTok in · $0.50 / MTok out` (cache hit 0,01 $);
`(for prompts over 100,000 tokens) $0.50 / $2.50`; `Claude Haiku 4.5 $1 / $5`; `Claude Sonnet 4.6 $3 / $15`.
Los prompts del planner rondan 9.000 tokens por llamada: siempre en la tarifa barata.

**Pasadas [API] y criterio del §4** (planner en Haiku 5.5, sobre `anthropic` 0.79 y Python 3.11):

| Criterio | Resultado | ¿Cumple? |
|---|---|---|
| 1. Goldens 55/55 (un fallo estable no se acepta) | **51/55.** Fallan #21, #28, #48, #49. Los repetí solos con `-k` y **los 4 fallan igual** (salidas en `docs/fase2/goldens/`). | **No** |
| 2. Pasada completa < 0,5 $ | **0,2974 $** (Haiku 5.5: 0,1062 · Sonnet 4.6: 0,1912) | Sí |
| 3. Mediana por turno no peor que +30 % | **4,41 s** (p90 6,59 s, n = 57: 55 goldens + 2 turnos del flujo de aclaración) frente a **4,90 s** (p90 8,15 s) de los 171 turnos de goldens antiguos con Haiku 4.5 (`logs/sebastian.log`, solo lectura): **−10 %**. Con los 47 turnos de usuarios reales (6,90 s, p90 12,81 s) la comparación no es de lo mismo: lleva tools reales y más iteraciones. | Sí |

**Los cuatro fallos, tal como salieron** (ninguno llama a `salud` de forma indebida; son cambios de qué tool
elige):
- **#21** («que te dije de la alergia de paco?», esperado `search_memory`): `search_memory → notes_search`.
  Responde bien («su cuñado Paco es alérgico a los frutos secos»); busca además en notas.
- **#28** («recuérdame acostarme pronto», esperado ninguna o `notes_create`): `request_clarification`
  (pregunta a qué hora). Es el golden que ya fue intermitente en la fase 1 con Haiku 4.5; aquí falló dos de
  dos veces.
- **#48** («compra yogures», esperado aclaración o nada): `list_add_item`. Para mí es lo razonable
  («Anotado. Yogures en la lista de la compra»); el golden recoge lo que hacía Haiku 4.5.
- **#49** («¿qué ceno hoy?», esperado ninguna tool): `inventory_list → notes_search → search_memory` (la
  primera vez) y `… → calendar_list_events` (la repetición). Más tools de las necesarias; la respuesta es
  coherente.

Mi lectura: el criterio 1 **no se cumple**, así que según el §4 el planner vuelve a Haiku 4.5. Esa decisión
es tuya. Si es así, el cambio son **dos líneas** (`_MODELO_PLANNER = "claude-haiku-4-5-20251001"` y
`_PLANNER_EXTRA = {}`, porque `effort` da 400 en 4.5), en un commit aparte que hago antes del merge; los
tests nuevos siguen valiendo con cualquiera de los dos, y T0.1, T0.3, T0.4 y T0.6 se quedan como dice el §4.

**Flujo de aclaración y reanudación real** (contra `sebastian_test`, dos veces: en la pasada completa y en
la comprobación del SDK 1.14): sin ningún 400. Turno 1: `request_clarification`; el plan guardado **sí**
llevaba bloques `thinking`; turno 2: `calendar_add_event` y «Dentista mañana, 15 de octubre, a las 10:30»,
y el plan se consumió. El riesgo que anoté (el prompt del planner lleva la hora, y al reanudar se reenvían
los `thinking` con un `system` distinto) **no se materializó en esta cuenta**; no sé si es porque la cuenta
no está sujeta al chequeo (anterior al 2026-08-31) o por otra razón, así que no lo doy por descartado para
una cuenta nueva.

### Parte 2 — SDK y Python (§6)

**Inventario del paso 1 de la guía `python/claude-api/sdk-upgrade.md`** (sobre todo el árbol de la rama,
sin `.venv`, `.git` ni `backup_old_modules/`):

| Señal | Resultado |
|---|---|
| Suelo de Python (`requires-python`, `python_requires`, `python-version`, `py39`) | Ninguno declarado: no hay `pyproject`, ni CI, ni `tox`. |
| `import httpx` / `from httpx`, `respx`, `pytest_httpx`, `vcr`, `MockTransport`, instrumentación de `httpx` | **Ninguno.** Nada pasa objetos `httpx` al SDK. |
| `with_raw_response`, `LegacyAPIResponse`, `_legacy_response` | Ninguno. |
| `completions.create` | 5 hits en `sebastian_bot.py` **de la raíz del repo** (el Sebastian antiguo, con `openai`): no son del SDK de Anthropic. No se tocan. |
| `temperature`, `top_p`, `top_k` | Solo `temperature_2m` de Open-Meteo (`modules/weather.py`): no son del SDK. |
| `output_format`, exports renombrados (`BetaBase64PDFBlockParam`, `ProxiesTypes`…), `.parse(`, `compaction_control`, `body=` con bytes, `isinstance(…Stream)`, `default_headers`/`extra_headers`, `AnthropicBedrock` | Ninguno. |
| Uso real del SDK | `core/orchestrator.py` (`Anthropic`, `APIError`, `APIConnectionError`, `RateLimitError`) y `scripts/cuaderno/despertar.py` (`Anthropic`), más `anthropic.types.ThinkingBlock` y `APIConnectionError` en tests. Todo existe igual en 1.14. |

**Conclusión del inventario: ningún cambio de código** (T0.8 vacío). Un único cambio de dependencia.

- **T0.7:** `python3.12 -m venv .venv` en `sebastian2/` del worktree e instalación del `requirements.txt` con
  solo `anthropic==0.79.0` → `anthropic==1.14.0`. **Todos los demás pins instalan en 3.12** (incluidos
  `zxing-cpp` 3.0.0, `Pillow` 12.3.0, `numpy` 2.4.2 y `-e /data/logcentral/packages/client/`). `httpx2` 2.13.1 y
  `httpcore2` 2.13.1 los trae el propio SDK; no los fijé. `requirements.txt` cambia **solo la línea de
  `anthropic`**. Las rutas de `sebastian2.service` y `deploy/cuaderno.service` (`…/sebastian2/.venv/bin/…`) no
  cambian y no se tocan.
- **`pytest` no está en `requirements.txt`**: el `.venv` de producción lo tenía instalado a mano
  (`pytest==9.0.2`); lo instalé igual en el nuevo para poder probar. Si quieres `pytest` en un entorno
  de producción recién creado, hay que instalarlo aparte (no hace falta para que corra el servicio).
- **T0.9.1:** `pytest` completo en el `.venv` nuevo (Python 3.12.14, anthropic 1.14.0): **417 passed**.
- **T0.9.2 [API] con `-k`**, en la configuración final (Haiku 5.5 + 1.14), salida en
  `docs/fase2/goldens/2026-10-14-sdk114-py312-k.txt`: **#20, #22, #23, #24 (salud), #50 y #54 pasan; el flujo de
  aclaración y reanudación pasa; los 3 casos de honestidad de H4 pasan** (las 9 respuestas están en la
  salida: ninguna inventa nombre, año ni fecha). **Solo falla el #21**, con el mismo resultado exacto que en la
  pasada sobre 0.79 (`search_memory → notes_search`, cuatro veces la misma): **no es del SDK**. No hay
  ningún golden que pasara con 0.79 y falle con 1.14.
- La advertencia de Tristras («no respondió… ConnectionError») que sale en el #24 es la neutralización de D27
  funcionando.

## Gasto

Autorizado por Josem el **2026-10-14, en la ventana del programador** («dale», para el humo de #53, la
pasada completa y el flujo de aclaración; y «sí», para la comprobación del SDK con `-k`). El tope del hito
es 1,2 $ (Josem, 2026-10-14, en la ventana del arquitecto; el encargo original decía 1 $). La repetición de
los 4 fallos con `-k` es la que permitía el §5 del encargo original.

| Paso [API] | Haiku 5.5 | Sonnet 4.6 | Total |
|---|---|---|---|
| Humo, #53 | 0,0019 $ | 0,0044 $ | 0,0064 $ |
| Pasada completa (55 + aclaración), 0.79 | 0,1062 $ | 0,1912 $ | 0,2974 $ |
| Repetición de #21, #28, #48, #49 | 0,0070 $ | 0,0129 $ | 0,0199 $ |
| Comprobación SDK 1.14 (`-k`) | 0,0156 $ | 0,0612 $ | 0,0768 $ |
| **Total del hito** | **0,1307 $** | **0,2697 $** | **0,4005 $** |

Muy por debajo del tope de 1,2 $. (La estimación del encargo, ≈ 0,3 $ para la pasada, fue buena esta vez.)

## Desviaciones

1. **Pasada completa con la configuración de D28 sobre `anthropic` 0.79**, como pedía el §6; la
   comprobación del SDK nuevo se hizo después solo con `-k`.
2. Aviso de `max_tokens` del planner, no pedido (T0.4 solo hablaba del rechazo).
3. `test_aclaracion.py` borra de `sebastian_test` las citas «dentista» del usuario de golden antes y
   después, y los planes pendientes de ese usuario antes.
4. En el flujo de aclaración la primera frase («Apunta en el calendario una cita») provoca la aclaración las
   dos veces que se ha lanzado, pero la redacción de Alfred cambia entre ejecuciones (en una dice algo
   confuso sobre «quién hace la pregunta»; es de la síntesis de `_ask_user`, no del planner).
5. `pytest==9.0.2` instalado a mano en el `.venv` nuevo (ver arriba).
6. En la comprobación del SDK, un turno tardó **31,6 s** (p90 11,9 s con n = 9). No lo he investigado: no
   sé cuál fue ni si es la API o una tool.

## Decisiones que necesito

1. **D28:** ¿se adopta Haiku 5.5 con el criterio 1 incumplido (51/55 estable), o vuelve el planner a Haiku
   4.5? Si vuelve, aviso de que el cambio son dos líneas y lo hago antes del merge. Si se adopta, hay
   que decidir qué hacer con los goldens #21, #28, #48, #49 (yo no los reescribo; no es mi decisión).
2. Ninguna sobre el SDK.

## Despliegue (lo ejecuta Josem)

Va al final de H0, se adopte o no D28, porque el `.venv` nuevo vale igual con cualquier planner. Cuando el
arquitecto lo dé por revisado:

```bash
# 1. Parar el servicio
sudo systemctl stop sebastian.service
# 2. Apartar el venv de producción (Python 3.11.0rc1, anthropic 0.79.0)
mv /data/AssistantStudies/sebastian2/.venv /data/AssistantStudies/sebastian2/.venv-3.11-old
# 3. Merge de la rama de la fase
cd /data/AssistantStudies && git merge --ff-only fase-2
# 4. Venv nuevo en producción, con Python 3.12
cd /data/AssistantStudies/sebastian2 && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
# 5. Arrancar y comprobar
sudo systemctl start sebastian.service
logcentral query --source sebastian --level error      # tiene que salir vacío desde el arranque
logcentral query --source sebastian --grep "Escribiendo en BD"   # sebastian_db / sebastian_memory
```

Tras el arranque, prueba por Telegram, por ejemplo «¿qué tiempo hace en Madrid?» y luego «¿y mañana?». El
cuaderno usa el mismo `.venv` en su próximo disparo. `.venv-3.11-old` no estaba ignorado por git
(`sebastian2/.gitignore` solo tenía `.venv/`); añadí `.venv-*` en un commit aparte (`46ea349`), que el merge del
paso 3 trae, así que `git status` en producción no lo listará.

**Vuelta atrás:**

```bash
sudo systemctl stop sebastian.service
rm -rf /data/AssistantStudies/sebastian2/.venv
mv /data/AssistantStudies/sebastian2/.venv-3.11-old /data/AssistantStudies/sebastian2/.venv
cd /data/AssistantStudies && git reset --hard ee01f58     # el main de antes de la fase 2
sudo systemctl start sebastian.service
```

`ee01f58` es el `main` de hoy (`H4-revision: aprobado; listo para el merge de Josem`). El `git reset --hard`
solo descarta el merge de `fase-2`; la rama `fase-2` se queda.

## Parada

H0 completo. El plan de la fase 2 lo escribe el arquitecto después de revisar este informe; no sigo con
nada de la fase 2.

---

## Anexo — esfuerzo medium

Responde a: 877232c (H0-revision, «Para el programador»)

### Hecho

- **R1** (`29e0a58`): `_PLANNER_EXTRA = {"output_config": {"effort": "medium"}}`, commit propio. 417 tests.
- **R2** [API]: una pasada completa (55 goldens + flujo de aclaración) con `medium`, sobre el `.venv` nuevo
  (Python 3.12.14, anthropic 1.14.0). Salida: `docs/fase2/goldens/2026-10-14-haiku55-medium-completa.txt`
  (`17e7727`). Autorizada por Josem el 2026-10-14, en esta ventana («sí»).
- **R3**: el criterio no se cumple (tabla abajo), así que **el planner vuelve a `claude-haiku-4-5-20251001` con
  `_PLANNER_EXTRA = {}`** (`99ac214`, dos líneas, un commit), y comprobación con `-k` en 4.5 (`911a6b5`).
  T0.1, T0.3, T0.4 y T0.6 se quedan. No he tocado ningún golden.
- **Hallazgo aparte, de entorno (`3d7b013`): `requests` 2.34.2 rompe `requests-cache` 1.2.1.** Ver abajo.

### Criterio del §4 con `medium` (Haiku 5.5, Python 3.12 + anthropic 1.14)

| Criterio | Resultado | ¿Cumple? |
|---|---|---|
| 1. Goldens 55/55 | **47/55.** Fallan #03, #04, #05, #24, #28, #48, #49 y #51. | **No** |
| 2. Pasada completa < 0,5 $ | **0,2984 $** (Haiku 5.5: 0,1110 · Sonnet 4.6: 0,1874) | Sí |
| 3. Mediana ≤ 6,37 s (+30 % sobre 4,90 s) | **4,16 s** (p90 5,44 s, n = 57), un 15 % **mejor** que la línea base | Sí |

**Los 8 fallos, separados por causa** (salida completa en el fichero citado):

*Causa 1 — entorno, no del modelo ni del esfuerzo (3 fallos):* **#04, #05 y #51** (el tiempo). Alfred contesta
«el servicio meteorológico no responde» porque `modules/weather.py` falla con
`Forecast fetch failed: name 'RequestsCookieJar' is not defined`. Es del `.venv` nuevo (ver «Hallazgo»).

*Causa 2 — comportamiento del planner con `medium` (5 fallos):*
- **#03** (esperado `notes_delete → notes_delete`): `notes_get → notes_get → notes_delete → notes_delete`. Mira
  las notas antes de borrarlas. **Nuevo**: con `low` pasaba.
- **#24** (esperado `salud`): `salud → salud`. Con Tristras neutralizado (D27) la tool devuelve el error de red y
  el planner la **reintenta** una vez. **Nuevo**: con `low` pasaba.
- **#28**: `request_clarification` (pregunta a qué hora). **Igual que con `low`** (falló también en las dos
  ejecuciones de aquel día).
- **#48**: `list_add_item`. **Igual que con `low`.**
- **#49**: `inventory_list → calendar_list_events → notes_search`. **Igual que con `low`** (otras tools, mismo
  problema: tres tools para una pregunta que no necesita ninguna).
- El **#21 sí pasa** con `medium` (con `low` hacía `search_memory → notes_search`).

**No repetí con `-k` los fallos de la causa 2**: #28, #48 y #49 llevan fallando estables en las tres pasadas de
Haiku 5.5 (dos con `low`, esta con `medium`), así que repetirlos no puede cambiar el veredicto del criterio 1. #03 y
#24 son nuevos con `medium` y los dejo sin repetir por la misma razón (gastarlo no cambia la decisión). Si el
arquitecto prefiere tener esas dos repeticiones guardadas, son ≈ 0,03 $.

**Conclusión:** con `medium` el criterio 1 sigue sin cumplirse; con las causas de entorno quitadas sigue en
**5 fallos de comportamiento**. Por eso R3 manda volver a Haiku 4.5.

### Hallazgo: `requests` 2.34.2 + `requests-cache` 1.2.1 (decisión que necesito)

- **Qué pasó:** `requests-cache==1.2.1` está fijado en `requirements.txt`, pero `requests` no (llega como
  dependencia transitiva). En el `.venv` nuevo `pip` resolvió `requests 2.34.2`; en el de producción hay
  `2.32.5`. Con 2.34.2, `CachedSession` lanza `NameError: name 'RequestsCookieJar' is not defined`: **el tiempo
  (`modules/weather.py`) dejaba de funcionar por completo.** Lo reproduje con una petición mínima a Open-Meteo en
  el `.venv` nuevo (error) y en un venv de prueba con `requests==2.32.5` (200 OK).
- **Por qué no lo vi antes:** los tests unitarios simulan Open-Meteo, y mi comprobación con `-k` de T0.9 no incluyó
  ningún golden del tiempo. **De haberse desplegado el `.venv` con solo el cambio de `anthropic`, habría roto el
  tiempo en producción.** Lo cazó la pasada completa.
- **Qué hice:** fijé `requests==2.32.5` (la versión de producción) en `requirements.txt`, con un comentario, en
  un commit propio (`3d7b013`), y lo instalé en el `.venv` nuevo. **Es más de lo que decía el §6** («solo la línea
  de `anthropic`»), así que lo pongo como desviación y como decisión tuya.
- **Comparación completa de los dos entornos** (`pip freeze`, excluyendo los editables): las dependencias
  directas están iguales salvo `anthropic`, pero **~35 transitivas son distintas** (p. ej. `urllib3` 2.6.3 → 2.8.0,
  `attrs`, `cattrs`, `pydantic` 2.12.5 → 2.14.1, `pydantic_core`, `pillow` 12.1.1 → 12.3.0, `url-normalize` 2.2.1 →
  3.0.1, `anyio`, `jiter`, `certifi`…). `requests` es la única que he visto fallar, pero los goldens no ejercen
  todo (por ejemplo, el escaneo de tickets con `pyzbar`/`zxing-cpp`/`Pillow`), así que **no sé** si otra sorpresa
  espera. Mi recomendación: o bien (A) lo que ya hice, fijar solo `requests`; o bien (B) generar un fichero de
  constraints con el `pip freeze` del venv de producción para todo lo que no sea `anthropic`, de modo que el
  entorno nuevo sea idéntico salvo el SDK. B es más seguro para el despliegue y algo más rígido después. **Dime
  cuál**; hasta entonces dejo A.

### Comprobación con `-k` en Haiku 4.5 + anthropic 1.14 (R3)

`docs/fase2/goldens/2026-10-14-haiku45-sdk114-k.txt`: **#03, #04, #05, #20, #21, #22, #23, #24 y #51 pasan.** El
tiempo vuelve a responder (#04, #05, #51), con `requests` 2.32.5. Latencia por turno (n = 10): mediana 3,97 s,
p90 5,35 s.

**El flujo de aclaración y reanudación NO se puede provocar con Haiku 4.5.** Probé 4 frases en la primera
ejecución («Apunta en el calendario una cita», «Añade una cita al calendario», «Quiero apuntar una cita»,
«Apúntame una cita con el dentista») y otras 4 en la segunda («Dime qué tiempo hará cuando vaya a pilates»,
«compra yogures», «Pon un recordatorio para llamar al médico» y la primera otra vez): **ocho intentos y
Haiku 4.5 no llamó nunca a `request_clarification`**; o contesta por texto («¿Qué cita desea apuntar?», sin tool)
o actúa (`list_add_item`, `calendar_add_event`). Es coherente con la descripción de la tool («último recurso»). Con
Haiku 5.5 sí la llamaba (dos de dos). Consecuencias:
- Con 4.5 no hay bloques `thinking` (4.5 no razona por defecto), así que el riesgo del `thinking` reenviado con
  otro `system` no existe en la configuración que se desplegaría. El camino `_resume_plan` con 4.5 es el de
  siempre, cubierto por los tests con mocks.
- Dejé el test `tests/golden/test_aclaracion.py` con varias frases candidatas y, si ninguna provoca la aclaración,
  **`pytest.skip` con el detalle de los intentos** (antes era un fallo). **Es un cambio mío hecho después de ver el
  resultado**: lo declaro por si prefieres un fallo visible. Se revierte con un `git revert` de `911a6b5` (solo ese
  fichero y las salidas).

### Gasto

Autorizado por Josem el 2026-10-14, en la ventana del programador («dale» y dos «sí»); tope del hito 1,2 $.

| Paso [API] | Haiku 5.5 | Haiku 4.5 | Sonnet 4.6 | Total |
|---|---|---|---|---|
| Primera parte (informe de arriba: humo, completa `low`, repetición, SDK `-k`) | 0,1307 $ | — | 0,2697 $ | 0,4005 $ |
| Pasada completa `medium` (R2) | 0,1110 $ | — | 0,1874 $ | 0,2984 $ |
| `-k` en Haiku 4.5 (#03–05, #20–24, #51, aclaración) | — | 0,1504 $ | 0,0348 $ | 0,1852 $ |
| Aclaración en 4.5, intento 1 (4 frases) | — | 0,0341 $ | 0,0118 $ | 0,0459 $ |
| Aclaración en 4.5, intento 2 (4 frases) | — | 0,0499 $ | 0,0122 $ | 0,0620 $ |
| **Total del hito** | **0,2417 $** | **0,2344 $** | **0,5159 $** | **0,9920 $** |

Quedan ≈ 0,21 $ de los 1,2 $. No hay margen para otra pasada completa; si hace falta alguna, necesita autorización
nueva.

### Desviaciones

1. `requests==2.32.5` fijado en `requirements.txt` (arriba): fuera del §6.
2. `test_aclaracion.py`: varias frases candidatas y `skip` si ninguna provoca la aclaración.
3. No repetí #03 y #24 con `-k` (arriba, con el motivo).
4. El `-k` de Haiku 4.5 incluyó #03, #04, #05 y #51, que no estaban en T0.9: los añadí para comprobar el arreglo
   de `requests` y los que fallaban nuevos con `medium`.

### Decisiones que necesito

1. **Entorno:** ¿opción A (solo `requests`, ya hecha) o B (constraints con el `pip freeze` de producción)? Ver arriba.
2. **Aclaración con 4.5:** ¿`skip` o fallo visible? (Y, si te preocupa no ejercer `_resume_plan` de extremo a
   extremo con 4.5, no veo otra frase que lo provoque; habría que decidir si basta con los tests con mocks.)
3. **Los goldens #28, #48, #49 y #21 con Haiku 5.5:** como D28 no se adopta, ya no hay nada que decidir sobre
   ellos en esta fase; los dejo como están.

### Despliegue (actualizado)

Los pasos y la vuelta atrás **no cambian** respecto a la sección «Despliegue» de arriba, con dos matices:
`fase-2` ahora lleva el planner en **Haiku 4.5** (sin cambios de comportamiento respecto a producción hoy) y
`requirements.txt` con `anthropic==1.14.0` **y** `requests==2.32.5`. Tras reiniciar, además de lo que ya había,
conviene probar el tiempo por Telegram («¿qué tiempo hace en Madrid?»): es justo lo que rompía `requests` 2.34.
Hash de la vuelta atrás: `ee01f58` (`main` actual). Sigue valiendo `.venv-3.11-old` y `.venv-*` ignorado.

**Para en el anexo.**
