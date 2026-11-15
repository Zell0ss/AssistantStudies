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

## 3. Segunda parte (2026-11-15): la frase de origen de cada hecho

Josem lo ha decidido el 2026-11-15. Registro en `ADR-MEMORIA.md` §4:

- **D41 (vigente):** cada llamada a `mark_as_memorable` guarda su frase de origen en `mem_fuentes`,
  y cada hecho apunta a ella. Sirve para volver a extraer, para la consolidación de la fase 3 y para
  auditar. **Va antes de H4** porque es irreversible: un hecho que se guarda sin fuente ya no la
  recupera, porque `conversations` se borra a los 7 días (D23).
- **D42 (vigente):** «olvida lo de…» **borra el texto**, no solo cierra el hecho. D5 queda revisada
  solo para `retirar`; corregir sigue sin borrar nada.

### 3.1 Contrato: migración `012_memoria_fuentes.sql`

Sin `USE` (D20) e idempotente, como 010 y 011.

```sql
CREATE TABLE IF NOT EXISTS mem_fuentes (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     VARCHAR(50) NOT NULL,
  texto       TEXT NULL,          -- lo que recibió el extractor (inputs['texto'] de la tool); NULL = purgada
  mensaje     TEXT NULL,          -- el mensaje literal del usuario en ese turno; NULL = purgado o no disponible
  purgada_at  DATETIME NULL,      -- D42
  created_at  DATETIME NOT NULL,
  INDEX idx_user_fecha (user_id, created_at)
);
-- mem_hechos: columna fuente_id BIGINT NULL, FK a mem_fuentes(id), con índice.
-- NULL solo para lo que existía antes (origen 'migracion', D18).
```

- **Por qué hay `texto` y `mensaje`:** el planner reescribe la frase como autocontenida
  (`inputs['texto']`), y eso es lo que permite volver a extraer. El literal sirve para auditar.
- `mensaje` llega del orquestador al `ToolExecutor` y de ahí a
  `ServicioMemoria.guardar(user_id, texto, username=None, mensaje=None)`.
  - Si pasar el mensaje toca el orquestador más allá de añadir un parámetro, **para y pregunta**.
- **Una fuente por llamada a `guardar`,** aunque la frase dé varios hechos o ninguno.
  - Si no sale ningún hecho (`hechos: []`), la fuente se crea igual y se purga en el acto: así no
    queda texto sin hecho.
  - Las notas también llevan su `fuente_id`.

### 3.2 Regla de purga (D42)

Cuando `retirar` cierra un hecho H, se purgan:

1. el **valor de H**, que pasa a `''` en `mem_hechos` (la fila, sus fechas y su decisión se quedan);
2. si H es una nota, su **vector** en `<base>_notas`;
3. también el valor (y el vector, si es nota) de los hechos de su **cadena de sustituciones**, es
   decir, los que H sustituyó directa o indirectamente (`superseded_by` → … → H);
4. la **fuente** de H y la de cada hecho de la cadena, poniendo `texto` y `mensaje` a NULL y
   `purgada_at`, pero solo si **todos** los hechos de esa fuente están cerrados. Una fuente con
   algún hecho vigente se queda como está.

Lo que **no** se purga:

- Corregir (`sustituir`) no purga nada: el historial «¿qué te dije antes?» sigue funcionando (E3).
- `mem_decisiones.detalle` y `senales` ya no llevan texto del usuario (`servicio.py:110`). Si
  encuentras alguno que sí lo lleve, dilo en el informe.

La purga y el cierre van en **la misma transacción** que `retirar`. El borrado en Qdrant va
después del commit: si falla, se registra con un `warning` sin el texto y el turno sigue.

### 3.3 Pruebas

Todas contra `sebastian_test` y las colecciones de test (D25), sin API:

- `test_guardar_crea_fuente_y_enlaza`: dos hechos de una frase comparten `fuente_id`; la fuente
  tiene `texto` y `mensaje`.
- `test_fuente_sin_hechos_se_purga`.
- `test_sustituir_no_purga`: E2 deja las dos fuentes con su texto.
- `test_retirar_purga_cadena`: guardar 2,30 → corregir a 2,4 → olvidar. Las dos fuentes quedan
  purgadas y los dos valores en `''`.
- `test_retirar_no_purga_fuente_con_vigentes`: una frase con dos hechos, y se olvida uno. La fuente
  conserva su texto, y el valor del retirado sí queda en `''`.
- `test_retirar_nota_purga_vector`, con el embedder falso.
- Escenario **E5** ampliado: después de olvidar el marisco, su valor queda en `''` y la fuente de
  «frutos secos» conserva su texto.

### 3.4 Lista previa (convención §4)

- **¿Borra datos?** Sí: valores, fuentes y vectores. Las pruebas usan solo `sebastian_test` y las
  colecciones `*_test_*`, y el guardarraíl de D25 tiene que impedir que se ejecuten contra otra
  base.
- **¿API externa?** No hay llamadas nuevas. Los escenarios que ya estaban crecen un poco.
- **¿Producción?** La migración 012 se aplica en H4 junto con 010 y 011, en `sebastian_db`. La
  ejecuta Josem.

## Para el programador

Responde a: 5739f7f (H2-informe). Esto se suma a la `## Para el programador` de arriba. He visto
`eaffa3d`: no cambia nada de lo que pido aquí.

1. Haz **R7** (el §3 entero: migración 012, el `mensaje` hasta el servicio, la purga de D42 y sus
   pruebas) en H3, en commits propios. Va **antes** de la pasada completa de goldens y de los
   escenarios, para que E5 se pruebe ampliado.
2. Si la purga choca con algo de R3 (retirar una nota por similitud), **para y pregunta**.
3. **Para** en `H3-informe.md` como estaba previsto. Añade una tabla con lo que queda en
   `mem_hechos` y `mem_fuentes` después de E5.
