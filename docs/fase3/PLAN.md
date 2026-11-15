# Plan de la fase 3 — Prospectiva: Sebastian habla primero

> Arquitecto, 2026-11-15. `plan: arquitecto`, porque la fase crea contratos: una tabla, cuatro
> tools, dos tareas del planificador y el formato del resumen y de los avisos. Decisiones en
> `30-projects/sebastian/ADR-MEMORIA.md` §4 (D45, D47, D48 y las de este plan, D49–D52). Caso de
> diseño en `30-projects/sebastian/CASO-COLONOSCOPIA.md`. Diario en `DIARIO-FASE-3.md`.

## 0. Qué entra y qué no

**Entra (D45):**
- **Compromisos:** cosas que Josem tiene que hacer. Tienen día, y a veces hora o un intervalo de
  días. Pueden ir **atados a un evento del calendario** y se mueven con él.
- **El resumen de las 08:00**, que ya existe (`bot/scheduler.py`) y hoy solo trae la agenda.
  Añade los compromisos del día y lo que cae antes del próximo resumen. Si no hay nada, calla
  (D47).
- **Avisos a su hora (D48):** una tarea nueva del planificador del bot manda por Telegram cada
  compromiso con hora cuando le llega el momento.
- **Los datos de una cita** (lugar, teléfono, código, acompañante) van en las notas del evento
  (D49, que sustituye a D40).
- **La frontera de salud** con Tristras, en forma de regla del planner y de goldens (D52).

**No entra (fase 4 por D45):** la consolidación nocturna, las marcas de herramientas en el
historial, la normalización de números y los compromisos recurrentes («todos los lunes»).
**Tampoco entra** leer fotos de hojas médicas: Josem dicta la preparación.

**Fecha límite real:** la dieta de Josem empieza el **lunes 14/12**. El resumen de ese día
tiene que salir ya con los compromisos cargados, así que **el despliegue tiene que estar hecho
el 10/12 como muy tarde**. Si H3 se retrasa, el recorte es H3.2 (los goldens de frontera), no
los avisos.

## 1. Decisiones de este plan (entran en el ADR como `tentativa`)

| # | Decisión | Por qué |
|---|---|---|
| D49 | **Los datos de una cita van en las notas del evento** (`events.notes`, la migración 005 y `calendar_add_note`). No hay entidad `evento` en la memoria. **Sustituye a D40** | D40 suponía un calendario externo (Google) que había que reflejar en algún sitio. El calendario es nuestro, y la fila del evento ya tiene la fecha y un campo de notas con su tool. Así hay un solo sitio, y «¿qué teléfono tiene endoscopia?» se contesta con `calendar_search_events`. Lo que se pierde: «Rebeca» queda como texto en la nota, no como enlace a su entidad. Se acepta para la fase 3 |
| D50 | **Un compromiso atado a un evento guarda un desfase, no una fecha.** El momento se calcula al leerlo, desde `events.start_datetime`. Si el evento se mueve, sus compromisos se mueven solos. Si se borra, sus compromisos se cancelan | Es el punto 3 del caso: los pasos son «3 días antes», «la víspera a las 21:00», «3 horas antes». Guardar fechas copiadas haría que una cita movida dejara la preparación en el día viejo |
| D51 | **Un aviso se marca con el momento para el que se mandó** (`aviso_para`), no con un «enviado sí/no». Se avisa si el momento ya llegó, no han pasado más de 2 h y `aviso_para` es distinto del momento actual | Es idempotente: la tarea puede correr dos veces, o tras un reinicio, sin repetir el aviso. Si el evento se mueve, el momento cambia y el aviso vuelve a quedar pendiente. Pasadas 2 h, un aviso tardío confunde más de lo que ayuda |
| D52 | **Frontera de salud:** la cita, la preparación, el lugar, el acompañante y los papeles son **logística** y son de Sebastian (compromisos y notas del evento). Lo que se mide del cuerpo (sueño, comidas, hambre, peso, síntomas) va a `salud`, es decir, a Tristras. **Los resultados, los diagnósticos y los episodios clínicos no se guardan en Sebastian**: ni memoria, ni notas, ni compromisos. La alergia sigue siendo memoria (fase 2, R6). Cierra la pregunta de §5. Va también al registro de tristras | Es el criterio que se propuso en §5, comprobado con el caso. El indicador de falsación es el de §5: si una frase razonable de los goldens de frontera cabe en los dos lados o en ninguno, el criterio no sirve |

