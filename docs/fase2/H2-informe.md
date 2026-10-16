# H2 (fase 2) — Informe: escritura de la memoria

Responde a: 16382e2 (H1-revision, «Para el programador»)

## Hecho

Commits: `9300aa6` (resolución, hechos con vigencia, registro de decisiones), `51fc60c` (extractor,
`ServicioMemoria.guardar`, la tool con el contrato nuevo), `92ce116` (harness de goldens y los 10 casos),
y el de este informe (arreglo de `temperature` y salidas). **521 tests en verde** (sin API) y **10/10 casos del
extractor y 5/5 goldens** con la API.

- **`core/memoria/resolucion.py`** (funciones puras, D8, D35): `resolver_entidad`, `resolver_atributo`
  (alias exacto → semántica con puntuación y margen → crear; el tipo incompatible es resolución débil) y
  `decidir_hecho` con las reglas del plan (`anadir`, `sustituir`, `retirar`, `nota`, `sin_cambio`). Los
  umbrales son los de H1 (0,58/0,03 y 0,68/0,05, `config.memoria.umbrales`).
- **`repositorio.py`:** `anadir_hecho`, `sustituir_hecho` (una transacción: cierra el viejo, abre el
  nuevo y enlaza `superseded_by`; si el INSERT falla, el viejo sigue vigente), `retirar_hecho`,
  `hechos_vigentes`, `hechos_historial`, `registrar_decision` y los alias para el prompt.
- **`extractor.py`** (D32): Haiku 4.5 con `tool_choice` forzado a `registrar_hechos`. Esquema del plan más
  `ejemplos` (como mucho 3, H1-revision §2.2), máximo 8 hechos, y validación y recorte en código.
  **El prompt va en `core/memoria/prompts/extractor_hechos.md`**: el repo no tenía patrón de prompts en
  ficheros (todo está inline en `orchestrator.py`), así que lo creé para este.
- **`servicio.py`:** `guardar(user_id, texto)` hace extractor → resolución → escritura → `mem_decisiones`, embebe
  las `nota` en `<base>_notas` (payload `{hecho_id, user_id}`, sin el texto) y devuelve el contrato del §2.2.
  `texto_catalogo` arma el catálogo del usuario para el extractor (sus entidades y todos los atributos con
  descripción y alias). `desde_config` lo construye de `memory_collection` (D34, D19, D20).
- **La tool:** `mark_as_memorable` pasa a `{texto}`, con la descripción «cuándo sí y cuándo no» (la frontera
  de #20, #22 y salud). `FAMILY_SUMMARY` sin recordatorios (lo comprueba un test). `_ALFRED_SYSTEM` lleva la
  línea de D16 (`nuevos_pendientes`, `sustituye`, y no afirmar lo que quedó en `notas`). El extractor informa
  de su uso a `_track_usage` mediante `ToolExecutor(on_usage=…)`.
- **Privacidad:** `mark_as_memorable` y `search_memory` entran en `_TOOLS_SIN_LOG_DE_CONTENIDO`.
  `test_log_no_lleva_valores` (servicio, repositorio y catálogo) y las pruebas del ejecutor comprueban que ni
  el texto ni el valor van al log. `mem_decisiones.detalle` y `senales` llevan ids y reglas, nunca valores.
- **Harness de goldens:** recrea `<base>_catalogo` y `<base>_notas` en cada sesión, indexa las semillas y limpia
  las filas `mem_*` del usuario de goldens antes de cada golden.

### Pruebas normativas del plan

| Grupo | Pruebas | Estado |
|---|---|---|
| Resolución (puras) | las 9 del plan (`test_varios_anade` … `test_tipo_incompatible_es_debil`) y 11 más | verdes |
| Repositorio | `test_sustitucion_es_atomica`, `test_nada_se_borra`, `test_superseded_by_apunta_al_nuevo` y 5 más | verdes |
| Servicio (extractor y embedder falsos) | `test_guardar_devuelve_contrato`, `test_atributo_nuevo_queda_pending_y_se_informa`, `test_cada_decision_queda_en_log` y 11 más | verdes |
| Privacidad | `test_log_no_lleva_valores` y las del ejecutor | verdes |
| [API] extractor | los 10 casos, una vez cada uno | **10/10** |
| [API] goldens de frontera | #20, #21, #22, #30, #36 | **5/5** |

### Los 10 casos del extractor (salida completa en `docs/fase2/goldens/2026-10-16-extractor-10-casos.txt`)

| # | Frase | Lo que devolvió |
|---|---|---|
| 1 | Paco alérgico | Paco (persona) · `alergia` · «frutos secos» · afirmar |
| 2 | presión 2,4 | coche (vehiculo) · `presion_neumaticos` · «2,4 bares» · corregir |
| 3 | olvida camisetas UV | «camisetas UV» (objeto) · `nota` · retirar |
| 4 | saxhero en GitHub | saxhero (proyecto) · **`nota`** · «No publicado en GitHub de momento» · afirmar |
| 5 | cumpleaños 12 de marzo | yo · `cumpleanos` · `--03-12` · afirmar |
| 6 · 7 | «Qué tal estás» · «Tengo hambre» | `[]` |
| 8 | Paco y Ana hermanos | 2 hechos, `parentesco`: «hermano de Ana» y «hermana de Paco» |
| 9 | ya no vivo en Gijón | yo · `lugar_residencia` (nuevo, con descripción y 3 ejemplos) · «Oviedo» · corregir |
| 10 | talla de camisa | yo · `talla_camisa` (nuevo) · «M» · afirmar |

Lo que hay que mirar: en el 4 el extractor **no creó un atributo de publicación** y usó `nota`; el plan
admite cualquier atributo, así que el test pasa, pero conviene saberlo. En el 3, la retirada apunta a la
entidad «camisetas UV», que no existe (ver Decisiones §1).

Los 5 goldens (`2026-10-16-goldens-memoria-20-21-22-30-36.txt`): #20 llama a `mark_as_memorable` y Alfred dice
«He abierto una ficha para él; avíseme si desea añadir algo más» (la línea de D16 funciona); #22 sigue en la
lista de la compra y #30 y #36 siguen en `salud`. (En #30 y #36 Alfred dice «problema técnico»: Tristras está
neutralizado en los goldens, D27.)

