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
