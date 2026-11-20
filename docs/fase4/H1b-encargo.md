# H1b — encargo (fase 4, parche): Alfred no se corta a media frase

> Responde a: b9c9d7c (H1-informe, cierre). 2026-11-20, arquitecto. Decisión: **D68** (ADR-MEMORIA §4, tentativa).
> Sin API. Va en el mismo despliegue que H1.

## 1. Qué pasó en producción (20/11)

Josem preguntó «¿Qué herramientas tienes ahora?». Alfred empezó un inventario y se cortó en mitad de una palabra («…guardada en el vault de»). La causa está en `core/orchestrator.py`:

- **`:723`:** la síntesis lleva `max_tokens=400`.
- **`:727`:** devuelve `response.content[0].text` sin mirar `stop_reason`.
- **`:734`:** `_ask_user` tiene el mismo problema, con `max_tokens=100`.

El planner ya avisa de un corte (D28, `:358`). Alfred no avisa.

## 2. Requisitos (D68)

- **R6 — techo.** Constantes `_ALFRED_MAX_TOKENS = 1500` y `_ASK_MAX_TOKENS = 300`, en lugar de los números sueltos.
  - El techo no cuesta nada si no se usa. El peor caso es 1500 × 15 $/MTok ≈ 0,02 $ por turno.
  - El «concisa» del prompt se queda tal cual.
- **R7 — si aun así se corta** (`stop_reason == "max_tokens"`):
  - **Log `WARNING`**, sin texto (D42): `Alfred cortado por max_tokens (<techo>) | user=… | chars=<n>`.
  - **Recorte:** el texto se corta en el último salto de línea. Si no hay ninguno, en el último fin de frase («. », «? », «! »). Si tampoco, se queda como está. Después se añade, en una línea aparte, «(Me he quedado sin espacio, señor. Dígame si quiere el resto.)».
  - **Lo mismo en `_ask_user`.**
  - Una función pequeña sirve para los dos sitios.
- **R8 — respuesta sin texto.** Si `response.content` no trae un bloque de texto, no hay `IndexError`. Se usa el mismo mensaje de error que ya se dé en ese caso, y se escribe un log `WARNING` con el `stop_reason`.

## 3. Pruebas (sin API, cliente falso)

1. La síntesis llama con `max_tokens=_ALFRED_MAX_TOKENS` (1500), y `_ask_user` con 300.
2. Con `stop_reason="max_tokens"` y el texto «• Uno — a.\n• Dos — b.\n• Tres — guardada en el vault de», la respuesta acaba en «• Dos — b.» y luego la línea de «Me he quedado sin espacio».
3. Con un corte sin saltos de línea pero con frases («Primera frase. Segunda a medias»), se corta tras «Primera frase.».
4. Con `stop_reason="end_turn"`, el texto sale exactamente igual que hoy.
5. El texto de la respuesta no aparece en ningún log (loguru, con una marca `ZZALFRED`).
6. Con una respuesta sin bloque de texto, no hay excepción.

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No.
- **¿Llama a una API externa?** No en las pruebas. En producción, la misma llamada de hoy con un techo más alto. Precio de Sonnet 4.6 según la skill `claude-api`: 3 $ / 15 $ por MTok.
- **¿Toca producción?** Solo al desplegar, junto con H1, y lo hace Josem.

## Para el programador

Responde a: b9c9d7c (H1-informe, cierre)

1. Haz R6, R7 y R8 en `core/orchestrator.py`, con las pruebas del §3. Cita D68 en un comentario.
2. Pasa la suite.
3. Escribe `docs/fase4/H1b-informe.md`, corto, y para.

Sin gasto. Josem despliega H1 y H1b juntos, cuando yo revise tu informe.
