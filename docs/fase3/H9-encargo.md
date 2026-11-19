# H9 — encargo (fase 3, parche): las fechas por el día de la semana y la búsqueda por palabras

> Responde a: 93f3350 (H8-informe; tras él va mi H8-revision, `b735ca6`). 2026-11-19, arquitecto. Decisiones: **D60, D61 y D62** (ADR-MEMORIA §4).
> El tope de la fase sigue en **11,50 $**, y van ≈ 10,57 $. Este parche no debe pasar de **0,45 $**.

## 1. Qué pasó en producción (19/11, jueves)

1. «Este viernes tengo cena de Navidad de BNP… a las 20:30». A las 08:06, `calendar_add_event` creó el evento 4947, «Cena de Navidad BNP - TBC», para el **27/11** y no para el 20/11. El planner solo ve «Hoy es 2026-11-19 y son las 08:06.» (`core/orchestrator.py:105`), sin el día de la semana.
2. A las 08:08, «Dame mi calendario para esta semana» listó del 19 al 25 y no mostró la cena, porque estaba el 27. Alfred dijo «no la veo… puede que no quedara guardada. ¿La anoto?».
3. A las 08:34, «Mueve la cena de Navidad de BNP al viernes 20…»: `calendar_search_events` dio **0 resultados**. `LIKE '%frase%'` (`modules/calendar.py:674`) exige que la frase aparezca tal cual en el título. Lo que buscó el planner no está en el log, porque solo sale en DEBUG. Mi hipótesis es «cena de Navidad de BNP», con el «de» de más. Alfred volvió a decir «parece que no llegó a guardarse» y ofreció crearla, lo que habría dejado un duplicado.

## 2. Requisitos

### R22 — la fecha con el día de la semana y los próximos 14 días (D60)

- Una función, por ejemplo `_contexto_fecha(ahora=None)`, sustituye a `_now_str()` en sus tres usos (`orchestrator.py:154`, `:678` y `:685`). Así el planner y Alfred ven lo mismo. El reloj se puede inyectar para las pruebas.
- El texto, más o menos: `Hoy es jueves 2026-11-19 y son las 08:06.`, y después una línea con hoy y los 13 días siguientes, día de la semana y dd/mm: `Próximos días: hoy jueves 19/11, mañana viernes 20/11, sábado 21/11, … miércoles 2/12.` Los nombres de los días van en una tupla en español escrita en el código, **sin `locale`**.
- En el `system` del planner, junto a `_REGLA_COMPROMISOS`, una frase: «"este viernes", "el lunes", "el martes que viene": toma la fecha de la lista de próximos días. "Este X" es el próximo X que aún no ha pasado. No calcules el día de la semana.» Vale para eventos y para compromisos.
- **Pruebas sin API, con el reloj en el jueves 2026-11-19 a las 08:06:**
  - El texto contiene `jueves 2026-11-19`, `viernes 20/11` y `miércoles 2/12`, y tiene exactamente 14 días.
  - Con el reloj en el sábado 2026-11-28, la lista cruza al mes siguiente: contiene `lunes 30/11` y `martes 1/12`.
  - El `system` del planner y el prompt de Alfred llevan el mismo texto de fecha.
  - Las tools de `_PLANNER_TOOLS` no cambian, porque D59 sigue en pie.

### R23 — búsqueda por palabras (D61)

En `CalendarModule.search_events(query)`:

- **Normaliza** la consulta y los títulos: minúsculas, sin acentos (NFD y quitar los diacríticos) y troceados por lo que no es letra ni número.
- **Palabras vacías:** se quitan `de, del, la, las, el, los, en, a, al, y, con, para, por, un, una, mi, mis`. También las palabras de menos de 2 caracteres.
- **Si no queda ninguna palabra** (consulta vacía o solo con palabras vacías), se mantiene lo de hoy. `search_events("")` sigue devolviendo todos los eventos (lo usa `tests/test_calendar_module.py:364`).
- **Primer nivel:** los eventos cuyo título contiene **todas** las palabras (como subcadena del título normalizado). Si hay alguno, se devuelven solo esos.
- **Segundo nivel, solo si el primero está vacío:** los eventos que contienen **alguna** palabra, ordenados por cuántas coinciden (de más a menos) y después por fecha. Cada uno lleva `coincidencia: "parcial"`. Los del primer nivel no llevan esa clave, o llevan `"completa"`; elige tú y dilo en el informe.
- La forma de los recurrentes (la próxima ocurrencia) y la de cada evento no cambian, salvo la clave nueva.
- Si filtras en Python sobre los eventos del usuario en vez de en SQL, vale: son pocos. Dilo en el informe.
- **`bot/ticket_handler.py:166`** también llama a `search_events(caption)`. Mira si le afecta que ahora encuentre más, sobre todo si coge el primero de los parciales. Si le afecta, dímelo; no lo arregles por tu cuenta.
- La descripción de `calendar_search_events` (D55) dice: «busca por palabras del título; usa una o dos palabras clave. Un resultado con `coincidencia: "parcial"` puede no ser el evento: no lo muevas ni lo borres sin confirmarlo con el usuario. Cero resultados no quiere decir que no exista: prueba con otra palabra o con `calendar_list_events` del rango.»
- **Al log de INFO** va solo el tamaño de la consulta, nunca el texto (D42), por ejemplo `query_chars=22 palabras=3`. Puede ir en la línea `Tool calendar_search_events → …` o en una aparte.
- **Pruebas sin API** (BD de test, como `test_calendar_module.py`):
  - «cena de Navidad de BNP» encuentra «Cena de Navidad BNP - TBC», en el primer nivel.
  - «BNP» la encuentra.
  - «cena navidad» la encuentra (mayúsculas y acentos).
  - «revision» encuentra «Revisión dental».
  - Con solo ese evento, «cena con Ana» lo devuelve marcado `parcial`.
  - Con «Cena de Navidad BNP» y «Cena con Ana», «cena con Ana» devuelve solo «Cena con Ana», en el primer nivel.
  - «xyz inexistente» devuelve `[]`.
  - `""` devuelve todos.
  - Las pruebas que ya existen en `test_calendar_module.py` pasan sin tocarlas.
  - El texto de la consulta no aparece en ningún log (captura de loguru).

