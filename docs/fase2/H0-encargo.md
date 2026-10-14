# H0 (fase 2) — Encargo del arquitecto: ¿puede Haiku 5.5 hacer de planner?

Responde a: — (primer mensaje de la fase 2)

**Plan:** arquitecto. La fase 2 cambia el esquema y la familia `memory`, y su plan se escribe
después de este hito. H0 es una evaluación con un cambio pequeño: el modelo del planner.
**Decisión:** D28 (tentativa) en `30-projects/sebastian/ADR-MEMORIA.md`. Josem dio el visto
bueno el 2026-10-14.
**Rama y worktree:** `fase-2`, en `/data/AssistantStudies-fase2`, sacada de `main` = `ee01f58`.
**Config:** como en la fase 1. Se copia `config.yaml` (nunca symlink); los tests van a
`sebastian_test` (D25) y los goldens con los servicios externos neutralizados (D27).

## 1. Por qué

Una pasada completa de goldens cuesta unos 1,06 $, y el planner (Haiku 4.5) se lleva 0,85 $. Según
la skill `claude-api` (caché del 2026-10-06), `claude-haiku-5-5` cuesta 0,10 $ / 0,50 $ por millón
de tokens con prompts de hasta 100.000, frente a 1 $ / 5 $ de Haiku 4.5. Los prompts del planner
rondan los 8.000–16.000 tokens. Si funciona igual de bien, abarata el uso diario y los goldens, y
la extracción de hechos de la fase 2 nacería ya sobre ese modelo.

Lo que puede comerse el ahorro o romper algo, según la guía de migración de la skill
(`shared/model-migration.md` § «Migrating to Claude Haiku 5.5»):

- **Piensa por defecto** (adaptive), y el razonamiento se cobra como salida y cuenta para
  `max_tokens`. Se controla con `output_config.effort`.
- **El mismo texto cuenta un ~30 % más de tokens.**
- **Rechaza con un 400** `temperature`, `top_p` y `top_k` no por defecto, el prefill y
  `budget_tokens`. En `core/` no usamos ninguno de los tres: lo he mirado.
- **La respuesta puede empezar con bloques `thinking`.** Hay que leer los bloques por `type`, no
  por posición, y devolver los `thinking` sin tocar junto con los `tool_result`.
- **Tiene clasificadores de seguridad** que pueden rechazar una petición
  (`stop_reason: "refusal"`) sin pasarla a otro modelo.

## 2. Qué se cambia

Solo `core/orchestrator.py`. La síntesis y `_ask_user` siguen en `claude-sonnet-4-6`, y el
cuaderno no se toca.

- **T0.1 · Un solo sitio para el modelo del planner.** Hoy el ID está repetido en las líneas 205,
  247, 253, 375 y 381. Va a una constante de módulo, `_MODELO_PLANNER`, junto a su
  `output_config` (`{"effort": "low"}`), con un comentario `D28`. `_track_usage` usa la misma
  constante.
- **T0.2 · Planner en `claude-haiku-5-5`** con esfuerzo `low`, en `_handle_inner` y en
  `_resume_plan`.
  - El bucle ya añade `response.content` entero a `messages`, así que los bloques `thinking`
    vuelven intactos. Confírmalo con una prueba.
  - Los bloques de tool se leen por `type`, como ya se hace.
  - `max_tokens` del planner: súbelo lo necesario para que quepa el razonamiento. Cuenta en el
    informe qué valor pones y por qué.
- **T0.3 · `_is_plan_reply`.**
  - Hoy usa `max_tokens=10` y `response.content[0].text`; con Haiku 5.5 eso se rompe.
  - Pasa al mismo modelo, con `max_tokens` holgado y leyendo el primer bloque de tipo `text`.
  - Si no hay bloque de texto, se trata como «NO» y se deja un `warning`.
- **T0.4 · Rechazos.** Si el planner devuelve `stop_reason == "refusal"`, se registra un
  `warning` con `stop_details.category`, sin el contenido del mensaje. El turno sigue como cuando
  el planner termina sin tools: síntesis sin datos, que con D26 dirá que no le consta.
- **T0.5 · El SDK instalado es `anthropic` 0.79.0.** No lo actualices en este hito.
  - Comprueba en la documentación de la skill `claude-api` (no de memoria) cómo pasar
    `output_config` con esta versión. Si el parámetro no existe, usa `extra_body`.
  - Si `extra_body` tampoco basta, para y lo pones en «Decisiones que necesito».
- **T0.6 · Pendientes de plan serializados.** `pending_plans` guarda `messages` con
  `_messages_to_json`. Ahora esos mensajes llevan bloques `thinking` con `signature`, y al
  reanudar se reenvían. Comprueba que el ida y vuelta conserva `signature` y `thinking` (aunque
  esté vacío). La guía avisa de que un serializador que se salta los bloques vacíos rompe el
  razonamiento.

