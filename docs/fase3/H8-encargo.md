# H8 — encargo (fase 3, parche): el planner cachea sus herramientas

> Responde a: c543917 (tomorrow.md tras H7-revision). 2026-11-18, arquitecto. Decisión: **D59** (ADR-MEMORIA §4).
> Origen: recado del arquitecto de klothulhu. Anthropic avisó de que la tasa de aciertos de caché de la clave común es baja.
> Josem ha subido el tope de la fase a **11,50 $** (antes estaba en ≈ 10,53 $). Este parche no debe pasar de **0,30 $**.

## 1. Qué arreglamos

`_llamar_planner` (`sebastian2/core/orchestrator.py:300`) manda `tools=ALL_TOOLS` en cada vuelta del bucle sin `cache_control`. Son 42 tools, unos 7000 tokens según los bytes, y en el repo no hay ningún marcador de caché. Lo he comprobado: `ALL_TOOLS` es una concatenación de listas estáticas (`core/tools/__init__.py:15`) y ninguna descripción lleva fechas, así que el prefijo es estable. El `system` empieza por `_now_str()` y cambia en cada llamada. No pasa nada: el orden de la caché es `tools` → `system` → `messages`, y lo que cambia después no invalida las tools.

## 2. Requisitos

### R20 — marcador en la última tool del planner (D59)

- Una constante de módulo, por ejemplo `_PLANNER_TOOLS`, con una **copia** de `ALL_TOOLS` en la que solo el último elemento lleva además `"cache_control": {"type": "ephemeral"}`. Es la TTL de 5 minutos, sin `ttl`.
- **`ALL_TOOLS` no se muta.** Lo usan `tests/test_tools.py`, `test_compromisos_tools.py`, `test_turno_solo_lectura.py` y el digest. Copia solo el último dict, no toda la lista en profundidad.
- `_llamar_planner` pasa `tools=_PLANNER_TOOLS`. No toques nada más del request: ni el `system`, ni los `messages`, ni `_PLANNER_EXTRA`.
- `_is_plan_reply`, Alfred (`_synthesize`, `_ask_user`) y el extractor no cambian en este hito.
- Cita `D59` en un comentario junto a la constante.
- **Pruebas sin API:**
  - Con el cliente falso, la lista `tools` que recibe `messages.create` tiene `cache_control == {"type": "ephemeral"}` en el último elemento, y ninguno en los demás.
  - Después de una llamada, ningún elemento de `ALL_TOOLS` tiene la clave `cache_control`.
  - Sin `cache_control`, `_PLANNER_TOOLS` es igual a `ALL_TOOLS`: mismos nombres, mismo orden y mismo contenido.
  - Dos llamadas al planner en el mismo turno reciben `tools` idénticas (`json.dumps(..., sort_keys=False)` igual). Es la guardia contra un futuro invalidador silencioso.

### R21 — el uso registra la caché (D59)

- `_track_usage` acumula también `cache_read_input_tokens` y `cache_creation_input_tokens` (con `getattr(..., 0) or 0`, igual que hoy) en `_turn_usage`.
- La línea `Turn end` añade `cache_read=` y `cache_creation=` como campos de `bind` y en el texto. `tokens_in` sigue siendo solo `input_tokens` (lo no cacheado): no lo sumes.
- **Pruebas sin API:** una respuesta falsa con `cache_read_input_tokens=7000` y `cache_creation_input_tokens=0` acumula bien. Una respuesta sin esos atributos (un `usage` viejo o un mock) no rompe y suma 0. Además, la línea `Turn end` capturada contiene los dos campos.

## 3. [API] y gasto (cada paso, con el «sí» de Josem en tu ventana)

Con la BD de desarrollo del `.env`, nunca la de producción.

1. **Recuento, gratis** (`messages.count_tokens` no se factura): tokens de `ALL_TOOLS` sola, del `system` del planner con un índice típico, de `_ALFRED_SYSTEM` y del prompt del extractor con su tool. Lo necesito para decidir el siguiente paso, fuera de H8.
2. **Comprobación, ≈ 0,10–0,20 $:** dos turnos reales de solo lectura en menos de 5 minutos, que obliguen a usar una tool. Por ejemplo, «¿Qué tiempo hace mañana en Madrid?» y luego «¿Y en Gijón?». Para **cada llamada al planner**, apunta `input_tokens`, `cache_creation_input_tokens` y `cache_read_input_tokens`. Lo esperado:
   - en la primera llamada, `cache_creation` ≈ el recuento de las tools;
   - en las siguientes, `cache_read` ≈ ese mismo número y `cache_creation` ≈ 0.

   Si `cache_creation` sale 0 en la primera, para y avisa: puede ser el mínimo de 4096 tokens o un invalidador.

Informa del gasto por modelo (Haiku 4.5 del planner, Sonnet 4.6 de Alfred).

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No. Las pruebas usan el cliente falso, y el paso [API] usa turnos de solo lectura con la BD de desarrollo.
- **¿Llama a una API externa?** Sí. El modelo es el actual, `claude-haiku-4-5-20251001`, y no cambia. Lo he comprobado con la skill `claude-api`: el mínimo cacheable de Haiku 4.5 es **4096 tokens**, escribir cuesta 1,25×, leer 0,1×, la TTL es de 5 minutos y hay como mucho 4 marcadores. El coste lo da el paso 3.2.
- **¿Toca producción?** Solo al desplegar, y lo hace Josem: merge `--ff-only` de `fase-3` en `main` desde `/data/AssistantStudies` y reinicio de `sebastian.service`. Escribe los pasos exactos en el informe.

## 5. Dónde parar

Cuando estén R20, R21, la pasada completa de pruebas sin API y los dos pasos [API] (si Josem los autoriza), escribe `H8-informe.md` y para. Si algo de este encargo no encaja con el código, para antes y pregunta.

## Para el programador

Responde a: c543917 (tomorrow.md tras H7-revision)

1. Haz R20 y luego R21, con sus pruebas sin API.
2. Pasa la suite completa.
3. Pide a Josem el «sí» para el §3 y ejecuta sus dos pasos.
4. Escribe `docs/fase3/H8-informe.md` con el formato de siempre e incluye los tokens de cada llamada del paso 3.2. Para ahí.