## 2. Contratos

### 2.1 Esquema (migración `013_compromisos.sql`, sin `USE`, D20)

```sql
CREATE TABLE IF NOT EXISTS compromisos (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id          VARCHAR(50)  NOT NULL,
  texto            VARCHAR(500) NOT NULL,       -- «2.ª toma del preparado (sobres A y B en ½ l)»
  evento_id        INT NULL,                    -- events.id; NULL = compromiso suelto (D50)
  -- Cuándo. Exactamente una de estas dos formas (lo comprueba el repositorio):
  --  a) suelto: fecha_inicio [, fecha_fin] [, hora]
  --  b) atado:  dias_inicio [, dias_fin] [, hora]  ó  minutos (relativo a la hora del evento)
  fecha_inicio     DATE NULL,
  fecha_fin        DATE NULL,                   -- intervalo de días (la dieta: 14 → 16)
  dias_inicio      SMALLINT NULL,               -- días respecto al día del evento (-3, -1, 0)
  dias_fin         SMALLINT NULL,
  hora             TIME NULL,                   -- hora de reloj de ese día; NULL = sin hora
  minutos          INT NULL,                    -- desfase en minutos respecto a la hora del evento (-180)
  estado           ENUM('pendiente','hecho','cancelado') NOT NULL DEFAULT 'pendiente',
  aviso_para       DATETIME NULL,               -- D51: momento para el que ya se avisó
  created_at       DATETIME NOT NULL,
  updated_at       DATETIME NOT NULL,
  INDEX idx_user_estado (user_id, estado),
  INDEX idx_evento (evento_id),
  FOREIGN KEY (evento_id) REFERENCES events(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

- **Reglas de forma** (en el repositorio, con prueba normativa):
  - suelto exige `fecha_inicio`;
  - atado exige `dias_inicio` o `minutos`, nunca los dos;
  - `minutos` no va con `hora`;
  - `fecha_fin`/`dias_fin` no van con `minutos`;
  - un intervalo no lleva `hora`.
- **Momento efectivo:**
  - atado con `minutos`: `start_datetime + minutos`;
  - atado con `dias_*`: el día del evento + días, con la `hora` si la hay;
  - suelto: `fecha_inicio` y la `hora`.
  Un evento de todo el día (`all_day`) solo admite `dias_*`.
- **Zona horaria:** todo es hora local de seb01 (Europe/Madrid), igual que `events`. Los
  cálculos usan fechas del calendario, no sumas de 24 h, para que el cambio de hora no mueva
  una toma.
- **Borrar es borrar (D42):** «olvida ese compromiso» hace `DELETE`, no lo cancela. Cancelar
  (estado `cancelado`) es lo que pasa cuando se borra el evento, o cuando Josem dice «ya no
  hace falta».
- **Al borrar un evento** con `calendar_remove_event`, sus compromisos pendientes pasan a
  `cancelado`, en la misma transacción. Por eso la FK no lleva `ON DELETE`: el código lo hace
  primero.

### 2.2 Tools (familia nueva `compromisos`)

| Tool | Entrada | Qué hace |
|---|---|---|
| `compromisos_crear` | `items: [{texto, evento_id?, fecha_inicio?, fecha_fin?, dias_inicio?, dias_fin?, hora?, minutos?}]` (1–20) | Crea varios a la vez: la preparación de una cita se dicta en un mensaje. Valida la forma (§2.1) y devuelve cada uno con su momento efectivo ya calculado, para que Alfred lo repita con fechas reales («el lunes 14…») |
| `compromisos_listar` | `desde?`, `hasta?` (por defecto, de hoy a 14 días), `evento_id?` | Los pendientes con su momento efectivo, en orden |
| `compromisos_completar` | `id` | Pasa a `hecho` |
| `compromisos_borrar` | `id`, `motivo: olvidar\|cancelar` | `olvidar` hace DELETE; `cancelar` pasa a `cancelado` |

Descripciones (las escribe el programador; estas líneas son normativas):
- `compromisos_crear`: «Para cosas que el usuario **tiene que hacer** en un día o a una hora:
  "el lunes empiezo la dieta", "la víspera a las 21:00, la primera toma". Si van ligadas a una
  cita del calendario, usa su `evento_id` y desfases (`dias_inicio`, `minutos`) en vez de
  fechas, para que se muevan con la cita. **No para citas** (eso es `calendar_add_event`, D39),
  **ni para datos** (eso es `mark_as_memorable`), **ni para registros de salud** (eso es
  `salud`). Si un paso depende de algo que no sabes ("si toma hierro"), pregunta antes con
  `request_clarification`; si no aplica, no lo crees.»
- `calendar_add_note` (amplía la descripción actual): «También para los datos de una cita:
  lugar, planta, teléfono, código, quién acompaña. **Nunca** resultados ni diagnósticos (D52).»

**El índice del planner (D36) no cambia.** Los compromisos no son memoria; el planner los
consulta con `compromisos_listar`.

### 2.3 Planificador del bot (D48)

Las dos tareas viven en `bot/scheduler.py`, junto a las que ya hay. **No se crean unidades
systemd.**

**a) Resumen de la mañana** (el `daily_calendar_reminder` actual, a la misma hora:
`calendar.daily_reminder_time`, 08:00). Por cada usuario autorizado:

```
📅 Buenos días. Hoy, jueves 17:
• 09:30 — Colonoscopia
✅ Para hoy:
• Llevar el parte de interconsulta
⏰ Antes del próximo resumen:
• (nada)
```

- **«Hoy»** es la agenda actual, sin cambios.
- **«Para hoy»:** los compromisos sin hora cuyo día o intervalo incluye hoy, y los que tienen
  hora entre ahora y las 23:59. Un intervalo se escribe con su posición: «Dieta sin residuos
  (día 1 de 3)».
- **«Antes del próximo resumen»:** los compromisos con hora de mañana antes de la hora del
  resumen. En el caso, el del 16 enseña las 01:00 y las 06:30 del 17.
- Una sección vacía no se escribe. **Si las tres están vacías, no se manda nada** (D47).
- Formato: el `bot.send_message` que ya existe. Sin LLM: el resumen se arma con plantilla, sin
  coste y sin inventar nada.

**b) Avisos a su hora** (tarea nueva `avisos_compromisos`, cada minuto, con
`max_instances=1` y `coalesce=True`):
- Selecciona los pendientes con hora cuyo momento efectivo `m` cumple `ahora − 2 h < m ≤ ahora`
  y `aviso_para` distinto de `m` (D51).
- Manda `⏰ 01:00 · 2.ª toma del preparado (sobres A y B en ½ l) — Colonoscopia` (con el título
  del evento si va atado).
- Escribe `aviso_para = m` **después** de enviar. Si el envío falla, no lo escribe, y se
  reintenta al minuto siguiente.
- **Al arrancar el bot**, la tarea corre una vez enseguida, sin esperar al primer minuto. Esto
  recupera los avisos perdidos por un reinicio, dentro de la ventana de 2 h.
- Cada aviso enviado, y cada uno descartado por caducado, deja una línea en LogCentral sin el
  texto: solo id, usuario, momento y resultado (lección de la fase 2, R12).

## 3. Hitos

### H1 — Compromisos: tabla, repositorio y tools

- `013_compromisos.sql` en `sebastian_test` y `sebastian_dev`.
- `modules/compromisos.py`: el repositorio, el momento efectivo y las reglas de forma.
- `core/tools/compromisos_tools.py`: las cuatro tools y su familia en el registro.
- `calendar_remove_event` cancela los compromisos atados. La descripción de `calendar_add_note`
  se amplía (§2.2).

**Pruebas normativas** (sin API, en `sebastian_test`, con un reloj inyectado; nunca
`datetime.now()` directo):
- `test_forma_suelto_exige_fecha`, `test_forma_atado_dias_o_minutos_no_ambos`,
  `test_forma_intervalo_sin_hora`, `test_forma_minutos_sin_hora`.
- `test_momento_atado_minutos`: un evento el 17/12 a las 09:30 con `minutos=-180` da el 17/12 a
  las 06:30.
- `test_momento_atado_dias_hora`: `dias_inicio=-1, hora=21:00` da el 16/12 a las 21:00, y
  `dias_inicio=0, hora=01:00` da el 17/12 a la 01:00.
- `test_intervalo_dieta`: `dias_inicio=-3, dias_fin=-1` sin hora cubre del 14/12 al 16/12, ambos
  incluidos.
- `test_evento_movido_mueve_compromisos`: se mueve el evento al 18/12 y los cinco momentos del
  caso se desplazan un día.
- `test_evento_borrado_cancela_compromisos`.
- `test_borrar_olvidar_hace_delete` (la fila ya no existe) y `test_borrar_cancelar_conserva`.
- `test_cambio_de_hora`: un evento el lunes después del cambio de hora de marzo, con
  `dias_inicio=-1, hora=21:00`, da 21:00 de reloj, no 20:00 ni 22:00.
- `test_crear_devuelve_momento_efectivo`.
- `test_aislamiento_usuarios`: el usuario A no lista, completa ni borra compromisos de B.

### H2 — Planificador: resumen y avisos

- Las dos tareas de §2.3. El armado del resumen va en una función pura
  `armar_resumen(usuario, ahora) -> str | None`, aparte del envío, para poder probarla.

**Pruebas normativas** (bot falso que registra los envíos y reloj inyectado; nunca Telegram de
verdad). Fixture común: **el caso de la colonoscopia con datos inventados.** El evento es el
17/12 a las 09:30 y lleva los compromisos de la tabla del caso.
- `test_resumen_14_dieta_dia_1`: el 14/12 a las 08:00 sale «Dieta sin residuos (día 1 de 3)».
- `test_resumen_16_mira_a_manana`: el 16/12 a las 08:00 trae en «Para hoy» los líquidos claros y
  la 1.ª toma de las 21:00, y en «Antes del próximo resumen», las 01:00 y las 06:30 del 17.
- `test_resumen_dia_vacio_calla`: devuelve `None` y no se envía nada (D47).
- `test_resumen_agenda_sin_compromisos_igual_que_hoy`: sin compromisos, el texto es el de ahora
  (no se rompe lo existente).
- `test_aviso_a_su_hora`: a las 01:00 del 17/12 sale el aviso de la 2.ª toma, y a las 01:01 no
  se repite.
- `test_aviso_tras_reinicio_dentro_de_ventana`: si el bot arranca a las 02:30, sale el de la
  01:00.
- `test_aviso_caducado_no_sale`: si arranca a las 03:30, no sale y queda una línea de log
  «caducado».
- `test_aviso_fallo_envio_reintenta`: el primer envío lanza una excepción, `aviso_para` sigue a
  NULL, y al minuto siguiente sale.
- `test_aviso_evento_movido_vuelve_a_avisar`: se avisó de la 01:00; se mueve el evento un día;
  el 18 a la 01:00 se avisa otra vez.
- `test_aviso_solo_pendientes`: un compromiso `hecho` o `cancelado` no avisa.
- `test_log_sin_texto`: las líneas de log de avisos no contienen `texto`.

### H3 — El planner: goldens y escenario de punta a punta

**H3.1 Goldens normativos** (los escribe el arquitecto; el programador los copia en
`goldens.yaml` tal cual):

```yaml
# Fase 3 (D45, D49, D50, D52). Normativos; su línea base va solo con -k.
- id: 67
  phrase: "El lunes empiezo la dieta sin residuos, tres días"
  mode: exact
  expected: [compromisos_crear]
  validates: "Fase 3 (D45): una cosa que hacer con fecha es compromiso, no cita ni memoria"