## Gasto

Tope de la fase: 5 $, entre Anthropic y OpenAI (autorizado por Josem el 2026-10-15).

| Qué | Anthropic | OpenAI |
|---|---|---|
| 10 casos del extractor (Haiku 4.5: 23 936 entrada, 1 015 salida) | 0,0290 $ | 144 tokens |
| 5 goldens (Haiku 4.5: 82 935 / 815; Sonnet 4.6: 5 194 / 196) | 0,1055 $ | 143 tokens |
| Calibraciones de H1 | 0 $ | 0,00002 $ + < 0,001 $ |
| **Total de H2** | **0,1345 $** | **≈ 0,00001 $** (287 tokens × 0,02 $/millón, medido) |

**Acumulado de la fase 2: ≈ 0,136 $ de 5 $.** El primer intento de lanzar el extractor falló antes de enviar
nada (ver Desviaciones §3): no costó nada.

## Desviaciones

1. **Defecto de H1 en la migración 011 (arreglado):** el nombre canónico de cada semilla no era alias de sí
   mismo (`atributos_por_alias("nota")` salía vacío). Añadí a 011 un `INSERT IGNORE` con `nombre` como alias
   (10 alias más) y `test_cada_semilla_se_resuelve_por_su_nombre`. Reaplicada a `sebastian_test` y
   `sebastian_dev`; sigue siendo idempotente.
2. **`ToolExecutor` y `Orchestrator` cambian de firma** (`on_usage`) para que el uso del extractor llegue a la
   telemetría del turno. Por eso cambié `test_accepts_config_override_and_passes_to_tool_executor`
   (comprueba la config y que `on_usage` llega a `_track_usage`) y los tests de `mark_as_memorable` de
   `test_tool_executor.py` (el contrato `{content, tags}` ya no existe). No toqué ninguna prueba normativa del
   plan.
3. **`anthropic` 1.14 ya no acepta `temperature` en `messages.create`.** Lo vi al lanzar el extractor por
   primera vez: `TypeError` antes de enviar nada, 0 $. Lo quité (el cliente falso de los tests no lo
   detectaba; el test ahora comprueba que no se envía). Una nota para H3: ningún otro parámetro de
   muestreo.
4. **Cada hecho es su propia transacción**, no todo `guardar` en una: el plan dice que `servicio.guardar` «hace
   la transacción», pero una frase con dos hechos (caso 8) queda a medias si el segundo falla. Lo que sí es
   atómico es lo que importa: sustituir (cerrar el viejo y abrir el nuevo). Si quieres una sola, es un
   cambio pequeño.
5. **La nota se embebe después de confirmar en SQL.** Si falla el embedding, la nota queda guardada sin
   vector, con un `warning` sin contenido; no se pierde el dato.
6. **El «yo» sin `username` se llama `yo`**, no el id de Telegram (`entidad_usuario` cae en `yo`). El
   ejecutor solo conoce el `user_id`.
7. **`confianza`** = la menor de las puntuaciones de las dos resoluciones (alias exacto 1,0; semántica, su
   puntuación; lo creado en el turno no resta). Va también en `senales`.
8. **`search_memory` sigue siendo el de Sprint 3 hasta H3.** Hasta entonces, lo que escribe
   `mark_as_memorable` no lo encuentra `search_memory` (#21 pasa porque lee la colección vieja sembrada).
   La rama no se despliega hasta H4.
9. **`ejemplos`** está en el esquema como pediste, pero con la representación (a) no se embebe ni se guarda.

## Decisiones que necesito

1. **Retirar algo que se guardó como texto libre.** «Olvida lo de las camisetas UV» (caso 3) hace que el
   extractor proponga la entidad «camisetas UV» con atributo `nota`; como esa entidad no existe, el
   servicio responde «no he encontrado qué olvidar» y no crea nada. Si antes se había guardado «las camisetas
   UV me van bien» como `nota`, esa nota no se puede retirar todavía. La solución natural es que, ante un
   `retirar` sin entidad, busque en `<base>_notas` por similitud y cierre la nota que encaje. ¿Lo hago en
   H3, o lo dejamos como límite conocido?
2. **Entidades y atributos `pending`.** Alfred dice «dígame si prefiere otro nombre», pero hoy no hay
   forma de renombrar ni de confirmar un pendiente. ¿Es para la fase 3, o hace falta una tool pequeña en esta?
3. **El caso 4** (saxhero → `nota` en lugar de un atributo de publicación). Si quieres que el extractor
   prefiera crear atributos cuando el hecho es una decisión, es un retoque del prompt (otra pasada de los 10
   casos, ≈ 0,03 $). Si te vale, lo dejo.

Paro aquí. No empiezo H3 hasta tu revisión.
