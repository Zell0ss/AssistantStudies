# Pasos con sudo

Pasos que **ejecuta Josem** (el programador no usa sudo ni toca producción). Cada sección es una
fase; se hace en el orden escrito.

---

## Fase 1 — Producción y desarrollo separados, y contexto entre turnos (D19, D20, D25)

**Qué cambia al terminar:** la BD y la colección de Qdrant que usa cada proceso las fijan las
**unidades systemd** (producción: `sebastian_db` / `sebastian_memory`). El `config.yaml` del
directorio de producción pasa a apuntar a **desarrollo** (`sebastian_dev` / `sebastian_memory_dev`),
así que un script lanzado a mano ya no escribe en producción por accidente. Los tests usan siempre
`sebastian_test`.

**Qué NO cambia:** el bot sigue escribiendo en `sebastian_db`, porque la unidad lo fija. El
`config.yaml` solo manda cuando se ejecuta algo a mano.

**Rutas:** `/data/AssistantStudies` (producción, siempre en `main`) y
`/data/AssistantStudies-fase1` (worktree de la rama `fase-1`). Hasta el paso 4, el código nuevo
solo está en el worktree: por eso los pasos 1 a 3 se lanzan desde allí.

### Paso 0 — Copia de seguridad (recomendado)

```bash
mysqldump -u root -p sebastian_db > ~/sebastian_db_backup_$(date +%Y%m%d_%H%M%S).sql
```

### Paso 1 — Crear la BD `sebastian_dev` (sudo mysql)

```bash
cd /data/AssistantStudies-fase1/sebastian2
bash db/setup_db.sh sebastian_dev
```

Crea la BD, da permisos a `sebastian_user` y aplica todas las migraciones. Acaba listando las
tablas; deben salir las mismas que en `sebastian_test`. El script se niega con `sebastian_db`.

### Paso 2 — Crear la colección `sebastian_memory_dev` en Qdrant

Misma configuración que `sebastian_memory` y `sebastian_memory_test` (1536 dimensiones, Cosine):

```bash
curl -X PUT localhost:6333/collections/sebastian_memory_dev \
  -H 'Content-Type: application/json' \
  -d '{"vectors": {"size": 1536, "distance": "Cosine"}}'
```

Debe contestar `"result":true`. La colección empieza vacía: es la de desarrollo.

### Paso 3 — Poner las variables en las dos unidades (sudo) — **antes** de tocar nada más

Los ficheros del repo ya llevan las dos líneas `Environment=`. Con `diff` se ve que es lo único que
cambia respecto a lo instalado:

```bash
cd /data/AssistantStudies-fase1/sebastian2
diff /etc/systemd/system/sebastian.service sebastian2.service
diff /etc/systemd/system/cuaderno.service  deploy/cuaderno.service

sudo cp sebastian2.service        /etc/systemd/system/sebastian.service
sudo cp deploy/cuaderno.service   /etc/systemd/system/cuaderno.service
sudo systemctl daemon-reload
systemctl show -p Environment sebastian.service cuaderno.service
```

La última orden tiene que mostrar `SEBASTIAN_DB_NAME=sebastian_db` y
`SEBASTIAN_MEMORY_COLLECTION=sebastian_memory` en las dos. `daemon-reload` **no** reinicia nada: el
bot sigue con el código viejo, que ignora esas variables.

### Paso 4 — Merge de `fase-1` en producción

```bash
cd /data/AssistantStudies
git status          # debe estar limpio y en main
git merge --ff-only fase-1
```

(Hoy `main` no ha avanzado desde que se creó la rama, así que el `--ff-only` entra. Si no entra,
no lo fuerces: avisa al arquitecto.)

> **Si ves `Fatal error starting bot: 'memory_collection'` (un `KeyError`) al arrancar:** significa
> que el bot arrancó con el código nuevo **sin** las variables de las unidades y con un
> `config.yaml` que no tiene `memory_collection`. **No es un fallo del código**: es la protección
> de D20, que prefiere caerse a escribir en una colección que no toca. Es lo que pasa si se hace el
> merge y el reinicio antes del paso 3. `Restart=on-failure` lo reintentará cada 10 s: páralo con
> `sudo systemctl stop sebastian.service`, haz el paso 3 y arranca otra vez. (Se ve con
> `logcentral query --source sebastian --level error`.)

