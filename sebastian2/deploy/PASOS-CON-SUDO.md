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