- id: 68
  phrase: "Para la colonoscopia: la víspera a las 21:00 la primera toma y el mismo día a la una la segunda"
  historia:
    - {user: "Tengo la colonoscopia el 17 de diciembre a las 9:30", bot: "Apuntado en tu calendario: colonoscopia, jueves 17 de diciembre a las 9:30."}
  mode: any_of
  expected:
    - [compromisos_crear]
    - [calendar_search_events, compromisos_crear]
    - [calendar_find_by_datetime, compromisos_crear]
  validates: "Fase 3 (D50): pasos ligados a una cita van atados al evento; puede buscar antes el evento_id"

- id: 69
  phrase: "En la colonoscopia me acompaña Rebeca y es en la planta baja del Gregorio Marañón"
  historia:
    - {user: "Tengo la colonoscopia el 17 de diciembre a las 9:30", bot: "Apuntado en tu calendario: colonoscopia, jueves 17 de diciembre a las 9:30."}
  mode: any_of
  expected:
    - [calendar_add_note]
    - [calendar_search_events, calendar_add_note]
    - [calendar_find_by_datetime, calendar_add_note]
  validates: "Fase 3 (D49): los datos de una cita van a las notas del evento, no a la memoria"

- id: 70
  phrase: "¿Qué tengo que hacer esta semana?"
  mode: any_of
  expected:
    - [compromisos_listar]
    - [compromisos_listar, calendar_list_events]
    - [calendar_list_events, compromisos_listar]
  validates: "Fase 3: consultar lo pendiente lee compromisos"