### Paso 5 — Poner el `config.yaml` de producción en desarrollo

Solo ahora, a mano, en `/data/AssistantStudies/sebastian2/config.yaml` (no está en git):

```yaml
mariadb:
  database: "sebastian_dev"        # era "sebastian_db"
  # …el resto igual
memory_collection: sebastian_memory_dev   # clave nueva, a nivel raíz
```

Tras esto el fichero **no debe** contener la cadena `sebastian_db` en ningún sitio.

### Paso 6 — Reiniciar y comprobar

```bash
sudo systemctl restart sebastian.service
bash /data/AssistantStudies-fase1/sebastian2/deploy/comprobar_fase1.sh   # o deploy/… ya desde main
```

El script es de **solo lectura** (no usa sudo, no escribe en ninguna BD ni en Qdrant). Comprueba las
variables de las dos unidades, que el log de arranque del bot diga `sebastian_db` /
`sebastian_memory` (la unidad manda sobre el `config.yaml`), que `sebastian_dev` y
`sebastian_memory_dev` existan, que `sebastian_db` tenga la tabla `conversations`, que el
`config.yaml` ya no mencione `sebastian_db` y que no haya errores en LogCentral desde el reinicio.
Termina con `Todo bien.` o con la lista de FALLOS.

### Paso 7 — Prueba por Telegram

1. «¿qué tiempo hace en Madrid?»
2. «¿y mañana?»

La segunda tiene que contestar sobre Madrid mañana, **sin preguntar la ciudad**. Si pregunta qué
ciudad, el historial no está llegando: `logcentral query --source sebastian --grep "Historial"` debe
mostrar `intercambios=1` (o más) en el segundo turno; si hay un warning de «No se pudo leer el
historial», dímelo con su hora.

### Si hay que deshacerlo

Las variables de las unidades son inofensivas para el código viejo. Para volver atrás:

```bash
sudo systemctl stop sebastian.service
cd /data/AssistantStudies && git reset --hard b96e5e0     # main de antes de la fase 1
# y en config.yaml: database "sebastian_db"; la clave memory_collection puede quedarse
sudo systemctl start sebastian.service
```

`sebastian_dev` y `sebastian_memory_dev` pueden quedarse: no los usa nadie.

---

## Fase 2 — Memoria v1: hechos que se pueden corregir (D31–D43)

**Qué cambia al terminar:** la memoria de Sebastian deja de ser una lista plana de frases en Qdrant y pasa a ser
**hechos con vigencia en MariaDB** (`mem_*`): «Paco · alergia: frutos secos», con su historial («¿qué presión llevaba
antes?»), corregibles («me equivoqué») y olvidables («olvida lo de…», que **borra el texto**, D42). Cada hecho guarda la
frase de la que salió (`mem_fuentes`, D41). Los 3 recuerdos que había en Sprint 3 se migran. El cuaderno saca su semilla de
memoria de MariaDB.

**Qué NO cambia:** la colección `sebastian_memory` (Sprint 3) **no se borra** en esta fase: queda como archivo (D18).
Tampoco cambian las unidades systemd ni el `config.yaml`.

**Rutas:** `/data/AssistantStudies` (producción, siempre en `main`) y `/data/AssistantStudies-fase2` (worktree de la rama
`fase-2`). Hasta el paso 3, el código nuevo solo está en el worktree: por eso los pasos 1 y 2 se lanzan desde allí.

**Gasto:** una sola llamada de pago, en el paso 5 (OpenAI, embebe unas 15 frases: menos de 0,001 $).

### Paso 0 — Requisitos y copia de seguridad

