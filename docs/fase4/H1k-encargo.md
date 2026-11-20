# H1k — encargo (fase 4): el log de fin de turno separa el uso por papel

> Responde a: 0b7d605 (H1j-informe). 2026-11-20, arquitecto. Josem lo aprueba («Adelante tb!!»). Sin API. **Va después de la segunda vuelta de H1j.**

## 1. Por qué

`Turn end` suma en una sola cifra los tokens del planner (Haiku), del extractor (Haiku, vía `on_usage`) y de Alfred (Sonnet). Hoy, 20/11, han salido 16 turnos con `tokens_in` = 126 mil, `cache_read` = 227 mil y `cache_creation` = 72 mil. Con eso no se sabe quién gasta sin caché. Se pide para el indicador de D59 (≈ 26/11).

Sé, sin medirlo, que Alfred no lleva `cache_control`: su system tiene unos 1.400 tokens, y con el historial pasa del mínimo de Sonnet 4.6, que es 1024. Eso no se toca aquí: primero se mide.

## 2. Requisitos

- **R26 — el uso por papel.**
  - `_track_usage(response, model, papel)`, con `papel` en `planner`, `extractor`, `alfred` o `otro`. `otro` es la llamada SI/NO de la línea 470 y lo que haya parecido.
  - `on_usage` del ejecutor pasa `extractor`.
  - Por cada papel se acumulan `in`, `out`, `cache_read` y `cache_creation`.
- **R27 — el log.**
  - La línea `Turn end` se queda **igual** (totales y campos de `bind`), para no romper lo que la lee.
  - Detrás va una segunda línea `INFO`:

    `Turn uso | user=… | planner=in/out/cr/cc | extractor=… | alfred=… | otro=…`

    Solo salen los papeles que tuvieron llamadas.
  - Los mismos datos van en `bind`, como `uso_por_papel` (un dict).
  - Sin contenido.
- **Cita D59 en un comentario.**

## 3. Pruebas (sin API, cliente falso)

1. **Un turno completo:** planner → `mark_as_memorable` → extractor → planner → Alfred. Sale `Turn uso` con los tres papeles, y sus sumas cuadran con los totales de `Turn end`.
2. **Un turno sin tools:** solo `planner` y `alfred`.
3. **`Turn end`** sale exactamente igual que antes. Su prueba no se toca.
4. **Ningún contenido en el log,** comprobado con una marca.

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No.
- **¿Llama a una API externa?** No.
- **¿Toca producción?** Solo al desplegar, que lo hace Josem. Va en el mismo despliegue que H1j.

## Para el programador

Responde a: 0b7d605 (H1j-informe)

1. Cuando acabes la segunda vuelta de H1j, haz R26 y R27 con las pruebas del §3.
2. Pasa la suite.
3. Escribe `docs/fase4/H1k-informe.md`, corto, y para.

El despliegue va junto con H1j, con una sola línea. Sin gasto.