- id: 71
  phrase: "Ya he hecho la primera toma"
  historia:
    - {user: "¿Qué me toca hoy?", bot: "Hoy: solo líquidos claros, y a las 21:00 la primera toma del preparado."}
  mode: any_of
  expected:
    - [compromisos_completar]
    - [compromisos_listar, compromisos_completar]
  validates: "Fase 3: marcar hecho; no es un registro de salud (D52)"

- id: 72
  phrase: "Me han cambiado la colonoscopia al 18 a la misma hora"
  mode: any_of
  expected:
    - [calendar_update_event]
    - [calendar_search_events, calendar_update_event]
    - [calendar_find_by_datetime, calendar_update_event]
  validates: "Fase 3 (D50): se mueve el evento, y los compromisos se mueven solos; no se tocan uno a uno"

# Frontera de salud (D52). Negativos: lo que falla es guardarlo donde no toca.
- id: 73
  phrase: "El test de sangre oculta me salió positivo"
  mode: any_of
  expected:
    - []
    - [request_clarification]
  validates: "Fase 3 (D52), negativa: un resultado clínico no se guarda en Sebastian (ni memoria, ni notas, ni salud)"

- id: 74
  phrase: "Recuérdame que en la colonoscopia tengo que decir que soy alérgico a la aspirina"
  mode: any_of
  expected:
    - [compromisos_crear]
    - [calendar_search_events, compromisos_crear]
    - [calendar_find_by_datetime, compromisos_crear]
    - [calendar_add_note]
    - [calendar_search_events, calendar_add_note]
  validates: "Fase 3 (D52): avisar de la alergia en la cita es logística; la alergia ya es memoria"