El código de la fase 2 necesita el `.venv` de H0 (Python 3.12 y anthropic 1.14). Si todavía tienes el de Python 3.11 y
anthropic 0.79, haz antes el «Despliegue definitivo» de `docs/fase2/H0-informe.md`.

```bash
/data/AssistantStudies/sebastian2/.venv/bin/python -V                          # Python 3.12.x
/data/AssistantStudies/sebastian2/.venv/bin/pip show anthropic | grep ^Version # 1.14.x
git -C /data/AssistantStudies rev-parse HEAD     # APUNTA este hash: es la vuelta atrás
sudo mysqldump sebastian_db > ~/sebastian_db_backup_$(date +%Y%m%d_%H%M%S).sql
```

### Paso 1 — Migraciones 010, 011 y 012 en `sebastian_db` (sudo mysql)

En este orden. Son idempotentes (`IF NOT EXISTS`, `INSERT IGNORE`) y no llevan `USE`: la BD la eliges tú aquí.

```bash
cd /data/AssistantStudies-fase2/sebastian2
sudo mysql sebastian_db < db/migrations/010_memoria.sql
sudo mysql sebastian_db < db/migrations/011_memoria_semillas.sql
sudo mysql sebastian_db < db/migrations/012_memoria_fuentes.sql
sudo mysql sebastian_db -e "SHOW TABLES LIKE 'mem_%'; SHOW COLUMNS FROM mem_hechos LIKE 'fuente_id';"
```

Deben salir 7 tablas (`mem_entidades`, `mem_entidad_alias`, `mem_atributos`, `mem_atributo_alias`, `mem_hechos`,
`mem_decisiones`, `mem_fuentes`) y la columna `fuente_id`. Las tablas nuevas no molestan al código viejo.

### Paso 2 — Crear las colecciones `sebastian_memory_catalogo` y `sebastian_memory_notas` en Qdrant

La base se pasa explícita porque el `config.yaml` apunta a desarrollo (D19). La herramienta se niega con una base que no
termine en `_test` o `_dev` si no lleva `--produccion`.

```bash
cd /data/AssistantStudies-fase2/sebastian2
SEBASTIAN_MEMORY_COLLECTION=sebastian_memory .venv/bin/python -m scripts.memoria.crear_colecciones --produccion
```

Debe imprimir `OK sebastian_memory_catalogo` y `OK sebastian_memory_notas`. Repetirlo no es un error.

### Paso 3 — Merge de `fase-2` en producción

```bash
cd /data/AssistantStudies && git status        # debe estar limpio y en main
git merge --ff-only fase-2
```

El bot sigue con el código viejo en memoria hasta el reinicio del paso 6.

### Paso 4 — Migrar los recuerdos de Sprint 3 a MariaDB

`SEBASTIAN_DB_NAME` y `SEBASTIAN_MEMORY_COLLECTION` van **explícitos en la línea**, porque el `config.yaml` apunta a
desarrollo (D19). Primero `--dry-run`, que no escribe nada y enseña de qué texto sale cada hecho:

```bash
cd /data/AssistantStudies/sebastian2
SEBASTIAN_DB_NAME=sebastian_db SEBASTIAN_MEMORY_COLLECTION=sebastian_memory \
  .venv/bin/python -m scripts.memoria.migrar_sprint3 --produccion --dry-run
```

Tienen que salir **tres** líneas «escribiría»: la alergia al ácido acetilsalicílico, las camisetas UV (con el sujeto corregido
a «Uso camisetas UV para bañarme») y la presión de las ruedas (una sola vez; el duplicado se descarta). Si sale algún
«sin mapa» que debería migrarse, **para y dímelo**. Si está bien, lo mismo sin `--dry-run`:

```bash
SEBASTIAN_DB_NAME=sebastian_db SEBASTIAN_MEMORY_COLLECTION=sebastian_memory \
  .venv/bin/python -m scripts.memoria.migrar_sprint3 --produccion
```

Lee `sebastian_memory` (solo lectura) y no escribe en Qdrant. Repetirlo no duplica nada, ni resucita lo que olvides después.

### Paso 5 — Indexar el catálogo (OpenAI, menos de 0,001 $)

