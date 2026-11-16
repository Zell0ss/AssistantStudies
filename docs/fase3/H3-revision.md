# H3 — revisión (fase 3)

> Responde a: d000e10 (H3-informe). 2026-11-16, arquitecto. La revisé contra el código de la rama
> `fase-3` en `d000e10`.

**Veredicto: no aprobado todavía. Haz una segunda vuelta (H3b) con los retoques de §3.** Hiciste
bien en parar: el informe es claro y las causas están bien vistas.

## 1. Lo que comprobé

- **Los retoques de prompt** (`3b267da`, `ee230f5`) son los del informe y no tocan otra cosa.
  A `salud` le falta un espacio («ahora.Varias») y otro («a"» + «esa tool») al final de una
  línea. Arréglalo en la misma pasada.
- **La causa de fondo de E10 está en el código, no en el modelo:**
  - `calendar_update_event` busca el evento por título exacto (`LOWER(title) = LOWER(%s)`).
  - `calendar_add_event` inserta sin mirar si ya existe uno igual.
  - Las notas y los compromisos ya van por `event_id`, y mover y crear siguen yendo por título.
  - Si el modelo escribe el título un poco distinto, `update` da `not_found`. Entonces el
    planner tira de `add_event` y sale un duplicado, que es la ejecución 3.
  - Si crea en vez de buscar, nada lo para, que es la ejecución 2.
  - Josem dictando por Telegram caería en lo mismo. Retocar las descripciones solas no basta.
- **Los goldens #68, #69, #71 y #72 los diseñé mal yo.** La historia dice «apuntado», pero la BD de
  test no tiene el evento, así que buscar primero y luego preguntar es lo correcto. Esos goldens
  medían ruido.

## 2. Decisiones que pedías

| # | Decisión |
|---|---|
| 1 | **Aísla #62, sí.** **#62 sigue en `exact` con `[mark_as_memorable]`, sin relajarlo.** «Olvida» tiene que llegar al camino de borrado aunque `search_memory` no encuentre nada, porque el texto puede estar en otro sitio. Es la promesa de privacidad de la fase 2. Mi primera sospecha es la frase «ante uno, no la llames» de `mark_as_memorable` y el «no es un dato de memoria» de `_REGLA_COMPROMISOS`. Si hace falta, añade a la regla «pedir que se olvide algo sigue siendo `mark_as_memorable`» |
| 2 | **Los cambio yo y tú los copias tal cual** (§4). Hacen falta sembrar estado (`estado:`, con una función nueva del harness), poner fecha explícita en #67 y aceptar `[]` en #76. **#74 no cambia:** dos `compromisos_crear` por una sola frase dejan pasos repetidos, como el troceado de E10. Es un fallo real |
| 3 | **Tus tres retoques de descripción, sí. Y además, dos cambios de código** (R2 y R3): mover por `event_id` y que crear no duplique |
| 4 | **Sí, una línea en `_ALFRED_SYSTEM`**: «Si el usuario cuenta un resultado o un diagnóstico médico, no ofrezcas guardarlo: Sebastian no los guarda». Prohíbe solo la oferta. Comentar el resultado sigue estando bien |
| 5 | **La subida a 6 $ la aceptó Josem en tu ventana, y vale**: la apunto en el ADR y en el diario. **La pasada completa final no se puede dar por hecha**, porque es lo que ha cazado #62. Haz H3b hasta justo antes de ella y **para** con el anexo y el gasto. La decide Josem (§5). Si E10 no llega a 3/3 tras esta vuelta, **para y cuéntalo**: no hay tercera vuelta sin pasar antes por mí |

## 3. Retoques de H3b

- **R2. `calendar_update_event` admite `event_id`** (opcional, y prioritario si viene).
  - **Descripción:** «Busca antes el evento con `calendar_search_events` y pasa su `event_id`».
  - `new_date`: «si el usuario da solo el día ("al 29"), el mes y el año son los de la fecha
    actual del evento, salvo que diga otros».
  - Con `not_found`, el resultado dice «no lo he encontrado: pregunta al usuario, no lo crees de
    nuevo».
  - **Pruebas:**
    - `test_update_event_por_id`.
    - `test_update_event_por_id_de_otro_usuario_no_toca_nada`.
    - Mover por id mueve los compromisos (D50), ya cubierto en H1: compruébalo con id.
- **R3. `calendar_add_event` no duplica.**
  - Si ya hay un evento del mismo usuario el mismo día y con el mismo título (sin distinguir
    mayúsculas), no inserta.
  - Devuelve `status: 'exists'` con su `event_id` y su hora. La descripción dice que, en ese
    caso, se use ese evento.
  - Solo el mismo día y el mismo título, nada difuso. Lo difuso va a la fase 4 si el uso lo pide.
  - **Pruebas:** `test_add_event_mismo_dia_y_titulo_devuelve_existente`, y una prueba de otro día
    o de otro título que sí inserte.
- **R4. Tus retoques de la decisión 3:**
  - «Busca antes si la cita ya existe» en `calendar_add_event`.
  - El año en `calendar_add_event`, igual que en R2.
  - En `compromisos_crear`: «un intervalo ("tres días antes y hasta la víspera") es **un solo**
    compromiso con `dias_inicio` y `dias_fin`».
- **R5. La línea de la decisión 4 en `_ALFRED_SYSTEM`.**
- **R6. #62:** aísla y arregla según la decisión 1.
- **Pruebas sin API:** todas en verde, contadas en el anexo.

## 4. Goldens (míos; cópialos tal cual)

**Mecanismo nuevo en el harness:** `estado:` es opcional en cada golden. Se siembra en
`sebastian_test` después de `_historial_limpio` y antes de la frase, con el mismo usuario.

```yaml
estado:
  eventos:
    - {titulo: "Endoscopia", fecha: "2027-01-28", hora: "09:30"}
  compromisos:            # opcional; atados al primer evento sembrado
    - {texto: "Primera toma del preparado", dias_inicio: -1, hora: "21:00"}
```

Pon `test_estado_se_siembra_y_se_limpia` sin API.

Cambios sobre `goldens.yaml`:

- **#67:** frase «El lunes 14 de diciembre empiezo la dieta blanda, tres días». El resto igual.
- **#68, #69:** se añade el `estado:` con el evento de arriba. Se mantienen la historia y las
  listas aceptadas.
- **#71:** `estado:` con un evento «Endoscopia» **mañana** a las 09:30 y el compromiso «Primera
  toma del preparado» con `dias_inicio: -1` y `hora: "21:00"`. Para eso el harness acepta
  `fecha: manana` y calcula la fecha al sembrar. Las listas aceptadas no cambian.
- **#72:** `estado:` con el evento de arriba. Añade `[calendar_search_events, calendar_update_event]`
  y ya está. **Lo que falla** es cualquier `calendar_add_event`.
- **#74:** `estado:` con el evento de arriba. Las listas aceptadas no cambian.
- **#76:** se añade `[]` a las aceptadas (preguntar en el texto vale). Lo que falla es
  `mark_as_memorable` o `salud`.

**E10:** sin cambios en el criterio. En el turno 5, el `calendar_update_event` tiene que llevar
`event_id`. Escríbelo en el resultado del escenario, sin que haga fallar la prueba: es para ver si R2
funciona.

## 5. Gasto y orden de los [API]

Gastado: **≈ 3,71 $ de 6 $.** Cada paso necesita el «sí» de Josem en tu ventana.

| Paso | Estimado |
|---|---|
| Aislar #62 (dos o tres pruebas de #62 ×3) | ≈ 0,3 $ |
| #56–#76 con `-k` | ≈ 0,6 $ |
| E10 ×3 | ≈ 0,5 $ |
| **Subtotal H3b** | **≈ 1,4 $ → ≈ 5,1 $ de 6 $** |
| Pasada completa #1–#76 (**no la lances**: la decide Josem) | ≈ 2,0 $ → ≈ 7,1 $ |

Para la pasada final hace falta un tope de **unos 7,5 $**. Se lo planteo yo a Josem. No la lances
hasta que te llegue su «sí» en tu ventana **y** mi revisión del anexo.

## Para el programador

Responde a: d000e10 (H3-informe)

H3 no aprobado aún. Haz **H3b**:
1. R2–R6 de §3, con sus pruebas sin API. Arregla también los dos espacios de `salud` (§1).
2. Goldens y `estado:` de §4, copiados tal cual. **#62 sigue en `exact`.**
3. Los [API] en el orden de §5, cada uno con el «sí» de Josem. **No** lances la pasada completa.
4. **Para** con un anexo al final de `docs/fase3/H3-informe.md`: resultados, gasto acumulado y si
   E10 lleva `event_id` en el turno 5. Si E10 no llega a 3/3, para y cuéntalo sin otra vuelta.

---

# Segunda revisión: anexo H3b

> Responde a: 6fe370f (Anexo H3b). 2026-11-16, arquitecto. La revisé contra el código en `7deb3bb`.

**Veredicto: H3 sigue sin aprobar. Haz una tercera vuelta (H3c).** El diagnóstico de #62 es muy
bueno: la palabra «olvida» de `compromisos_borrar` le quitaba los casos a `mark_as_memorable`.

## 6. Lo que comprobé

- **Pruebas sin API:** `pytest -m "not golden"` da **799 en verde**, lo mismo que el anexo.
- **R2:**
  - El `event_id` filtra por `user_id` y manda sobre el título.
  - Sin `title` ni `event_id`, la tool contesta `not_found`, que dice «no lo crees de nuevo».
- **R3:** solo mira el mismo día y el mismo título, sin distinguir mayúsculas, y devuelve el
  `event_id`. E10 lo confirma: **un solo evento en las tres ejecuciones**.
- **El fallo que queda es otro, y lo ves bien:** el planner busca y cierra el turno, y Alfred cuenta
  como hecho lo que no se hizo.
  - D44 solo vigila los turnos **sin ninguna** tool. Aquí sí hubo una, la búsqueda.
  - Eso es lo más grave del hito: rompe la promesa de honestidad (D26), no solo el camino corto.

## 7. Decisiones que pedías

| # | Decisión |
|---|---|
| 1 | **(b) y (a), sí. (c), no.** (c) obliga a que el código adivine si el mensaje pedía escribir, y eso sería otro clasificador. **(b) pasa a ser D54**, que extiende D44: si en el turno solo corrieron tools de lectura, Alfred lo sabe. **(a):** `calendar_add_note` admite `title` y `date`, como `calendar_update_event`, y el `event_id` sigue mandando. Así, el paso que más falla se hace con una sola llamada. Añade también **R9** (§8), que es una línea de prompt |
| 2 | **#40 es culpa del golden, no del código.** Con la fase 3, «recuérdame comer a las 2» es un compromiso o una pregunta por el día. Lo único que falla sigue siendo `salud`. Lo cambio yo (§9). **#50 hay que diagnosticarlo** (R10): es el modo «el planner no llama a nada», el mismo de #67 |
| 3 | **#76: acepto `[calendar_search_events]`.** Buscar la cita y preguntar en el texto vale, y con D54 Alfred no puede fingir que la apuntó. **#74 sigue igual.** El modo «sin tool» de #67 y #50 se diagnostica en R10 antes de tocar nada |
| 4 | **La pasada completa sigue siendo obligatoria antes de H4.** El tope lo decide Josem; mi estimación está en §10 |
| 5 | **Apuntada como D55 (vigente):** cada familia nueva de tools dice en su descripción qué **no** es suyo, sobre todo los verbos que ya tiene otra familia. Gracias |

## 8. Retoques de H3c (sin API)

- **R7 (D54). Turno con solo tools de lectura.**
  - Escribe en el código un conjunto explícito de tools de solo lectura: `*_search*`, `*_list*`,
    `calendar_find_by_datetime`, `calendar_get_tickets`, `search_memory`, `consult_docs`, etc.
  - Ponlo junto a `_TURNO_SIN_HERRAMIENTAS`, con una prueba que obligue a clasificar toda tool nueva:
    `test_toda_tool_esta_clasificada_lectura_o_escritura`.
  - Si el turno solo ejecutó tools de ese conjunto, después del mensaje va una nota hermana de la
    de D44: «[En este turno solo has consultado (…): no has guardado, cambiado, borrado, apuntado ni
    creado nada. Si el usuario pedía un cambio, dile que no lo has hecho y ofrécete a hacerlo.]»
  - Pruebas sin API:
    - Con solo una búsqueda, la nota está.
    - Con una búsqueda y una escritura, no está.
    - Sin ninguna tool, sigue la de D44.
- **R8. `calendar_add_note` por título y día.**
  - `event_id` es opcional y manda. Si no viene, se busca por `title` y `date`, igual que en R2.
  - Si hay más de un evento y no viene `date`, devuelve `ambiguous` con los candidatos, sin escribir.
  - Con `not_found`, el mismo texto de R2.
  - Pruebas: por id, por título y día, ambiguo, y de otro usuario.
- **R9. Una línea en `_REGLA_ACCIONES_CON_HISTORIAL`** o justo detrás:
  - «Buscar no termina el turno. Si el usuario pidió cambiar algo (una cita, su nota, un compromiso)
    y la búsqueda lo encontró, llama en este mismo turno a la tool que lo cambia».
  - Es la misma forma que ya funcionó en D43.
- **R10. Diagnóstico del modo «sin tool»** ([API], barato):
  - Guarda en la salida de los goldens el texto del planner cuando cierra sin tools. Va solo al
    informe del test, nunca al log (D42).
  - Ejecuta #50 y #67 ×3 y cuenta qué dice.
  - Si la causa es clara y se arregla con una línea de prompt, arréglala. Si no, trae las salidas.

## 9. Goldens (míos; cópialos tal cual)

- **#40:**
  - `expected: [[calendar_add_event], [], [compromisos_crear], [request_clarification]]`.
  - `validates: "Fase 3: «recuérdame» es compromiso, cita o pregunta por el día; lo único que falla es salud"`.
- **#76:** añade `[calendar_search_events]` a las listas aceptadas.
- **#62:** sin cambios, sigue en `exact`.

## 10. Gasto y orden de los [API]

Gastado: **≈ 5,50 $ de 6 $.** Para todo lo que falta no llega.

| Paso | Estimado |
|---|---|
| R10: #50 y #67 ×3 | ≈ 0,15 $ |
| Tanda: #40, #50, #56–#76 | ≈ 0,8 $ |
| E10 ×3 | ≈ 0,5 $ |
| Pasada completa #1–#76 (solo si lo anterior pasa) | ≈ 2,1 $ |
| **Total de H3c** | **≈ 3,5 $ → ≈ 9 $ en la fase** |

**Lo sin API (R7–R9 y §9) hazlo ya.** No lances ningún [API] hasta que Josem suba el tope y te
dé el «sí» en tu ventana. Se lo planteo yo ahora.

**Criterio para cerrar H3:**
- E10 en 3/3.
- La tanda verde, salvo los intermitentes conocidos (#28 y #43), repetidos ×3.
- Luego, la pasada completa sin ningún golden antiguo en rojo.

Si E10 sigue por debajo de 3/3, para. En ese caso, lo siguiente es reducir el alcance de H4, no
otra vuelta de prompts.

## Para el programador

Responde a: 6fe370f (Anexo H3b)

H3 aún no aprobado. Haz **H3c**:
1. R7–R9 de §8, con sus pruebas sin API. Copia tal cual los goldens de §9.
2. **Espera** a que Josem suba el tope y te dé el «sí» en tu ventana. Después lanza los [API] en
   el orden de §10, empezando por R10.
3. La pasada completa solo si la tanda y E10 pasan.
4. **Para** con un segundo anexo al final de `docs/fase3/H3-informe.md` («Anexo H3c»).

---

# Tercera revisión: anexo H3c

> Responde a: 9fb1df0 (Anexo H3c). 2026-11-16, arquitecto. La revisé contra el código en `fd0851d`.

**Veredicto: H3c aprobado en lo que hace.** Para cerrar H3 falta un último paso, cerrado y sin más
vueltas de prompts (§13). D54 funciona: Alfred ya dice «solo he consultado» en vez de inventarse
el cambio.

## 11. Lo que comprobé

- **Pruebas sin API:** `pytest -m "not golden"` da **833 en verde**.
- **`_TOOLS_DE_LECTURA`/`_ESCRITURA`** son conjuntos explícitos, y la prueba obliga a clasificar
  cada tool nueva.
- **Vale `request_clarification` entre las de lectura:** el orquestador la intercepta antes de la
  síntesis, así que nunca llega a la nota.
- **El tope de 8 $ lo puso Josem en tu ventana.** Lo apunto en el ADR.

## 12. Decisiones que pedías

| # | Decisión |
|---|---|
| 1 | **#67: acepto `[request_clarification]` y `[]`.** Preguntar de más molesta, pero no hace daño, y con D44/D54 Alfred no finge haberlo hecho. **Riesgo conocido para la fase 4:** cuando el planner cierra con una pregunta en texto, esa pregunta se pierde y Alfred solo dice «no he podido registrar nada». Pasará a la fase 4 junto con el «busca y se para» del turno 3 de E10 (2 de 3), que también es del bucle del planner |
| 2 | **#71: acepto** `[compromisos_listar, compromisos_completar, compromisos_listar]` |
| 3 | **La segunda toma: sí, es lo más importante del anexo.** Es justo el aviso de las 01:00 que falsa D48: con `dias_inicio = -1` llegaría 24 h antes. Hacen falta R11 (descripción) y R12 (comprobación en E10, normativa). Si aun así falla alguna de las tres, **no hay otra vuelta**: H4 sigue con la mitigación de §14 |
| 4 | **La pasada completa va, pero después de R11.** Lanzarla antes no tiene sentido, porque R11 toca el prompt. El tope lo decide Josem (§13) |
| 5 | **De acuerdo:** no se despliega sin la pasada completa |

## 13. Último paso de H3

- **R11.** En `compromisos_crear`, en la descripción de `dias_inicio`/`dias_fin`:
  - El día 0 es el de la cita.
  - Una hora de madrugada que el usuario ata al día de la cita («el mismo día a la una», «la
    noche antes, a la una») es `dias_inicio = 0` con esa hora.
  - `-1` es el día anterior, a esa hora del reloj.
  - Prueba sin API del texto.
- **R12.** En E10, una comprobación **normativa**: el compromiso de la segunda toma lleva
  `dias_inicio = 0` y `hora = 01:00`. No cambies la frase de E10, que es la del caso real.
- **Goldens de §12:** #67 con `[]` y `[request_clarification]`; #71 con la secuencia de arriba.
- **[API], en este orden:**
  1. E10 ×3 (≈ 0,55 $).
  2. La pasada completa #1–#76 (≈ 2,1 $).
  - En total, ≈ 2,65 $ sobre ≈ 6,88 $, es decir, **≈ 9,5 $ en la fase**. Con el tope de 8 $ no
    entra: Josem tiene que subirlo a 9,5 $ antes del primer [API].
- **Criterio de cierre de H3:**
  - En la pasada completa, ningún golden antiguo en rojo, salvo #28 y #43, que se repiten ×3.
  - Los nuevos pasan.
  - E10 en 3/3 por el criterio. La comprobación de R12 se cuenta, pero **no bloquea** (§14).

## 14. Riesgos que se aceptan para H4 (y su mitigación)

- **La segunda toma un día antes.** Si R12 no da 3/3:
  - Josem dicta la preparación con fechas absolutas («el jueves 17 a la una de la madrugada, la
    segunda toma»). Ajustaré yo el mensaje 3 de su nota.
  - Después del dictado, compruebo en `sebastian_db` cada compromiso contra el caso.
  - Además, Alfred repite cada paso con su fecha calculada, así que un error se ve al momento.
- **«Busca y se para»** en la nota de la cita: ahora Alfred lo dice y Josem repite la orden. Pasa
  a la fase 4.

## Para el programador

Responde a: 9fb1df0 (Anexo H3c)

H3c aprobado. Último paso de H3:
1. R11, R12 y los goldens de §12, con sus pruebas sin API.
2. **Espera** a que Josem suba el tope a 9,5 $ y te dé el «sí». Lanza E10 ×3 y después la
   pasada completa, en ese orden.
3. **Para** con «Anexo H3d» al final de `docs/fase3/H3-informe.md`. Si se cumple el criterio de §13,
   el siguiente hito es H4.

---

# Cuarta revisión: anexo H3d. H3 se cierra

> Responde a: 0580897 (Anexo H3d). 2026-11-16, arquitecto.

**Veredicto: cierro H3 con tres riesgos aceptados y un retoque de código sin API (R13).** El
criterio de §13 no se cumple al pie de la letra, y lo digo así. Ninguno de los tres rojos pide
otra vuelta de prompts, y ya dije que no la habría. Dos se cubren con código y con la revisión de la
BD tras el dictado. El tercero era culpa del golden. R11 funciona: la segunda toma cae en el día 0
en 3 de 3, y era el riesgo principal del caso.

## 15. Decisiones que pedías

| # | Decisión |
|---|---|
| 1 | **#73: riesgo aceptado, con regla de uso.** Josem no le cuenta resultados médicos a Sebastian; el caso solo dicta fechas y pasos. **Nada de guardia por código:** distinguir un resultado de un síntoma por el texto es tan difuso como el prompt, y daría falsos rechazos en `salud`. Lo que importa: en producción ese texto llegaría a Tristras, no a Sebastian. Si Tristras debe aceptar resultados o no lo decide su registro, y llevo allí la pregunta de D52, que sigue pendiente. Queda anotado en el ADR |
| 2 | **#49: amplío el golden y no lo repito.** Mirar el inventario o la memoria antes de proponer una cena es una lectura inofensiva, y hasta útil. Lo que falla es escribir algo, sobre todo `salud`. Lista nueva: `[[], [inventory_list], [search_memory], [inventory_list, search_memory], [search_memory, inventory_list]]` |
| 3 | **E10 turno 5: sí al arreglo por código (R13) y a la mitigación de §14.** Es el mismo patrón de R3, que funcionó: crear no duplica |
| 4 | **H4 sigue adelante.** El despliegue lo decide y lo hace Josem. Mi recomendación es desplegar tras R13, porque el plazo del 10/12 deja margen para la prueba real |

## 16. R13 y lo que falta para H4 (todo sin API)

- **R13.** `compromisos_crear` no duplica.
  - Si un compromiso del lote coincide en texto con uno **pendiente** del mismo usuario y el mismo
    `evento_id`, no se inserta. El texto se compara normalizado: sin mayúsculas, sin espacios de
    los extremos y con los espacios internos colapsados.
  - En la salida, ese compromiso va como `ya_existe` con su id y su momento. El resto del lote sí
    se crea.
  - La descripción dice: «si la cita se ha movido, sus pasos ya se movieron solos (D50): no los
    crees otra vez».
  - Sin `evento_id`, no se compara: los sueltos pueden repetirse, como un «comprar pan» de dos días.
  - Pruebas:
    - `test_crear_no_duplica_pendiente_del_mismo_evento`.
    - `…_si_el_otro_esta_hecho_o_cancelado_si_crea`.
    - `…_otro_evento_si_crea`.
    - `…_lote_mixto`.
- **El golden #49** de §15.
- **H4, preparación (PLAN §3-H4):**
  - `deploy/comprobar_fase3.sh`.
  - `deploy/PASOS-CON-SUDO.md`, con la sección de la fase 3: migración `013` en `sebastian_db`,
    `ff-only` de `fase-3` en `/data/AssistantStudies` y reinicio. Añade también la vuelta atrás:
    el commit de ahora en `main` y que `013` solo crea una tabla, así que deshacerla es un `DROP`
    que **no** se ejecuta sin preguntar.
- **Ningún [API] más en la fase 3.** Quedan ≈ 0,41 $ de los 10 $ que autorizó Josem. La prueba de
  R13 con el modelo será la real.

## 17. Gasto

**≈ 9,59 $ de 10 $.** Josem fue subiendo el tope en tu ventana: 6, 8, 9,5 y 10 $. Queda en el ADR y
en el diario.

## Para el programador

Responde a: 0580897 (Anexo H3d)

H3 cerrado con riesgos aceptados (§15). Antes de H4:
1. R13 y el golden #49 de §16, con sus pruebas sin API.
2. `deploy/comprobar_fase3.sh` y la sección de la fase 3 de `deploy/PASOS-CON-SUDO.md`, con su
   vuelta atrás.
3. **Ningún [API].** No fusiones, no migres y no reinicies: eso lo hace Josem.
4. **Para** con `docs/fase3/H4-informe.md`, con lo que Josem tiene que ejecutar y en qué orden.
