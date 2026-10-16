# H2 (fase 2) — Revisión del arquitecto

Responde a: 5739f7f (H2-informe)

**Veredicto: aprobado con retoques.** Son cuatro retoques pequeños: dos huecos del plan, una frase
que promete algo que no existe y el prompt del extractor. Se hacen **al principio de H3**, sin parar
aquí.

## 1. Comprobado contra el código (`9300aa6`, `51fc60c`, `92ce116`, `5739f7f`)

- **`resolucion.decidir_hecho`:** sigue las reglas del plan, una a una (retirar fuerte o débil,
  `varios`, `uno` sin vigente, igual, distinto fuerte o débil). Correcto.
- **Sustitución atómica,** registro de decisiones sin valores y privacidad en el log
  (`_TOOLS_SIN_LOG_DE_CONTENIDO`). Correcto.
- **El extractor:** los 10 casos salen bien. El prompt va en un fichero (bien; es el primero del
  repo y sirve de patrón). La línea D16 en `_ALFRED_SYSTEM` funciona (#20).
- **Desviaciones:**
  - 1: el defecto de 011, bien cazado.
  - 2: el cambio de firma por `on_usage`.
  - 3: `temperature` en 1.14. Lo anoto para que no vuelva.
  - 5–7.
  - 8: `search_memory` viejo hasta H3. Correcto, porque la rama no se despliega antes de H4.

  Todas aceptadas.
- **Desviación 4** (una transacción por hecho): **aceptada.** Los hechos de una frase son
  independientes, y lo que tiene que ser atómico es cerrar el viejo y abrir el nuevo.
- **Suite:** lanzada por mí: `521 passed`.

## 2. Hallazgos y decisiones

### 2.1 `parentesco` con cardinalidad `uno` — hueco del plan (arquitecto)

Lo sembré como `uno`. En el caso 8 se guarda «hermano de Ana». Si luego el usuario dice «Paco es mi
cuñado», el valor es distinto y la resolución es fuerte, así que **sustituiría** y se perdería que
es hermano de Ana. Una persona puede tener varias relaciones a la vez.

**R1:** `parentesco` pasa a `varios`. Va en 011, como `UPDATE` idempotente después del `INSERT`
(011 aún no está en producción), reaplicada a test y desarrollo. Prueba:
`test_parentesco_varios_no_sustituye`.

### 2.2 «Dígame si prefiere otro nombre» — promete algo que no existe (arquitecto)

La frase la puse yo en el plan §2.2, y hoy no hay manera de renombrar ni de confirmar un pendiente.
**Decisión 2 del informe:** confirmar y renombrar los pendientes es de la **fase 3**, con el resumen
de la mañana (D16).

**R2:** la línea de D16 en `_ALFRED_SYSTEM` solo **informa** («he abierto la categoría
*lugar de residencia*»), sin ofrecer cambiar el nombre. Prueba: que el prompt no contenga «otro
nombre».

### 2.3 Retirar una nota de texto libre — decisión 1 del informe: sí, en H3

En H3 se construye la búsqueda en `<base>_notas`, así que encaja ahí.

**R3** (H3), en `decidir_hecho` y el servicio: un `retirar` cuya entidad o atributo no se resuelve
de forma fuerte **busca en las notas vigentes del usuario** por similitud con el valor o el texto.
- Si la mejor nota supera `sustituir` (0,68) con su margen, se cierra con `valid_to` y queda en
  `mem_decisiones` con la regla `retirar_nota`.
- Si no, `sin_cambio` con el aviso de siempre.
- **Nunca** cierra más de una nota por turno.

Pruebas:
- `test_retirar_nota_por_similitud` (con el embedder falso);
- `test_retirar_nota_debil_no_toca`;
- E5 del plan sigue igual, y se añade **E9**: «Uso camisetas UV para bañarme» → «Olvida lo de las
  camisetas UV» → la nota queda cerrada.

### 2.4 El caso 4 (decisión → `nota`) — decisión 3: sí, retoque del prompt

Si una decisión que puede cambiar («no publico saxhero») va a `nota`, la corrección posterior («al
final sí publico») **añade** otra nota en vez de sustituir. Quedan dos verdades contradictorias
vigentes, que es justo lo que D5 quería evitar. Además, el escenario E6 espera `crear_atributo`.

**R4:**
- **Prompt del extractor:** para un estado o una decisión que pueden cambiar con el tiempo
  (publicar o no, dónde vive, qué coche tiene, si algo está pausado), usa un atributo específico de
  cardinalidad `uno`, existente o nuevo. Usa `nota` solo para lo que no encaje en ningún atributo y
  no sea una decisión ni un estado.
- **Quita `ejemplos` del esquema:** con la representación (a) no se usa, y le cuesta tokens al
  extractor (D35, calibración 2).
- **[API]** se repasan los 10 casos (unos 0,03 $). En el caso 4 se acepta cualquier atributo que
  **no** sea `nota`, con cardinalidad `uno`. Los demás casos tienen que seguir pasando.

## 3. Gasto

0,136 $ de 5 $. Correcto, y con OpenAI medido.

## Para el programador

Responde a: 5739f7f (H2-informe)

H2 aprobado con retoques. Sigue con H3 sin parar, en este orden:

1. **R1** (`parentesco` a `varios`) y **R2** (la línea de D16), con sus pruebas, en commits propios.
2. **R4:** el prompt del extractor, sin `ejemplos`, y los 10 casos **[API]**.
3. **H3** según el plan §3, con **R3** (retirar una nota por similitud) y el escenario **E9** añadido.
   - La línea base de los goldens #56–#63 va solo con `-k`.
   - Después, la pasada completa y los escenarios.
4. **Para** en H3 con `docs/fase2/H3-informe.md`: coste por modelo y de OpenAI, y las respuestas
   de los escenarios pegadas.
