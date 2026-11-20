# H1 — Informe del programador (fase 4: vigilancias con Wallapop)

Responde a: `0e2c39d` (PLAN fase 4, «Para el programador»).
Commits en `fase-4`: `7dcd8ec` (módulo, migración, tarea, carga y pruebas 1–26), `e646495` (piezas del [RED] y del [API], sin gasto) y este informe. Suite completa: **1051 pruebas** (942 + 109), sin API ni red.

## Hecho

- **Migración `014_vigilancias.sql`** (sin `USE`, idempotente; la prueba la aplica dos veces). Aplicada a `sebastian_test`, no a producción.
- **`modules/vigilancias/`:**
  - `anuncio.py`: `Anuncio` y `FuenteError`.
  - `fuentes/wallapop.py`: la fuente, y `fuentes/__init__.py` con `FUENTES`.
  - `filtro.py`: normalizar, firma, filtro y novedad.
  - `juez.py`: `MODELO_JUEZ`, `TOOL_INFORME`, `juzgar`.
  - `ronda.py`: `pasada_vigilancias`, `armar_mensaje`, `le_toca`.
  - `repositorio.py`: validación, `guardar` (upsert) y lectura. **No estaba en el plan**: el §2.7 dice «valida igual que el módulo», y esto es ese módulo. H2 lo reutilizará.
- **`bot/scheduler.py`:** tareas `vigilancias` (cada 15 min, `max_instances=1`, `coalesce`) y `vigilancias_arranque` (a los 5 s).
- **`scripts/vigilancias/cargar.py`:** upsert por `(user_id, nombre)`, atómico (si una del fichero no vale, no se escribe ninguna). Acepta un mapa o una lista de mapas.
- **Pruebas normativas 1–26 del plan**, cada una con el número en el nombre, más las de apoyo:
  - tablas y claves;
  - validación campo a campo;
  - tope de 5 activas;
  - bordes de la ventana;
  - recorte del mensaje por anuncios enteros;
  - parámetros de Haiku 5.5;
  - coste.
- **Piezas de [RED] y [API]** (`humo_wallapop.py`, `golden_juez.py`, `tests/golden/vigilancias/` con los 12 anuncios inventados y el criterio fijado antes de medir), con 16 pruebas propias sin gasto.
- El YAML de `mac-mini.yaml` valida con mi código (8 consultas, 300–3000 €, 1157 caracteres de reglas).

### [RED] Humo real de Wallapop (gratis, sin LLM)

8 peticiones, ninguna con error. Salida completa en el scratchpad (`f4_red.txt`).

| consulta | devueltos | nuevos 48 h | pasan filtro |
|---|---|---|---|
| 1 | 5 | 5 | 5 |
| 2 | 0 | 0 | 0 |
| 3 | 16 | 16 | 8 |
| 4 | 0 | 0 | 0 |
| 5 | 1 | 1 | 1 |
| 6 | 16 | 16 | 7 |
| 7 | 0 | 0 | 0 |
| 8 | 1 | 1 | 0 |

- **Totales:** 20 únicos, 20 nuevos, 10 pasan el filtro. Los 10 son los que habría visto el juez hoy.
- **Campos:** los 20 traen precio y ciudad, y ninguno está reservado.
  - `reserved` llega como `{flag: bool}`, como suponía.
  - `shipping` llega como `{cost_configuration_id, item_is_shippable, user_allows_shipping}`. El parser lee `item_is_shippable` primero, y el recuento da 12 con envío y 8 sin él.
  - La edad de los anuncios va de 0,6 h a 19,7 h.
- **Tres consultas devuelven 0** (la 2, la 4 y la 7). Dos de ellas llevan el número de GB («Mac mini M4 48», «Mac mini M2 Pro 32»). Con una sola prueba no sé si la búsqueda exige todas las palabras o si no había anuncios; es una duda abierta (ver Decisiones).
- Las consultas 3 y 6 devuelven 16 (las de «M4 Pro» y «M5 Pro»), y los 16 son nuevos. El filtro deja pasar 8 y 7, así que parte de lo que llega al juez no es lo que buscas.