*Es una adición del programador al plan:* sin este paso `sebastian_memory_catalogo` está vacío y la resolución semántica de
atributos (D35) no encuentra nada. Va después de migrar, para que `presion_neumaticos` y la entidad «coche» entren.

```bash
cd /data/AssistantStudies/sebastian2
SEBASTIAN_DB_NAME=sebastian_db SEBASTIAN_MEMORY_COLLECTION=sebastian_memory \
  .venv/bin/python -m scripts.memoria.indexar_catalogo --produccion
```

Debe imprimir `OK sebastian_memory_catalogo: N atributo(s) y 2 entidad(es) de <tu id>`. Es idempotente.

### Paso 6 — Reiniciar

```bash
sudo systemctl restart sebastian.service
```

### Paso 7 — Comprobar (solo lectura)

```bash
bash /data/AssistantStudies/sebastian2/deploy/comprobar_fase2.sh
```

No usa sudo, no escribe en ninguna BD ni en Qdrant y no llama a ninguna API. Comprueba que producción está en `main` y sin
`modules/memory.py`, que las dos unidades siguen fijando `sebastian_db` / `sebastian_memory`, que el log de arranque lo
confirma, que `sebastian_db` tiene las 7 tablas de la memoria y `mem_hechos.fuente_id`, las semillas activas y los 3 hechos
migrados, que las colecciones nuevas existen (1536, Cosine) y están indexadas, que `sebastian_memory` sigue ahí y que no hay
errores en LogCentral desde el reinicio. Termina con `Todo bien.` o con la lista de FALLOS.

### Paso 8 — Prueba por Telegram

1. «¿Qué sabes de mí?» → tiene que contar la alergia al ácido acetilsalicílico y las camisetas UV (y la presión de las ruedas
   del coche), sin inventar nada más.
2. «Mi coche ahora lleva 2,4 bares» → tiene que decir que **corrige** los 2,30 anteriores.
3. «¿Qué presión llevaba antes?» → tiene que decir 2,30 bares.

Si algo no cuadra: `logcentral query --source sebastian --level error` y dímelo con la hora.

### Si hay que deshacerlo

Las tablas `mem_*`, las colecciones nuevas y los hechos migrados no molestan al código viejo, así que basta con volver al
`main` anterior (el hash que apuntaste en el paso 0) y reiniciar:

```bash
sudo systemctl stop sebastian.service
cd /data/AssistantStudies && git reset --hard <el hash del paso 0>
sudo systemctl start sebastian.service
```

La colección `sebastian_memory` (Sprint 3) **no se borra** en esta fase, así que el bot viejo sigue teniendo sus recuerdos.
Lo que hayas pedido olvidar con el bot nuevo ya no se puede recuperar (D42 borra el texto): no es un fallo de la vuelta atrás.

---

## Fase 3 — Prospectiva: Sebastian habla primero (D45–D54)

**Qué cambia al terminar:** Sebastian guarda **compromisos** (cosas que tienes que hacer un día o a una hora, sueltas o atadas a
una cita, como los pasos de preparar una prueba médica) y **te escribe él primero**: un resumen a las 08:00 con lo de hoy y
un aviso por Telegram a la hora de cada compromiso con hora (incluida la madrugada, D48). Cuatro tools nuevas
(`compromisos_crear`, `_listar`, `_completar`, `_borrar`) y una tabla nueva, `compromisos` (migración 013). Si una cita se
mueve, sus compromisos se mueven con ella (D50); crear uno que ya existe pendiente para esa cita no lo duplica (R13).

**Qué NO cambia:** las unidades systemd, el `config.yaml` y Qdrant. La migración **solo crea una tabla**: no toca ninguna
existente, así que el código anterior sigue funcionando con ella puesta.

**Rutas:** `/data/AssistantStudies` (producción, siempre en `main`) y `/data/AssistantStudies-fase3` (worktree de la rama
`fase-3`). Hasta el paso 2, el código nuevo solo está en el worktree: por eso el paso 1 se lanza desde allí.

