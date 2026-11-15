# H3 — encargo añadido (fase 2): citas y frontera de salud

> 2026-11-15 · Arquitecto. Se suma a `H2-revision.md` § «Para el programador»: no cambia nada de lo
> que ya estaba pedido para H3.

## 1. De dónde sale

Josem preguntó cómo se guardaría «cita para colonoscopia el día X», junto con lo que va ligado a
ella (código, médico, preparación, recordatorios del día antes) y que se pueda consultar meses
después. Decisión de Josem (opción A, 2026-11-15):

- **D39 (vigente):** en la fase 2, una cita va **solo** a Google Calendar.
  `mark_as_memorable` no la guarda.
- **D40 (tentativa):** en la fase 3, una cita con datos ligados será una entidad de tipo `evento`
  que guarda el id del evento de Google Calendar, y los compromisos relativos colgarán de ella.
  **No es para esta fase:** no se toca el esquema ni la lista de tipos de entidad.

Registro: `30-projects/sebastian/ADR-MEMORIA.md` §4.

Al mirarlo encontré dos huecos, los dos del plan (**arquitecto**):

1. Ningún golden cubre una cita dicha con «recuerda que…». La descripción de
   `mark_as_memorable` pide usarla para «recuerda que…» y a la vez excluye el calendario: las dos
   reglas chocan.
2. La regla 5 del prompt del extractor (`core/memoria/prompts/extractor_hechos.md`) dice que
   «cualquier dato de salud» no es memoria. Pero `alergia` es un atributo semilla (plan §2.1), y
   el escenario E1 espera guardar la alergia de Paco. Hoy pasa porque el modelo se salta la regla,
   no porque la regla lo permita.

## 2. Qué se pide

**R5 · goldens #64 y #65.** Van en `tests/golden/goldens.yaml` y son normativos.

```yaml
- id: 64
  phrase: "Tengo cita para la colonoscopia el 3 de diciembre a las 10"
  mode: exact
  expected: [calendar_add_event]
  validates: "Fase 2 H3 (D39), negativa: una cita con fecha es calendario, no memoria ni salud"

- id: 65
  phrase: "Recuerda que el 3 de diciembre tengo la colonoscopia"
  mode: any_of
  expected:
    - [calendar_add_event]
    - [request_clarification]
  validates: "Fase 2 H3 (D39), negativa: «recuerda que» con una cita con fecha es calendario. Sin hora puede preguntar; lo único que falla es mark_as_memorable o salud"
```

- Línea base solo con `-k` **[API]** (céntimos), antes de tocar nada.
- Si #65 falla porque el planner elige `mark_as_memorable`, el arreglo va en la descripción de
  esa tool: excluir también «citas y eventos con fecha, aunque diga "recuerda que"». Repites
  `-k` con #56–#65 y cuentas en el informe qué cambiaste y con qué resultado.
- Si falla por `salud`, **no lo arregles**: pégalo en el informe y lo decido yo.

**R6 · regla 5 del extractor.** Sustituye «y cualquier dato de salud» por:

> y los registros de salud del día (cómo ha dormido, qué ha comido, hambre, síntomas o dolores
> pasajeros): son de Tristras. Las alergias sí son memoria.

- Así el prompt dice lo que el plan ya decidió: `alergia` es memoria. La frontera completa entre
  Sebastian y Tristras se decide en la fase 3 (ADR-MEMORIA §5).
- **[API]** se repasan los 10 casos del extractor (unos 0,03 $). Tienen que seguir pasando los 10.
- Prueba sin API: `test_prompt_extractor_alergia_es_memoria`. Comprueba que el prompt contiene
  «alergias sí son memoria» y ya no contiene «cualquier dato de salud».

## Para el programador

Responde a: 5739f7f (H2-informe). Se suma a la `## Para el programador` de `H2-revision.md`
(c4b4e2c).

1. Haz R5 y R6 dentro de H3, en commits propios. Encájalos donde te venga mejor en tu orden de
   H3, pero **antes** de la pasada completa de goldens (que pasa a ser de 65) y de los escenarios.
2. Todo el gasto entra en el tope de 5 $ ya aprobado. El «sí» de cada paso [API] te lo da Josem
   en tu ventana, como siempre.
3. Lo demás sigue igual. **Para** en `docs/fase2/H3-informe.md`, con #64 y #65, el diff de
   descripciones si R5 lo pidió y los 10 casos de R6.