### [API] Goldens del juez

Con las reglas de `mac-mini.yaml` y los 12 anuncios inventados, 3 pasadas por modelo. El criterio no cambió desde que lo fijé. Salida completa en el scratchpad (`f4_api.txt`).

| modelo | aciertos | latencia media | tokens de entrada | coste total |
|---|---|---|---|---|
| `claude-haiku-4-5-20251001` | **3/3** | 5,6 s | 2751 | 0,0160 $ |
| `claude-haiku-5-5` (`effort: low`, sin thinking) | **1/3** | 2,2 s | 3258 | 0,0017 $ |

- **Con 4.5:**
  - Los 3 buenos salen como COMPRAR en las 3 pasadas.
  - El revendedor, el de 256 GB hinchado, el M4 de 16 GB caro, los accesorios y la inyección no salen nunca.
  - Salen además, como MIRAR, el M2 Pro de 16 GB a 520 € (g07, las 3 veces) y el MacBook M3 Max (g08, una vez). Ninguno de los dos cuenta para el criterio.
- **Con 5.5:**
  - Las dos veces que falla es por la misma razón: **el M2 Pro 32 GB a 900 € (g03) no sale**. Los otros dos buenos salen, g02 como MIRAR en las 3 pasadas.
  - Tampoco sale nunca ninguno de los casos a evitar, ni la inyección.
  - Marca el anuncio sin RAM visible (g09) como MIRAR y pide aclarar la RAM, que es lo que piden las reglas.
- **Haiku 5.5 no acierta lo mismo ni más, así que no propongo cambiar `MODELO_JUEZ`.** Es unas 9 veces más barato y 2,5 veces más rápido.
- **Hallazgos que no cambian el veredicto:**
  - Los textos del juez a veces inventan cifras («20 % bajo mercado», «ganga: nuevo cuesta ~1300 €»). 4.5 lo hace en las 3 pasadas.
  - En una pasada, 5.5 escribe «sin factura ni garantía» de un anuncio que no habla de factura.
  - **El `cierre` cita ids** («Mejor de esta ronda: g01…»). En producción los ids de Wallapop son cadenas sin sentido y Josem leería un hash en vez del modelo.
  - La inyección no salió en ninguna de las 6 pasadas.

## Gasto

- **[RED]:** 0 $. 8 peticiones a la API de Wallapop.
- **[API]:** 0,0177 $ en total (0,0160 $ con 4.5 y 0,0017 $ con 5.5), muy por debajo del tope de 0,30 $.
- **Fase 4: ≈0,018 $ de 3 $.**
- **Autorizó Josem el 2026-11-20, en mi ventana:** «Si y si!», en respuesta a mi petición de lanzar los dos pasos.

## Desviaciones

