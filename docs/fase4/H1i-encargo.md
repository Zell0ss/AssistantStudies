# H1i — encargo (fase 4, parche D73): una consulta solo con `query` busca por sus palabras

> Responde a: 578a048 (H1g-informe, anexo H1h). 2026-11-20, arquitecto. Decisión: **D73** (ADR-MEMORIA §4, tentativa). Sin API.

## 1. Qué enseña la primera traza de `/debug` (16:31, con H1f + H1g + H1h desplegados)

Josem preguntó: «¿Qué datos tienes de mí en Telegram?».

- **El planner** llamó a `search_memory` con `{"query": "Telegram"}`, sin `entidad` ni `atributo`. En su índice tenía `yo (tú): telegram_id, nota`.
- **`consultar`** devolvió todo vacío, por tres motivos:
  - sin entidad ni atributo, `filas = []`, por diseño;
  - R15 solo saca términos de la entidad y del atributo, no de la `query`;
  - la nota «…usuario de Telegram…» se quedó por debajo del umbral semántico.
- **Alfred** contestó «No me consta», como debía con lo que recibió.

Aparte: el texto del planner afirmaba el id sacándolo del historial (D26). No llega al usuario, porque Alfred solo ve los resultados de las tools. No se toca aquí.

## 2. Requisitos (D73)

- **R23 — los términos de la `query` buscan hechos.** Si **no** vienen ni `entidad` ni `atributo` y sí viene una `query`:
  - **Términos:** `normalizar(query)`, troceado por espacios y `_`. Se quedan los de 4 letras o más, sin `yo`.
  - **Coincidencia:** un hecho vigente del usuario coincide si algún término es igual a:
    - el nombre normalizado de su entidad, o alguno de sus alias;
    - **o** una de las piezas del nombre de su atributo, troceado por `_` (`telegram_id` → `telegram`, `id`).

    Se excluye el atributo `nota`, porque las notas van por R15.
  - **Salida:**
    - los hechos que coincidan, como mucho 20, los más recientes primero;
    - `"por_palabras": true` en la salida.
  - **Si viene entidad o atributo**, todo sigue como en D71.
- **R24 — los mismos términos buscan notas.** `_notas_para` usa también los términos de la `query` para las notas por palabra. Si hay entidad o atributo, se unen a los suyos.
- **Alfred:** en la línea de «Memoria (consulta)», una frase: con `por_palabras`, los hechos salen por coincidencia de palabras con la pregunta; contesta solo con los que vienen a cuento.
- **R16:** el log de `memoria.consultar` añade `por_palabras=N`, sin contenido.
- **Cita D73 en un comentario** en cada costura.

## 3. Pruebas (sin API, embedder falso; datos inventados)

1. **El caso de la traza:** `yo · telegram_id = 700111222` y la nota «Mi usuario de Telegram es @usuario_prueba». Con solo `query="Telegram"`:
   - sale el hecho, con `por_palabras`;
   - sale la nota;
   - el log dice `por_palabras=1 notas_palabra=1`.
2. **Una pregunta larga,** con `query="¿qué datos tienes de mí en Telegram?"`: el mismo resultado. «datos» y «tienes» no coinciden con nada inventado del catálogo de la prueba.
3. **Coincidencia por entidad:** con `query="Paco"`, salen los hechos vigentes de Paco.
4. **Hechos de otro usuario:** nunca salen.
5. **Hechos cerrados:** nunca salen.
6. **Con `entidad` o `atributo`,** las pruebas de D71 siguen igual.
7. **Términos cortos** («de», «mi») y **`yo`** no buscan nada.
8. **Marca `ZZQUERY`:** no sale en ningún log.
9. **Tope de 20** hechos.
10. **La suite** pasa sin tocar sus esperados. Si alguno cambia, dilo con el motivo.

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No. Es solo de lectura.
- **¿Llama a una API externa?** No.
- **¿Toca producción?** Solo al desplegar, con merge y reinicio, que hace Josem.

## Para el programador

Responde a: 578a048 (H1g-informe, anexo H1h)

1. Haz R23 y R24 con las pruebas del §3.
2. Pasa la suite.
3. Escribe `docs/fase4/H1i-informe.md`, corto, con las órdenes de despliegue, y para.

Sin gasto.
