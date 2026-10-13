# H1 (fase 1) — Revisión del arquitecto

Responde a: be9ae3e (H1-informe)

**Veredicto: aprobado con retoques.** Los retoques son de medición y de rastro; no cambian el
código de H1. Se hacen dentro de H2, antes de su pasada de goldens.

## 1. Comprobado contra el código (`ee0e4f7`)

- **Override del entorno** (`utils/config.py`). Un único punto, aplicado en `load_config`, y
  `db/connection.load_config()` ya pasa por `get_config()`. He buscado otros lectores del YAML o
  `pymysql.connect` con la BD de la config: solo queda el de `tests/golden/conftest.py`, que fija
  `TEST_DB_NAME` a mano y tiene su propio guardarraíl. Correcto.
- **Sin nombres de producción por defecto.** `tool_executor` y `despertar.main()` leen
  `config["memory_collection"]` sin valor por defecto. Las apariciones de `"sebastian_memory"`
  que quedan en `tests/test_cuaderno_*` van contra un Qdrant simulado y no llegan a ninguna
  colección real. Correcto.
- **Migraciones sin `USE`**, y `setup_db.sh` rechaza cualquier nombre fuera de la lista antes de
  llamar a `sudo` o a `mysql`. T1.7 lo prueba con binarios falsos. Correcto.
- **Guardarraíl de `conftest.py`.** Fija el entorno antes de importar la app y aborta con
  `pytest.exit`. La validación rompiéndolo está contada en el informe. Correcto.
- **Suite:** lanzada por mí en el worktree: `391 passed, 49 deselected`.
- **Desviaciones 1–4:** aceptadas. T1.6 se prueba en `main()` porque es ahí donde se lee la
  config. La alternativa sería que `despertar()` leyera la config él mismo, y sería peor.

## 2. Hallazgos

### 2.1 No hay coste por modelo — hueco del plan (arquitecto) y de la entrega (programador)

El plan pedía «el informe da el coste por modelo», pero no decía cómo medirlo. Eso es mío. El
dato sí se puede sacar: `Orchestrator._track_usage(response, model)` ve cada respuesta con su
modelo y su `usage`. Se perdía porque los logs de los tests van a un directorio temporal.

**Pido (R1):**
- El runner de goldens (`tests/golden/conftest.py`) envuelve `_track_usage` y acumula
  `input_tokens` y `output_tokens` **por modelo** durante toda la sesión.
- `pytest_terminal_summary` imprime una tabla «modelo · tokens entrada · tokens salida · $»,
  con 1 $ / 5 $ por millón para Haiku 4.5 y 3 $ / 15 $ para Sonnet 4.6. Son los precios del plan
  §1; van como constantes con esa referencia en un comentario.
- **Prueba:** un test unitario del acumulador (sin red) que, con dos respuestas falsas de
  modelos distintos, comprueba los totales por modelo y el coste.

### 2.2 Golden #28 sin rastro — programador

«No guardé el mensaje del fallo». Una pasada de goldens cuesta dinero, y si falla algo sin dejar
rastro, hay que pagarla otra vez para entender qué pasó.

**Pido (R2):** cada pasada **[API]** deja su salida completa (el informe del harness, con la
tabla de R1) en `docs/fase1/goldens/<fecha>-<etiqueta>.txt`, y el commit va con el informe que la
cita. Si el #28 vuelve a fallar en la pasada de H2, se apunta como intermitente con las dos
salidas. Nada de reescribirlo.

### 2.3 Para H3: el bot falla al arrancar si faltan las variables — a favor, pero hay que decirlo (arquitecto)

El `config.yaml` de producción no tiene `memory_collection`. Si se hace el merge antes de poner
las variables en las unidades, el bot cae al arrancar con `KeyError`. Es el comportamiento
correcto, porque falla en vez de escribir donde no toca, y el orden de PLAN §4 ya lo evita.

**Pido (R3, en H3):** `PASOS-CON-SUDO.md` lo dice en el paso 4, para que Josem sepa qué
significa ese error si lo ve. Además, `docs/COMANDOS.md`, `docs/DEPLOYMENT_CHECKLIST.md` y
`db/verify_database.sh` se ponen al día, como propones en «Cosas que he visto».

## 3. Gasto

Una pasada completa más una repetición, dentro del tope de 2 $. Quedan como mucho dos pasadas
completas (H2 y, si hace falta, una de retoques). Con R1, el informe de H2 tiene que dar el
coste medido.

## Para el programador

Responde a: be9ae3e (H1-informe)

H1 aprobado. **Adelante con H2**, en este orden:

1. **R1:** medición de tokens y coste por modelo en el harness, con su test unitario (§2.1).
2. **R2:** carpeta `docs/fase1/goldens/` para la salida de cada pasada **[API]** (§2.2).
3. H2 según el PLAN §3: repo, borrar `ChatModule`, orquestador, T2.1–T2.13, aislamiento del
   harness, campo `historia`, y goldens #50–#52 escritos antes del código.
   - La pasada de línea base de #50–#52 va **sin** el historial implementado y solo con esos
     tres (`-k`), para no gastar una pasada completa.
   - Después, una pasada completa al final de H2.
4. **Para** en H2 con `docs/fase1/H2-informe.md`, con el coste medido por modelo.

R3 es para H3; no lo adelantes.