1. **El «Si y si!» respondía también a mi pregunta de añadir una regla de permisos** (`Edit(//data/AssistantStudies-fase4/**)` en `~/.claude/settings.json`). Josem rechazó esa edición en el diálogo y no la reintenté. No hay ninguna regla nueva.
2. **Duplicados por firma.** El plan fija el orden «duplicados, novedad, filtro». Yo deduplico por `id` antes de la novedad, y por firma después, solo entre los candidatos. Un anuncio con la misma firma que otro de la ronda sigue contando como «nuevo» y se guarda como visto, pero no llega al juez dos veces. Si no, mañana volvería a salir, porque su `id` no estaría en `vistos`. Lo cubre `test_8`.
3. **Tope de 40 candidatos.** El plan dice «escribe todos los anuncios nuevos», y lo cumplo al pie de la letra: los candidatos que quedan fuera del tope de 40 se guardan como vistos sin que el juez los haya visto, y no vuelven. Hoy salen 10, así que no se vería. Ver Decisiones.
4. **Horas pasadas las 22:00.** La ventana de 2 h se corta a medianoche (el día siguiente ya es otro día). No lo valido en `cargar`.
5. **Si el envío sale y la escritura en la BD falla,** el mensaje ya salió y la pasada siguiente lo repetiría. Lo dejo en el log como `enviada_sin_registrar`, que es raro y visible. Los vistos y `ultima_ronda` van en una sola transacción.
6. **Editar con Bash.** Una vez toqué `repositorio.py` con `python3` en Bash en vez de con Edit, contra la preferencia de Josem. Sin consecuencia (el cambio es el que se ve en el commit). Después usé Edit.
7. **`TOMORROW.md`** estaba hinchado de las fases anteriores. Lo reescribí corto, solo con lo de la fase 4.
8. **El comentario de cabecera de `mac-mini.yaml` (vault) dice `DB_NAME=sebastian_db`.** La variable que lee `utils/config.py` es **`SEBASTIAN_DB_NAME`**. Con `DB_NAME` la carga iría a la BD de desarrollo sin avisar. El script imprime «Escribiendo en BD: …». Corregir esa línea es del arquitecto.
9. **Las tareas reciben `config` como `kwargs`.** Solo se usa para crear el cliente de Anthropic cuando hay candidatos.

## Decisiones que necesito

1. **`MODELO_JUEZ`:** ¿se queda `claude-haiku-4-5-20251001`? Es lo que recomiendo, porque 5.5 pierde un anuncio bueno en 2 de 3 pasadas.
2. **Ids en el `cierre`.** Propongo añadir al marco una línea («en `texto` y `cierre` no escribas ids: nombra el chip, la RAM y el precio») y repetir los goldens, unos 0,02 $. Necesita tu OK y el «sí» de Josem.
3. **Cifras inventadas en el texto del juez** (porcentajes de descuento, precios de nuevo). ¿Las acepto como ruido, o añado al marco «no des cifras de mercado que no estén en el anuncio»? Si añades la regla, va en la misma pasada que el punto 2.
4. **Consultas con 0 resultados.** Veo 3 de 8 con 0, dos de ellas con el número de GB. ¿Quieres que mire con una prueba (unas pocas peticiones más, gratis) si Wallapop exige todas las palabras? Si es así, el buen M2 Pro de 32 GB no saldría nunca con esa consulta.
5. **Tope de 40 candidatos (desviación 3):** ¿se guardan también como vistos los que no llegan al juez (como ahora), o se dejan para mañana?
6. **Despliegue:** ¿añado `deploy/comprobar_fase4.sh` y una sección «Fase 4» en `deploy/PASOS-CON-SUDO.md`, como en la fase 3? No estaba en el encargo.

## Pasos de despliegue (los hace Josem)

```bash
cd /data/AssistantStudies && git status          # limpio, en main
git rev-parse HEAD                               # apunta este hash: es la vuelta atrás (hoy 7226ec3)
git merge --ff-only fase-4
sudo mysql sebastian_db < sebastian2/db/migrations/014_vigilancias.sql
cd sebastian2 && SEBASTIAN_DB_NAME=sebastian_db .venv/bin/python -m scripts.vigilancias.cargar /data/library/mi-wiki/docs/Obsidian/30-projects/sebastian/vigilancias/mac-mini.yaml --user <tu id de Telegram>
# tiene que imprimir «Escribiendo en BD: sebastian_db» y «creada id=… «Mac mini para LLM local»»
sudo systemctl restart sebastian.service
```

- **Prueba real:** la primera ronda sale mañana a partir de las 07:30. Para verla antes, se puede cargar con una hora cercana (por ejemplo dentro de 20 minutos) y volver a cargar con las 07:30 después.
- **Vuelta atrás:** `sudo systemctl stop sebastian.service; cd /data/AssistantStudies && git reset --hard <hash guardado>; sudo systemctl start sebastian.service`. Las tablas nuevas pueden quedarse: nada las lee sin el código.

> **Estos pasos quedan sustituidos por la sección «Fase 4» de `deploy/PASOS-CON-SUDO.md`** (anexo de abajo, R3): los comandos con `sudo` van allí en una sola línea.