**Gasto:** ninguno de pago en los pasos. Después, cada mensaje por Telegram es uso normal de la API de Anthropic.

**Plazo:** desplegar **antes del 10/12** y hacer la prueba real **antes del 7/12**. La dieta empieza el lunes 14/12 y la cita es el
jueves 17/12 (el aviso de la 01:00 de ese día es el indicador de D48).

### Paso 0 — Requisitos y copia de seguridad

La rama `fase-3` incluye la fase 2: antes de seguir, la fase 2 tiene que estar desplegada y sana.

```bash
bash /data/AssistantStudies/sebastian2/deploy/comprobar_fase2.sh      # debe terminar con «Todo bien.»
git -C /data/AssistantStudies rev-parse HEAD     # APUNTA este hash: es la vuelta atrás
sudo mysqldump sebastian_db > ~/sebastian_db_backup_$(date +%Y%m%d_%H%M%S).sql
```

### Paso 1 — Migración 013 en `sebastian_db` (sudo mysql)

Es idempotente (`IF NOT EXISTS`) y no lleva `USE`: la BD la eliges tú aquí.

```bash
cd /data/AssistantStudies-fase3/sebastian2
sudo mysql sebastian_db < db/migrations/013_compromisos.sql
sudo mysql sebastian_db -e "SHOW COLUMNS FROM compromisos;"
```

Debe salir la tabla con 14 columnas (de `id` a `updated_at`, incluida `aviso_para`).

### Paso 2 — Merge de `fase-3` en producción

```bash
cd /data/AssistantStudies && git status        # debe estar limpio y en main
git merge --ff-only fase-3
```

El bot sigue con el código viejo en memoria hasta el reinicio del paso 3.

### Paso 3 — Reiniciar

```bash
sudo systemctl restart sebastian.service
```

### Paso 4 — Comprobar (solo lectura)

```bash
bash /data/AssistantStudies/sebastian2/deploy/comprobar_fase3.sh
```

No usa sudo, no escribe en ninguna BD ni en Qdrant, no llama a ninguna API de pago y **no manda nada por Telegram**. Comprueba que
producción está en `main` con la fase 3, que las dos unidades siguen fijando `sebastian_db`, que el log de arranque dice que el bot
escribe en `sebastian_db` y que el planificador arrancó con los avisos cada minuto, que `sebastian_db` tiene `compromisos` con sus 14
columnas, una prueba seca de `armar_resumen` con la fecha de mañana (construye el texto, no lo envía; con `MOSTRAR=1` te lo enseña
en la terminal) y que no hay errores en LogCentral desde el reinicio. No imprime el texto de ningún compromiso (D52). Termina con
`Todo bien.` o con la lista de FALLOS.

### Paso 5 — Prueba real por Telegram (con el arquitecto)

Es el caso de verdad, `CASO-COLONOSCOPIA.md`. **Dicta fechas absolutas** («el jueves 17 de diciembre a las 9:30», «el lunes 14 de
diciembre empiezo la dieta, tres días») y **no le cuentes resultados de pruebas ni diagnósticos**: Sebastian no los guarda (D52)
y, si se lo cuentas, el texto podría acabar en el registro de salud (Tristras). Tras cada mensaje, dile al arquitecto qué
dictaste: él comprueba en `sebastian_db` que cada compromiso es el que debe (un solo evento, todos con `evento_id`, nada duplicado,
la segunda toma a la 01:00 **del día de la cita**).

1. Dicta la cita y, en otro mensaje, la preparación (dieta, tomas, última hora para líquidos).
2. «¿Qué tengo que hacer esta semana?» → tiene que listar tus compromisos con sus fechas.
3. Si mueves la cita («me la han cambiado al…»), comprueba que **no** aparecen los pasos duplicados.
4. **Indicador de D48:** el aviso de la 01:00 del 17/12 tiene que llegar a su hora. Si no llega, díselo al arquitecto con la hora.

Si algo no cuadra: `logcentral query --source sebastian --level error` y dímelo con la hora.