- id: 75
  phrase: "Hoy he desayunado un caldo y un zumo de manzana colado"
  mode: exact
  expected: [salud]
  validates: "Fase 3 (D52): lo que se come sigue yendo a Tristras, también en días de preparación"

- id: 76
  phrase: "Si tomo hierro tengo que dejarlo 7 días antes de la colonoscopia"
  mode: any_of
  expected:
    - [request_clarification]
    - [compromisos_crear]
    - [calendar_search_events, compromisos_crear]
  validates: "Fase 3 (D52): un paso condicional se pregunta o se crea; nunca va a memoria ni a salud"
```

- La línea base de #67–#76 va con `-k` y los ids exactos, con ×3 en los que salgan
  intermitentes.
- **La pasada completa** (#1–#76) va una vez, con las tools nuevas puestas. Si cae algún golden
  antiguo, se para y se cuenta (riesgo §5).

**H3.2 Escenario de punta a punta E10, la colonoscopia** (con datos inventados, reloj fijado y
`sebastian_test`):
1. Josem da la cita y se crea el evento.
2. Dicta la preparación en uno o dos mensajes y se crean los compromisos atados.
3. Da el lugar y el acompañante, que acaban en la nota del evento.
4. Se le dice que el test salió positivo y no se guarda nada.
5. Se mueve la cita un día.
6. Con el reloj del día −3, `armar_resumen` trae la dieta en su fecha nueva.

El criterio es el estado de la BD y el texto del resumen, no lo que diga Alfred. **Pasa si
pasa 3 de 3.**

### H4 — Despliegue (lo ejecuta Josem, con el arquitecto)

- `deploy/comprobar_fase3.sh`, solo de lectura, como el de la fase 2:
  - `013` aplicada en `sebastian_db`;
  - la línea de arranque del bot dice que hay dos tareas nuevas;
  - 0 errores en LogCentral;
  - prueba seca de `armar_resumen` para Josem con la fecha de mañana.
- Pasos con sudo, en `deploy/PASOS-CON-SUDO.md` (se actualiza): migración, `ff-only` y reinicio.
- **La prueba real** es el caso de verdad: Josem dicta su preparación por Telegram, y el
  arquitecto comprueba la BD contra `CASO-COLONOSCOPIA.md`.
  - Conviene hacerlo antes del 7/12, para que haya margen.
  - Es también el indicador de D48: el aviso de la 01:00 del 17 tiene que llegar a su hora.

## 4. Lista previa (convención §4)

- **¿Algo borra o sobrescribe datos?** Sí.
  - **Producción:** `013` solo crea una tabla. `compromisos_borrar(olvidar)` borra filas a
    propósito (D42), y `calendar_remove_event` pasa compromisos a `cancelado`.
  - **Tests:** todos van en `sebastian_test`, también los del planificador. El fixture borra
    solo los compromisos y eventos de los usuarios de prueba. El planificador se prueba con un
    bot falso: **ninguna prueba manda nada a Telegram de verdad**, y una guarda hace fallar el
    test si el bot real llega a construirse.
- **¿Algo llama a una API externa?** Sí, en pasos **[API]**.
  - **Anthropic, sin cambio de modelos (D29):** planner en `claude-haiku-4-5-20251001` y
    síntesis en `claude-sonnet-4-6`. Antes del primer [API] de H3, el programador comprueba con
    la skill `claude-api` que los dos ids siguen servidos y que los precios no han cambiado
    (1 $ / 5 $ y 3 $ / 15 $ por millón).
  - **El resumen y los avisos no usan LLM** (plantillas): no tienen coste por día.
  - **Telegram:** solo en producción, con el bot que ya existe.
  - **Presupuesto:**

    | Partida | Coste |
    |---|---|
    | Línea base #67–#76, ×3 en los dudosos | ≈ 0,3 $ |
    | Pasada completa (76 goldens) | ≈ 1,5 $ |
    | E10 ×3 (unos 8 turnos cada vez) | ≈ 0,6 $ |
    | Retoques (otra línea base y E10) | ≈ 0,9 $ |
    | **Total** | **≈ 3,3 $** |

    **Tope que pido: 4 $** para la fase. Cada informe da el coste por modelo. Si se pasa del
    tope, para.
- **¿Algo toca producción?** Sí, en H4, y lo ejecuta **Josem**:
  - `sebastian_db` (la migración 013);
  - `sebastian.service` (reinicio), y con él el planificador.

  No cambian unidades ni variables de entorno. **El cuaderno no se toca.**

## 5. Riesgos que vigilo en las revisiones

- **Cuatro tools nuevas en el prompt del planner** pueden mover goldens que hoy pasan, sobre
  todo los de calendario (#7, #8, #9, #40, #50, #64, #65) y los de memoria (#56–#66). Para eso
  está la pasada completa.
- **«Recuérdame…» tiene tres destinos:** compromiso, cita o dato. #65 (D39) sigue mandando una
  cita con fecha al calendario; #67 manda una tarea al compromiso; «recuerda que Paco…» va a
  memoria. Las descripciones tienen que nombrar qué hace cada una, no prohibir (lección de R5).
- **Un planificador dentro del bot depende del proceso** (D48). El indicador es que un aviso
  llegue más de 10 minutos tarde o se pierda por un reinicio, y la prueba real es el 17/12.
- **El planner tiene que conseguir el `evento_id`.** Si en #68 no lo busca y crea compromisos
  sueltos con fechas, el golden pasa, pero D50 no se cumple. E10 lo comprueba en la BD: los
  compromisos tienen que tener `evento_id`.

## Para el programador

*(Se escribe cuando Josem apruebe el plan y el tope.)*