---

# Anexo — Retoques de la revisión (R1, R2, R3)

Responde a: `0eaa6e2` (H1-revision).
Commits en `fase-4`: `bb19fe0` (R1), `a22d616` (R2), `c179aee` (R3) y `8375cf2` (`--modelos` en `golden_juez`). Suite completa: **1068 pruebas** pasan (1051 + 17), sin API. El resultado de R2 en la API es **negativo**: ver abajo.

## Hecho

- **R1 (D65):** `_hacer_ronda` guarda como vistos todos los nuevos salvo los candidatos que el tope de 40 deja sin juzgar.
  - **Prueba:** con 42 candidatos, al juez llegan los 40 más recientes, los 2 más antiguos no están en `vigilancia_vistos`, un nuevo que solo el filtro descartó sí está, y al día siguiente (dentro de las 48 h) los 2 vuelven al juez.
- **R2 (D66):** dos líneas nuevas en `MARCO`, con el sentido que pedías («no escribas ids…» y «no des cifras de mercado ni porcentajes…»).
  - **Criterio** ampliado en `criterios.py` antes de medir: además de lo anterior, ningún `texto` ni el `cierre` contiene el id de un candidato (palabra entera, sin distinguir mayúsculas) ni «%».
  - **Pruebas:** el marco lleva las dos líneas y el criterio falla con un id o un «%» en el texto o el cierre, y no se confunde con un id dentro de otra palabra.
- **R3:** `deploy/comprobar_fase4.sh` (solo lectura; sin sudo, sin escribir, sin red ni API ni Telegram) y la sección «Fase 4» de `PASOS-CON-SUDO.md`.
  - **Comprobaciones:**
    - producción en `main` con la fase 4, y que las dos unidades fijan `sebastian_db`;
    - el log de arranque (`Escribiendo en BD` y `Planificador arrancado` con «vigilancias cada 15 min»);
    - las dos tablas con sus columnas y la vigilancia activa y con hora (solo SELECT; de las consultas solo se cuenta cuántas hay, D42);
    - las rondas desde el reinicio (solo cuentas) y los errores en LogCentral.
  - **`bot/scheduler.py`:** la línea de arranque ahora dice «avisos cada minuto, vigilancias cada 15 min». `comprobar_fase3.sh` sigue encontrando «avisos cada minuto».
  - **Pasos con `sudo`:**
    - Una sola línea con `&&`, sin comentarios dentro.
    - Lo que hay que apuntar va en un bloque aparte, antes.
    - La vuelta atrás también va en una línea (en el informe original la dejé en varias).
    - Una prueba lo exige para todos los bloques de la sección.
  - **Ensayo:** contra `sebastian_test`, con la vigilancia de Josem cargada para un usuario de prueba (borrada después), el apartado de la BD sale OK. Los apartados de `main` y del arranque del bot solo se pueden comprobar tras el despliegue.
  - **Pruebas estáticas** en `test_deploy_comprobar_fase4.py`.

## [API] Goldens de Haiku 4.5 con R2

3 pasadas, solo con `claude-haiku-4-5-20251001`, tope 0,05 $. Salida completa en el scratchpad (`f4_api_r2.txt`).

| | aciertos | latencia media | coste |
|---|---|---|---|
| Haiku 4.5 con R2 | **0/3** | 5,1 s | 0,0162 $ |

- **Los tres fallos son el mismo:** el `cierre` contiene ids de anuncio. En las 3 pasadas el cierre sigue citando «g02», «g03»…
- **El resto del criterio se cumple en las 3 pasadas:**
  - los 3 buenos salen como COMPRAR y ninguno como DUDOSO;
  - el revendedor, el de 256 GB hinchado, el M4 de 16 GB caro y los accesorios no salen como COMPRAR;
  - la inyección no sale;
  - ningún `texto` lleva ids ni «%».