### Si hay que deshacerlo

La tabla `compromisos` no molesta al código viejo, así que basta con volver al `main` anterior (el hash del paso 0) y reiniciar:

```bash
sudo systemctl stop sebastian.service
cd /data/AssistantStudies && git reset --hard <el hash del paso 0>
sudo systemctl start sebastian.service
```

Dos cosas que hay que saber antes de hacerlo:

- **No se ejecuta `DROP TABLE compromisos` sin preguntar**: borraría para siempre lo que hayas dictado, y la tabla no estorba.
- El código viejo no sabe de compromisos. Una cita que tenga compromisos pendientes **no se podrá borrar** con el bot viejo (la FK de
  `compromisos.evento_id` no lleva `ON DELETE`). Si hay que borrar una cita en ese estado, se pregunta antes cómo hacerlo.

## Fase 4 — Vigilancias: Sebastian busca por ti cada mañana (D63–D67)

**Qué cambia al terminar:** Sebastian repite cada mañana las búsquedas de una **vigilancia** en Wallapop y te manda por Telegram un
resumen con lo que merece la pena según tus reglas. La tuya es «Mac mini para LLM local» (8 búsquedas, a las 07:30). Dos tablas
nuevas, `vigilancias` y `vigilancia_vistos` (migración 014), y una tarea nueva del planificador, cada 15 minutos. Las vigilancias
son **de solo lectura**: buscan e informan, y no crean, mueven ni borran nada. Todavía no se gestionan por chat (H2): se cargan
con un script.

**Qué NO cambia:** las unidades systemd, el `config.yaml` y Qdrant. La migración **solo crea dos tablas**: no toca ninguna
existente, así que el código anterior sigue funcionando con ellas puestas.

**Rutas:** `/data/AssistantStudies` (producción, siempre en `main`) y `/data/AssistantStudies-fase4` (worktree de la rama
`fase-4`). Hasta el paso 2, el código nuevo solo está en el worktree: por eso el paso 1 se lanza desde allí.

**Gasto:** cada ronda llama a Haiku 4.5 una vez, con menos de 10 candidatos: del orden de 0,005 $ al día. Las 8 peticiones a Wallapop
son gratis y sin clave.

### Paso 0 — Requisitos y apuntes (a mano, sin sudo)

La fase 3 tiene que estar desplegada y sana. Apunta tu **id de Telegram** (el que usas en `authorized_ids`): lo pide el paso 3.

```bash
bash /data/AssistantStudies/sebastian2/deploy/comprobar_fase3.sh
git -C /data/AssistantStudies rev-parse HEAD
git -C /data/AssistantStudies status
```

La primera debe terminar con «Todo bien.». La segunda da el hash que **tienes que apuntar**: es la vuelta atrás. La tercera debe
decir que estás en `main` y que el árbol está limpio.

### Paso 1 — Copia de seguridad y migración 014 en `sebastian_db`

Es idempotente (`IF NOT EXISTS`) y no lleva `USE`: la BD la eliges tú aquí. Una sola línea, para pegar entera:

```bash
cd /data/AssistantStudies-fase4/sebastian2 && sudo mysqldump sebastian_db > ~/sebastian_db_backup_$(date +%Y%m%d_%H%M%S).sql && sudo mysql sebastian_db < db/migrations/014_vigilancias.sql && sudo mysql sebastian_db -e "SHOW TABLES LIKE 'vigilancia%';"
```

Debe salir la lista con `vigilancia_vistos` y `vigilancias`.

### Paso 2 — Merge de `fase-4` en producción

```bash
cd /data/AssistantStudies && git status && git merge --ff-only fase-4
```

El bot sigue con el código viejo en memoria hasta el reinicio del paso 4.

### Paso 3 — Cargar tu vigilancia

Sin sudo. La variable que fija la BD es **`SEBASTIAN_DB_NAME`** (no `DB_NAME`): sin ella, la carga iría a la BD de desarrollo. Cambia
`<tu id>` por tu id de Telegram.