## 3. Pruebas normativas

Sin API (en `tests/test_orchestrator.py`):

- `test_planner_usa_modelo_unico`: todas las llamadas del planner, del `_resume_plan` y de
  `_is_plan_reply` van con `_MODELO_PLANNER`.
- `test_respuesta_con_thinking_primero`: con una respuesta simulada `[thinking, tool_use]`, el
  bucle ejecuta la tool y el siguiente `messages` lleva el bloque `thinking` tal cual.
- `test_is_plan_reply_con_thinking_primero`: con `[thinking, text("SI")]` devuelve `True`; con
  solo `[thinking]` devuelve `False` y deja un `warning`.
- `test_refusal_del_planner`: con `stop_reason="refusal"`, el turno termina y sintetiza, deja un
  `warning` con la categoría y no ejecuta ninguna tool.
- `test_pending_plan_conserva_thinking`: `_messages_to_json` → `_messages_from_json` conserva un
  bloque `thinking` con `thinking=""` y su `signature`.

**[API]:**

1. **Pasada completa de goldens (55) con el planner en Haiku 5.5.** El harness ya mide el coste
   por modelo (R1 de la fase 1).
2. **Un flujo de aclaración y reanudación real** contra `sebastian_test`, marcado `golden`. Una
   frase que provoque `request_clarification` (por ejemplo, «Apunta en el calendario una cita»),
   y luego la respuesta. El segundo turno no puede dar un 400. Comprueba el `_resume_plan` con
   bloques `thinking` reenviados.

**Línea base de latencia sin gasto.** Calcula la mediana y el p90 de `latency_ms` de las líneas
`Turn end` de producción con Haiku 4.5. Están en `logs/` del directorio de producción, solo
lectura; LogCentral solo tiene 8 turnos (mediana 6,4 s). En la pasada de goldens, que el harness
apunte la latencia de cada turno y dé la mediana y el p90.

## 4. Criterio para adoptar el cambio (lo aplico yo en la revisión)

Se adopta Haiku 5.5 como planner si se cumplen las tres:

1. **Goldens:** 55/55. Un fallo intermitente que pase al repetirlo solo se acepta, con las dos
   salidas guardadas, como el #28 de la fase 1. Un fallo estable no.
2. **Coste:** la pasada completa por debajo de **0,5 $**.
3. **Latencia:** la mediana por turno no empeora más de un **30 %** respecto a la línea base.

Si no se cumplen, el planner vuelve a Haiku 4.5. **T0.1, T0.3, T0.4 y T0.6 se quedan en
cualquier caso**: dejan el código preparado.

## 5. Lista previa (convención §4)

- **¿Algo borra o sobrescribe datos?** Solo lo de siempre: el harness en `sebastian_test` (D25)
  y con los servicios externos neutralizados (D27). El flujo de aclaración escribe en
  `pending_plans` y `conversations` de `sebastian_test`.
- **¿Algo llama a una API externa?** Sí, en pasos **[API]**.
  - `claude-haiku-5-5`: el ID y los precios salen de la skill `claude-api`, consultada el
    2026-10-14. La propia skill pide comprobar el precio en la página en vivo antes de
    presupuestar. **Hazlo** (la fila «Pricing» de `shared/live-sources.md`) y pega lo que diga
    en el informe.
  - `claude-sonnet-4-6` para la síntesis, sin cambios.
  - **Tope: 1 $** para el hito, en una pasada completa más, como mucho, una repetición de
    goldens sueltos con `-k`. Es probable que la pasada cueste unos 0,3 $.
  - **Pendiente del «sí» de Josem en tu ventana** antes del primer paso [API].
- **¿Algo toca producción?** Solo si se adopta, y lo hace Josem: merge `--ff-only` de `fase-2` en
  `main` y reiniciar `sebastian.service`. Sin cambios de BD, unidades ni `config.yaml`. Deja los
  comandos en el informe.

## Para el programador

Responde a: — (primer mensaje de la fase 2)

1. Prepara el worktree: copia de `config.yaml` y `pytest` de línea base sin API.
2. Línea base de latencia de producción, sin gasto (§3).
3. Las pruebas sin API del §3, primero en rojo. Después, T0.1–T0.6.
4. Con el «sí» de Josem, los dos pasos **[API]**. Si el coste se acerca al tope, paras.
5. Informe en `docs/fase2/H0-informe.md`, con el formato de la convención §3.2. Incluye: goldens
   (salida en `docs/fase2/goldens/`), coste medido por modelo, latencias comparadas con la línea
   base, el precio en vivo y los comandos de despliegue.