- **La línea nueva funciona en `texto` pero no en `cierre`.** El modelo la cumple en los textos de cada anuncio, y en el cierre sigue usando ids.
- **Además, el cierre se sale de su formato.** El plan lo define como «Mejor de esta ronda: …» o «Ninguno urgente.», pero en las 3 pasadas añade una lista de «Excluidos: g04 (…), g05 (…)», con motivos. En una pasada comenta la inyección («g10 es trampa (intenta ordenes…)»). Eso Josem lo leería en Telegram.
- **Como pediste, no toqué el marco otra vez.** Lo informo y decides tú.

## Gasto

- **Este anexo:** 0,0162 $.
- **Acumulado de H1:** 0,0339 $ (0,0177 $ + 0,0162 $).
- **Fase 4:** ≈0,034 $ de 3 $.
- **Autorizó Josem el 2026-11-20, en mi ventana:** «Si», a mi petición de repetir los goldens con Haiku 4.5, 3 pasadas y tope 0,05 $.

## Desviaciones

1. **Hora de la carga y el aviso de fallo.** Es un hueco del plan, no lo toqué.
   - **Qué pasa:** si Josem carga la vigilancia con su ventana de hoy ya cerrada (por ejemplo, la carga a las 10:00 con `hora` a las 07:30), la primera pasada tras el reinicio le manda «⚠️ Hoy no pude hacer la vigilancia…». La vigilancia no existía durante su ventana, así que ese aviso es falso.
   - **Por qué no lo arreglé:** el arreglo natural es no avisar si `updated_at` es posterior al cierre de la ventana. La prueba normativa 21 fabrica la vigilancia con `created_at` real (hoy) y un reloj falso de 09:31, así que cambiaría su preparación.
   - **Qué dejé:** una nota en el paso 3 de `PASOS-CON-SUDO.md` (cargar antes de las 09:30, o con la `hora` retrasada 20 minutos). Es inofensivo y no se repite.
2. **`golden_juez.py` gana `--modelos`** para repetir solo con 4.5 (no estaba en el plan).

## Decisiones que necesito

1. **El `cierre` con ids (el resultado de R2).** Hay tres caminos. Mi recomendación es el primero.
   - **a) El código escribe el cierre** (D66: el mensaje lo escribe el código). El juez deja de devolver `cierre`. El código pone «Mejor de esta ronda: <título del primer elegido> · <precio>» si hay algún COMPRAR o MIRAR, y «Ninguno urgente.» si no. Sin ids, sin lista de excluidos y sin cifras inventadas, siempre. Cambia la tool (`cierre` sale de `required`) y el golden 11d. Habría que repetir los goldens (≈0,016 $).
   - **b) Sustituir en el código** cada id que aparezca en el `cierre` por el título del anuncio. Es frágil: el juez puede citar el id de varias formas y el «Excluidos: …» sigue ahí.
   - **c) Endurecer el marco otra vez** («en `cierre` solo una línea, sin ids, sin lista de excluidos»). Es lo que dijiste que no hiciera sin ti, y con 3 pasadas de 3 fallando no me fío de que baste.
2. **La hora de la carga (desviación 1).** ¿Dejo la nota en el despliegue, o autorizas la guarda por `updated_at` y que cambie la preparación de la prueba 21?
3. **Despliegue:** tras decidir el punto 1, el despliegue es de Josem con la sección «Fase 4» de `PASOS-CON-SUDO.md` y `comprobar_fase4.sh`.

---

# Segundo anexo — R4 y R5

Responde a: `fe291e8` (H1-revision §5).
Commits en `fase-4`: `88d48f6` (R4) y `fcb49f4` (R5). Suite completa: **1084 pruebas** pasan (1068 + 16), sin API.

## Hecho

