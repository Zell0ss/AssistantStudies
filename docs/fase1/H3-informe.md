# H3 — Informe: preparar el despliegue (lo ejecuta Josem)

Responde a: fa835d3 (H2-revision, «Para el programador»)

## Hecho

- **R4:** `f5a2437` — commit de `docs/fase1/goldens/2026-10-13-final-h2.txt`.
- **R5:** `d6d2bd2` — `test_historial_descarta_intercambio_con_lado_vacio` y
  `test_no_guarda_respuesta_vacia`. **401 tests en verde.**
- **H3:** commit de despliegue (ver `git log fase-1`, el último de código), con:
  - `sebastian2/deploy/PASOS-CON-SUDO.md`, sección «Fase 1», pasos 0–7 en el orden del PLAN §4
    (el 0 es un `mysqldump` recomendado; el 7, la prueba por Telegram), más un apartado «Si hay que
    deshacerlo». Los pasos 1–3 se lanzan desde el worktree, porque `setup_db.sh` y los ficheros de
    las unidades aún no están en `main`.
  - **R3, en el paso 4:** recuadro que explica el `Fatal error starting bot: 'memory_collection'`
    (KeyError) — es la protección de D20, pasa si se arranca el código nuevo sin las variables de la
    unidad ni la clave en `config.yaml`; `Restart=on-failure` reintenta cada 10 s, así que dice cómo
    pararlo y cómo verlo en LogCentral.
  - `sebastian2.service` y `deploy/cuaderno.service` (los ficheros del repo, idénticos a los
    instalados en `/etc/systemd/system/` según `diff`) llevan ahora
    `Environment="SEBASTIAN_DB_NAME=sebastian_db"` y `Environment="SEBASTIAN_MEMORY_COLLECTION=sebastian_memory"`.
    El paso 3 las copia con `sudo cp`; no uso `EnvironmentFile=`.
  - `sebastian2/deploy/comprobar_fase1.sh`, **solo lectura** (sin sudo; no escribe en BD, Qdrant ni
    ficheros). Comprueba las 6 cosas del plan: variables en las dos unidades, línea de arranque del
    bot (`Escribiendo en BD=sebastian_db | memory_collection=sebastian_memory`, vía LogCentral y
    desde la hora de arranque de la unidad), `sebastian_dev` con todas las tablas de
    `sebastian_test`, colección `sebastian_memory_dev` en 1536/Cosine, `config.yaml` sin
    `sebastian_db` y con los valores de dev, y 0 errores en LogCentral desde el reinicio. Sale con 1
    si algo falla.
  - **R3, docs al día:** `docs/DEPLOYMENT_CHECKLIST.md` (sección «Fase 1» al principio: qué
    significan ahora los comandos con `sebastian_db`, que las migraciones ya no llevan `USE`, que
    `run_migration.sh`/`setup_test_db.sh` ya no existen), `docs/COMANDOS.md` (nota sobre
    `sebastian_db`) y `db/verify_database.sh` (acepta la BD como argumento, por defecto
    `sebastian_db`; sigue siendo solo `SHOW`/`DESCRIBE`).

**Probado sin desplegar:** `bash -n` de los dos scripts, y `comprobar_fase1.sh` en seco contra el
estado de hoy. Resultado esperado: FALLO en todo lo que el despliegue aún no ha hecho (variables de
las unidades, línea de arranque, `sebastian_dev`, `sebastian_memory_dev`, `config.yaml`), y OK en
«0 errores» y en «`sebastian_db` tiene `conversations`». El script no se ha podido probar en el
caso «todo bien».

## Gasto

0 $ en esta entrega (R4, R5 y H3 no llaman a la API). Total de la fase sin cambios: unos 1,9 $ de
los 2 $ autorizados por Josem el 2026-10-13 en la ventana del arquitecto (ver H2-informe).

## Desviaciones

1. **Lectura de producción:** `comprobar_fase1.sh` consulta `information_schema` de `sebastian_db`
   (solo nombres de tablas) para comprobar que existe `conversations`; lo ejecuté yo en seco, así que
   ha habido **una lectura de metadatos de la BD de producción**, sin leer ni escribir datos. Es una
   comprobación que no estaba en el PLAN §4: la añadí porque el historial (D21) escribe en la BD que
   fijan las unidades, es decir, en producción, y sin esa tabla el bot lo ignoraría con un warning
   (D22) sin avisar. Hoy la tabla existe.
2. El paso 0 (`mysqldump`) no estaba en el PLAN §4; es una recomendación, no un requisito.
3. Para los pasos 1–3 el PLAN decía «merge después»; por eso el documento los lanza desde
   `/data/AssistantStudies-fase1/sebastian2`.
4. Lo que hace el `config.yaml` de producción tras el paso 5 es **desarrollo**, pero el bot sigue
   en `sebastian_db` por las unidades; lo explico al principio del documento. En la prueba de
   Telegram, el historial entra en `sebastian_db` (la tabla `conversations` de producción).

## Cosas que he visto y no he tocado

- `/etc/systemd/system/sebastian.service` y `cuaderno.service` son los instalados: no los he tocado
  (solo `diff`).
- `sebastian_memory_dev` queda vacía; el cuaderno y la memoria del bot seguirán usando
  `sebastian_memory` (4 puntos hoy) mientras las unidades lo fijen.
- La inconsistencia de nombre: en el repo la unidad es `sebastian2.service` y en `/etc` es
  `sebastian.service` (por eso el `cp` del paso 3 renombra).

## Decisiones que necesito

Ninguna.

## Parada

H3 listo para que Josem despliegue. Merge, reinicio y sudo los ejecuta él (pasos 1–6 de
`PASOS-CON-SUDO.md`); no he hecho ninguno. Tras su prueba por Telegram, el arquitecto cierra la fase.