**Para en el informe.** El plan de la fase 2 lo escribo yo después de revisar H0.

## 6. Añadido (2026-10-14): Python 3.12 y `anthropic` 1.x

Responde a: 360d7bc (este mismo encargo; aún no hay informe de H0)

**Decisión de Josem (2026-10-14, opción B):** se actualiza el SDK dentro de H0.
- Hoy el `.venv` de Sebastian corre con **Python 3.11.0rc1**, la del sistema, que el `CLAUDE.md`
  global prohíbe; al recrear un `.venv` se usa 3.12. Además tenemos `anthropic` **0.79.0**, y la
  última es la **1.14.0** (lo he mirado con `pip index versions`).
- La guía de la skill `claude-api` (`python/claude-api/sdk-upgrade.md`) dice que de 0.x a 1.x
  cambian tres cosas: el cliente HTTP pasa de `httpx` a `httpx2`, se quita la superficie
  obsoleta y el mínimo es Python 3.10.
- Nuestro uso es pequeño (`Anthropic(...)`, `messages.create`, `APIError`, `APIConnectionError`,
  `RateLimitError`, `model_dump`, en `core/orchestrator.py` y `scripts/cuaderno/despertar.py`), y
  ningún punto de la guía nos toca a primera vista. **Compruébalo** con el inventario del paso 1
  de esa guía, no te fíes de mí.

**Orden.** He visto que ya estás en la pasada completa con Haiku 5.5 sobre el SDK 0.79. **Termínala
tal cual**: mide D28 sin mezclar nada. Lo de esta sección va **después**, en commits propios.

- **T0.7 · `.venv` nuevo en el worktree** con `python3.12 -m venv .venv`.
  - Instala `requirements.txt` cambiando solo `anthropic==0.79.0` por `anthropic==1.14.0`. El resto
    de los pins se quedan como están; si alguno no instala en 3.12, para y cuéntalo.
  - Actualiza `requirements.txt` solo en la línea de `anthropic`. Si `pip` trae dependencias
    nuevas (`httpx2`…), no las fijes a mano: las arrastra el propio SDK.
  - Revisa también `sebastian2/sebastian2.service`, `deploy/cuaderno.service` y cualquier otro
    sitio que cite la ruta del `.venv`. La ruta no cambia, cambia el contenido.
- **T0.8 · Código.** Si con 0.79 pasaste el esfuerzo por `extra_body` (T0.5), ahora pasa a
  `output_config=` normal, comprobado en la documentación de la skill para 1.x. Lo demás, solo si
  el inventario de la guía encuentra algo.
- **T0.9 · Pruebas.**
  1. `pytest` completo en el `.venv` nuevo, sin API: todo en verde.
  2. **[API]** con `-k`: #20–#23 (memoria y capacidades), #50 y #54 (historial), un golden de
     salud, el flujo de aclaración y reanudación, y el test de honestidad de la fase 1 (H4). Es
     la comprobación de que el SDK nuevo se comporta igual con la configuración final (Haiku 5.5
     + 1.14). La salida va a `docs/fase2/goldens/` como siempre.

**Tope del hito:** sube de 1 $ a **1,2 $** (Josem, 2026-10-14). Si el SDK nuevo falla algún golden
que en la pasada completa sobre 0.79 pasaba, **para**: es del SDK, y lo cuentas antes de tocar nada
más.

**Despliegue (lo hace Josem; déjalo escrito en el informe, con la vuelta atrás).** Va al final de
H0, se adopte o no D28, porque el `.venv` nuevo vale igual con cualquier planner:

1. Parar `sebastian.service`.
2. `mv /data/AssistantStudies/sebastian2/.venv /data/AssistantStudies/sebastian2/.venv-3.11-old`
3. Merge `--ff-only` de `fase-2` en `main`.
4. `python3.12 -m venv .venv` e instalar `requirements.txt` en el directorio de producción.
5. Arrancar el servicio y comprobar el arranque y que no hay errores en LogCentral. El cuaderno
   usa el mismo `.venv` en su próximo disparo.

**Vuelta atrás:** parar, borrar el `.venv` nuevo, devolver `.venv-3.11-old` a `.venv`,
`git reset --hard` al `main` anterior y arrancar. Deja la ruta exacta y el hash en el informe.

## Para el programador

Responde a: 360d7bc (H0-encargo)

1. Termina la pasada completa de Haiku 5.5 sobre 0.79 y guarda su salida. No la repitas.
2. T0.7–T0.9 (este §6), en commits separados de lo de D28.
3. Informe de H0 con las dos partes:
   - D28: el criterio del §4, contra la pasada completa;
   - SDK y Python: la lista de cambios encontrados, los goldens con `-k` y los pasos de despliegue
     con la vuelta atrás.