### R24 — Alfred no inventa el porqué (D62)

- En `_ALFRED_SYSTEM`, una línea con este sentido: «Si no encuentras algo que el usuario da por hecho (un evento, un compromiso), di que no lo encuentras con esa búsqueda, sin suponer por qué. No digas que no se guardó. Si ofreces crearlo, avisa de que podría quedar duplicado.»
- Nada más en Alfred. La regla general de la familia de D43 va a la fase 4.

## 3. Goldens nuevos

Adapta la forma al arnés, como en H7. El arnés ya fija `ahora:` por golden. Para comprobar la fecha de `calendar_add_event` y `calendar_update_event`, y para `alfred_no_menciona`, amplía el arnés de la forma más pequeña posible (como `crea_con_fecha`) y cuéntalo.

```yaml
- id: 81
  phrase: "Este viernes tengo cena de Navidad de BNP. Es en calle de las Huertas 41, Madrid, a las 20:30"
  ahora: "2026-11-19T08:06"          # jueves
  expected: [calendar_add_event]
  entrada: {date: "2026-11-20", time: "20:30"}
  alfred_menciona: ["20"]
- id: 82
  phrase: "El lunes a las 10 tengo dentista"
  ahora: "2026-11-19T08:06"          # jueves → lunes 23
  expected: [calendar_add_event]
  entrada: {date: "2026-11-23", time: "10:00"}
- id: 83
  phrase: "El miércoles a las 9 tengo reunión con el gestor"
  ahora: "2026-11-21T12:00"          # sábado → miércoles 25
  expected: [calendar_add_event]
  entrada: {date: "2026-11-25", time: "09:00"}
- id: 84
  phrase: "Mueve la cena de Navidad de BNP al viernes 20 de noviembre a las 20:30"
  ahora: "2026-11-19T08:34"
  estado: {eventos: [{titulo: "Cena de Navidad BNP - TBC", inicio: "2026-11-27T20:30"}]}
  expected: [calendar_search_events, calendar_update_event]
  entrada_update: {new_date: "2026-11-20"}
  alfred_no_menciona: ["no llegó a guardarse", "no se guardó", "no quedó guardada", "no quedara guardada"]
- id: 85
  phrase: "¿Cuándo es la cena con los de la uni?"
  ahora: "2026-11-19T09:00"
  estado: {eventos: [{titulo: "Cena de Navidad BNP - TBC", inicio: "2026-11-20T20:30"}]}
  # Pasa si no da la cena de BNP por la de la uni sin más (puede mencionarla como posible) y no dice que algo no se guardó.
  expected_any: [calendar_search_events, calendar_list_events]
  alfred_no_menciona: ["no llegó a guardarse", "no se guardó", "no quedó guardada"]
  validates: "D61 (parcial) y D62"
```

En #85, «no da la de BNP por la de la uni» lo puedes comprobar con `alfred_no_menciona: ["su cena con los de la uni es"]` o con algo parecido que sea objetivo. Si no ves forma de hacerlo, quédate solo con la parte de «no se guardó» y dilo.

## 4. [API] y gasto (cada paso, con el «sí» de Josem en tu ventana)

1. Los goldens **#81–#85, 3 veces cada uno**.
2. **Regresión de fechas y calendario, 1 vez:** los goldens que usan `calendar_*` o `crea_con_fecha*`, y entre ellos #79 y #80. No hace falta la pasada completa.

Informa del gasto por modelo. Si al acabar el paso 1 vas por más de 0,30 $, para y avisa antes del paso 2.

## 5. Lista previa (§4)

- **¿Borra o sobrescribe datos?** Las pruebas de R23 escriben eventos en la BD de **test**, la misma que usa `test_calendar_module.py`. Los goldens usan su `estado` aislado. Nada de `sebastian_db`.
- **¿Llama a una API externa?** Sí, a los mismos modelos de hoy (Haiku 4.5 en el planner y Sonnet 4.6 en Alfred), sin cambiar nada. La lista de días añade unos 100 tokens al `system`, que ya no está en caché (D59), así que la caché de las tools no se toca. El coste lo da el §4.
- **¿Toca producción?** Solo al desplegar, y lo hace Josem: ff-only y reinicio. El evento 4947 sigue el 27/11: **no lo toques**. Cuando esté desplegado, lo moverá Josem por Telegram, y esa será la prueba de producción.

## 6. Dónde parar

Cuando estén R22–R24, la suite sin API y los pasos de §4 (si Josem los autoriza), escribe `H9-informe.md` y para. Si algo no encaja con el código, para antes y pregunta.

## Para el programador

Responde a: 93f3350 (H8-informe). Después de tu informe va mi `H8-revision.md` (`b735ca6`), que aprueba H8.

1. Haz R22, luego R23 y después R24, cada uno con sus pruebas sin API.
2. Amplía el arnés y añade los goldens #81–#85.
3. Pasa la suite completa.
4. Pide a Josem el «sí» para el §4 y ejecútalo.
5. Escribe `docs/fase3/H9-informe.md` y para.