- **R4 (D66):**
  - La tool cambia `cierre` por `mejor_id` (cadena opcional). `required` queda en `["elegidos"]`.
  - `MARCO` sustituye la línea del cierre por la de `mejor_id`. La línea de no escribir ids se queda, ahora solo para `texto`.
  - `_validar` acepta `mejor_id` solo si es uno de los elegidos que quedan tras recortar a 6. Si no, es `None`.
  - `armar_mensaje` escribe el cierre: «Mejor de esta ronda: <título> · <precio>», con los datos del anuncio. Con `mejor_id` nulo o inválido, «Ninguno urgente.». Sin elegidos, «Nada nuevo que merezca la pena.», sin cierre.
  - **Pruebas:** las tres que pedías, más `mejor_id` recortado, sin él, de tipo erróneo y de un candidato no elegido.
  - **Criterio** ajustado antes de medir: ids y «%» solo en los `texto`, y `mejor_id`, si viene, uno de los 3 buenos.
- **R5 (D67):** `guardar` pone `aviso_fallo = hoy` cuando la vigilancia queda activa con su ventana de hoy cerrada y sin ronda hoy.
  - Vale al crear y al cambiar. No se aplica a una vigilancia inactiva ni a una con ronda ya hecha hoy.
  - **Pruebas:** las dos que pedías (carga a las 10:00 y pasada de las 10:15 sin nada, y ronda al día siguiente; carga a las 07:45 y ronda a las 08:00), más los bordes (09:29 y 09:30), una hora más tardía y el caso de cambiar una vigilancia.
  - He quitado la nota del paso 3 de `PASOS-CON-SUDO.md`.
  - **Un detalle de las pruebas:** `guardar` ahora lee el reloj, así que el `_crear` de las pruebas de la ronda pasa un `ahora` fijo (el día antes, de madrugada). Con el reloj real, la prueba 21 habría dependido del día en que se ejecuta. Sus aserciones no cambian.

## [API] Goldens de Haiku 4.5 con R4

3 pasadas, tope 0,03 $. Salida completa en el scratchpad (`f4_api_r4.txt`).

| | aciertos | latencia media | coste |
|---|---|---|---|
| Haiku 4.5 con R4 | **2/3** | 4,9 s | 0,0153 $ |

- **Pasadas 1 y 3: aciertan.** No hay ids en el mensaje (`mejor_id` es `g02`, que el código convierte en título y precio) y los 3 buenos salen como COMPRAR.
- **Pasada 2: falla por un solo motivo, y es mío.** En el texto de g08 (el MacBook), el juez escribe «batería al 94 %». Eso **sí está en el anuncio** («batería al 94 %»), así que no es una cifra de mercado inventada, que era lo que quería evitar. Mi criterio («ningún `texto` contiene %») es más estricto que la regla del marco («cifras que no estén en el anuncio»).
- **Lo demás se cumple en las 3 pasadas:** los buenos y los malos salen bien, la inyección no sale y `mejor_id` es siempre uno de los buenos.
- **Mejora respecto al anexo anterior:** los ids desaparecen del cierre (ahora lo escribe el código) y los textos ya no traen cifras de descuento ni «Excluidos».
- **Como pediste, no toqué el marco ni el criterio.** Lo informo y decides tú.

## Gasto

- **Este anexo:** 0,0153 $, con el «sí» de Josem de hoy («Dale!»).
- **Acumulado de H1:** 0,0492 $ (0,0177 $ + 0,0162 $ + 0,0153 $).
- **Fase 4:** ≈0,049 $ de 3 $.

## Decisiones que necesito

1. **El criterio de «%».** Propongo que falle solo si el «%» no aparece en la descripción o el título del anuncio citado, y no por cualquier «%». Con eso, la pasada 2 acierta y las 3 pasadas darían 3/3. Si lo apruebas, lo cambio y vuelvo a juzgar las 3 salidas guardadas **sin API**, como hice con #81, sin gastar nada. Si prefieres mantener el criterio estricto, el juez falla ante datos legítimos del anuncio, y habría que decidir si se endurece el marco.
2. **Despliegue:** si apruebas el punto 1 (o decides que 2/3 vale), el despliegue es de Josem con la sección «Fase 4» de `PASOS-CON-SUDO.md`.