```bash
cd /data/AssistantStudies/sebastian2 && SEBASTIAN_DB_NAME=sebastian_db .venv/bin/python -m scripts.vigilancias.cargar /data/library/mi-wiki/docs/Obsidian/30-projects/sebastian/vigilancias/mac-mini.yaml --user <tu id>
```

Tiene que imprimir **«Escribiendo en BD: sebastian_db»** y una línea «creada id=… «Mac mini para LLM local»». Si dice otra BD, no
sigas. Es seguro repetirlo: actualiza la vigilancia sin duplicarla.

**La hora a la que lo haces no importa.** Si cargas la vigilancia con su ventana de hoy ya cerrada (pasadas las 09:30 con `hora` a las
07:30), no te llega ningún «⚠️ Hoy no pude hacer la vigilancia…»: la carga marca ese aviso como ya dado para hoy, y la primera ronda
sale mañana. Si la cargas dentro de la ventana (entre las 07:30 y las 09:30), la ronda sale en la pasada siguiente.

### Paso 4 — Reiniciar

```bash
sudo systemctl restart sebastian.service
```

### Paso 5 — Comprobar (solo lectura)

```bash
bash /data/AssistantStudies/sebastian2/deploy/comprobar_fase4.sh
```

No usa sudo, no escribe en ninguna BD, no llama a ninguna API y **no manda nada por Telegram**. Comprueba que producción está en `main`
con la fase 4, que las dos unidades siguen fijando `sebastian_db`, que el log de arranque dice que el bot escribe en `sebastian_db` y que
el planificador arrancó **con las vigilancias**, que `sebastian_db` tiene las dos tablas con sus columnas y tu vigilancia activa y con
hora, cuántas rondas ha habido desde el reinicio y que no hay errores en LogCentral. No imprime consultas, reglas ni títulos (D42).
Termina con `Todo bien.` o con la lista de FALLOS.

### Paso 6 — La primera ronda

La ronda sale **cada día entre las 07:30 y las 09:30** (la tarea mira cada 15 minutos; la ventana es de 2 horas). Mañana por la
mañana tendría que llegarte un mensaje que empieza por «🔎 Mac mini para LLM local · <día/mes>». Si no hay nada nuevo que merezca la
pena, llega igualmente: «Nada nuevo que merezca la pena.» es la prueba de que corrió. Si a las 09:30 no ha salido, llega un
«⚠️ Hoy no pude hacer la vigilancia…». Díselo entonces al arquitecto, con la hora, y ejecuta
`logcentral query --source sebastian --grep "Vigilancia id="`.

Para verla **hoy**, sin esperar a mañana: copia el YAML a `/tmp`, cambia `hora` a unos 20 minutos más tarde y cárgalo con el comando del
paso 3 (apuntando a la copia). Cuando haya salido la ronda, vuelve a cargar el original del vault: el nombre es el mismo y la hora vuelve
a las 07:30. Esa ronda de hoy deja sus anuncios como vistos: mañana solo saldrán los nuevos.

### Si hay que deshacerlo

Las tablas nuevas no molestan al código viejo, así que basta con volver al `main` anterior (el hash del paso 0) y reiniciar. Cambia
`<hash>` por el que apuntaste, y pega la línea entera:

```bash
sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard <hash> && sudo systemctl start sebastian.service
```

Dos cosas que hay que saber antes de hacerlo:

- **No se ejecuta `DROP TABLE vigilancias` sin preguntar**: borraría tu vigilancia y lo que lleva visto, y la tabla no estorba.
- Para **pausar la vigilancia sin tocar el código** (por ejemplo, si Wallapop corta la API y llegan avisos de fallo cada mañana), en una sola línea:

```bash
sudo mysql sebastian_db -e "UPDATE vigilancias SET activa = 0 WHERE nombre = 'Mac mini para LLM local';"
```

  Para reactivarla, vuelve a cargar el YAML (paso 3): `activa` vale verdadero por defecto.

Las colecciones de Qdrant y la memoria de la fase 2 no cambian en esta fase.
