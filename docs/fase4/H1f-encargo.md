# H1f — encargo (fase 4, parche D71): `search_memory` no contesta «nada» cuando sabe de quién se pregunta

> Responde a: 898ee44 (H1e-informe). 2026-11-20, arquitecto. Decisión: **D71** (ADR-MEMORIA §4, tentativa). Sin API.

## 1. Qué pasó en producción (14:34 UTC, con H1e desplegado)

Un minuto después de guardar bien `yo · telegram_id` y una nota con «…usuario de Telegram…», Josem preguntó: «¿Qué datos tienes de mí en Telegram?».

- **El resultado:** `memoria.consultar: hechos=0 historial=0 notas=0`.
- **La respuesta de Alfred:** «No me consta ningún dato de Telegram».

Los parámetros de `search_memory` no se loguean (D42), así que no sé qué mandó el planner. Pero en `servicio.py:94`, una `entidad` o un `atributo` que no se resuelven por alias exacto dejan `filas = []`. Así que vale con un `atributo="telegram"` y `entidad="yo"`. Y la nota no superó el umbral semántico de `reutilizar`, que se calibró para el catálogo y no para notas.

## 2. Requisitos (D71)

- **R14 — entidad sí, atributo no.** Si la `entidad` se resuelve y el `atributo` no:
  - se devuelven los hechos vigentes de la entidad, y nada del historial;
  - en la salida va `"atributo_no_resuelto": true`;
  - el resto de casos se queda como hoy:
    - si la entidad no se resuelve, no hay hechos;
    - sin entidad y sin atributo, tampoco.
  - **En el prompt de Alfred,** junto a lo de memoria (`orchestrator.py`, «Memoria (consulta)»), una frase: con `atributo_no_resuelto`, contesta solo con los hechos que vienen a cuento de la pregunta, y si ninguno viene a cuento, dilo.
- **R15 — notas por palabra.** Además de las semánticas, se buscan las notas **vigentes del usuario** que contienen como palabra completa algún término de la entidad o del atributo pedidos:
  - los términos se normalizan con `normalizar`, se trocean por `_` y por espacios, y se quedan los de 4 letras o más, sin `yo`;
  - se unen a las semánticas sin repetir, y las semánticas van primero;
  - el tope sigue siendo `_MAX_NOTAS_EN_CONSULTA`;
  - se hace con SQL sobre los hechos de `nota` del usuario, o en Python sobre `hechos_con_nombres`. Lo que sea más simple.
- **R16 — log sin contenido.** La línea `memoria.consultar` añade:
  - `entidad=<no_pedida|resuelta|no_resuelta>` y `atributo=<igual>`;
  - `notas_sem=N notas_palabra=M`.
  - Ni nombres ni valores.
- **Cita D71 en un comentario** en cada costura.

## 3. Pruebas (sin API, embedder falso; datos inventados)

1. **El caso de producción:** `yo · telegram_id = 700111222` vigente y una nota «Mi usuario de Telegram es @usuario_prueba». Con `entidad="yo"`, `atributo="telegram"` y `query="datos de Telegram"`, y un embedder que deja la nota por debajo del umbral:
   - sale el hecho, con `atributo_no_resuelto`;
   - sale la nota, por palabra;
   - el log dice `entidad=resuelta atributo=no_resuelta notas_palabra=1`.
2. **Entidad que no se resuelve:** sigue dando 0 hechos, como hoy.
3. **Sin entidad ni atributo:** 0 hechos, como hoy. Solo las notas semánticas, y las de palabra si hay términos.
4. **Las notas de otro usuario** nunca salen por palabra.
5. **Las notas cerradas** (`valid_to`) no salen por palabra.
6. **Términos cortos y `yo`:** «yo» y «de» no buscan nada.
7. **Marca `ZZCONS`** en la entidad, el atributo y la query: no aparece en ningún log.
8. **La suite de memoria** pasa sin tocar sus esperados. Si alguno cambia, dilo con el motivo.

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No. Es solo de lectura.
- **¿Llama a una API externa?** No. El prompt de Alfred gana una frase, y eso solo se mide en producción.
- **¿Toca producción?** Solo al desplegar, con merge y reinicio, que hace Josem.

## Para el programador

Responde a: 898ee44 (H1e-informe)

1. Haz R14, R15 y R16 con las pruebas del §3.
2. Pasa la suite.
3. Escribe `docs/fase4/H1f-informe.md`, corto, con las órdenes de despliegue, y para.

Sin gasto.
