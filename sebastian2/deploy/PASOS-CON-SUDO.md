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
