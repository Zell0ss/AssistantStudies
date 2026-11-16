# H4 — informe (fase 3): R13 y preparación del despliegue

> Responde a: d69bd76 (H3-revision, cuarta revisión, «Para el programador»). Programador, 2026-11-16. Rama `fase-3`,
> commits `4399041` (R13 y golden #49) y `54aead6` (comprobar_fase3.sh y pasos con sudo). Todo sin API, sin Telegram real y
> sin tocar producción: no he fusionado, migrado ni reiniciado nada.

## Hecho

- **R13 — `compromisos_crear` no duplica** (`modules/compromisos.py`). Si un compromiso del lote coincide en texto con uno
  **pendiente** del mismo usuario y el mismo `evento_id`, no se inserta. El texto se compara normalizado (sin mayúsculas, sin
  espacios en los extremos y con los internos colapsados). Los hechos y los cancelados no cuentan; los sueltos (sin
  `evento_id`) no se comparan; un lote inválido sigue sin dejar nada.
  - **Salida:** ese compromiso vuelve **en su sitio del lote**, con su id y su momento ya calculado, marcado `"ya_existe": true`.
    El resto del lote se crea. `status` es `created` si se creó algo y **`exists`** si todo el lote ya estaba (mismo patrón que R3).
  - **Descripción** de `compromisos_crear`: «Si la cita se ha movido, sus pasos ya se movieron solos (D50): no los crees otra vez;
    si repites uno que sigue pendiente para esa cita, no se duplica y vuelve con `ya_existe`».
  - **Registro (D52):** solo ids, nunca el texto.
  - **Pruebas** (`tests/test_compromisos_module.py`): `test_crear_no_duplica_pendiente_del_mismo_evento`,
    `…_compara_el_texto_normalizado`, `…_si_el_otro_esta_hecho_o_cancelado_si_crea`, `…_otro_evento_si_crea`,
    `…_otro_usuario_no_cuenta_como_duplicado`, `…_sin_evento_no_compara_los_sueltos_se_pueden_repetir`, `…_lote_mixto_…`,
    `…_un_lote_invalido_no_deja_nada_aunque_algo_ya_existiera`; y la de la descripción en `tests/test_compromisos_tools.py`.
    Vi las tres primeras fallar antes de escribir el código.
- **Golden #49** con la lista de §15: `[[], [inventory_list], [search_memory], [inventory_list, search_memory], [search_memory,
  inventory_list]]`; prueba en `tests/test_golden_estado.py` (no admite `salud` ni `mark_as_memorable`).
- **`deploy/comprobar_fase3.sh`**, solo de lectura (sin sudo, sin API, sin Telegram, sin imprimir textos de compromisos, D52):
  1. producción en `main` y con los ficheros de la fase 3;
  2. las dos unidades fijan `SEBASTIAN_DB_NAME=sebastian_db`;
  3. desde el reinicio, las líneas «Escribiendo en BD=sebastian_db» y «Planificador arrancado … avisos cada minuto» (LogCentral);
  4. `compromisos` con sus 14 columnas, cuentas por estado y ningún compromiso atado a un evento inexistente;
  5. prueba seca de `armar_resumen` con la fecha de mañana (`FECHA=` para otro día) contra `sebastian_db`: construye el texto y dice
     cuántas líneas y viñetas tiene; con `MOSTRAR=1` lo enseña en tu terminal. No envía nada;
  6. 0 errores en LogCentral desde el reinicio.
- **`deploy/PASOS-CON-SUDO.md`, sección «Fase 3»**, con la vuelta atrás (abajo). Prueba estática de ambos ficheros en
  `tests/test_deploy_comprobar_fase3.py` (el script es bash válido, no escribe, no manda nada, el orden de los pasos).
- **Pruebas sin API: 851 pasan** (845 antes del script y su prueba; eran 835 al cerrar H3d).

## Lo que ejecuta Josem, y en qué orden (`deploy/PASOS-CON-SUDO.md`, «Fase 3»)

0. `comprobar_fase2.sh` → «Todo bien.»; anotar `git rev-parse HEAD` de producción (la vuelta atrás); `mysqldump` de `sebastian_db`.
1. `sudo mysql sebastian_db < db/migrations/013_compromisos.sql` (desde `/data/AssistantStudies-fase3/sebastian2`; solo crea una tabla).
2. `git merge --ff-only fase-3` en `/data/AssistantStudies`.
3. `sudo systemctl restart sebastian.service`.
4. `bash deploy/comprobar_fase3.sh` → «Todo bien.»
5. **Prueba real por Telegram**, con el arquitecto, **antes del 7/12**: dictar la cita y la preparación con **fechas absolutas**, sin
   resultados médicos; «¿qué tengo que hacer esta semana?»; mover la cita y comprobar que no se duplican los pasos; el aviso de la 01:00
   del 17/12 (indicador de D48). Despliegue **antes del 10/12**.

**Vuelta atrás:** `git reset --hard <hash del paso 0>` con el servicio parado, y arrancar. La tabla `compromisos` no estorba al código
viejo; **no se ejecuta `DROP TABLE` sin preguntar**. Un matiz que añado: con el código viejo, una cita con compromisos pendientes **no
se puede borrar** (la FK no lleva `ON DELETE`); lo dice la sección.

## Gasto

**0 $.** Ninguna llamada de pago en este paso. La fase 3 queda en ≈ 9,59 $ de los 10 $ autorizados por Josem (quedan ≈ 0,41 $), sin
más [API] como indica §16.

## Desviaciones

- **`status: "exists"`** cuando todo el lote ya estaba; la revisión pedía «va como `ya_existe`», sin decir el `status` del lote. Mi
  elección sigue a R3 (`calendar_add_event`).
- **No deduplico dentro de un mismo lote** (dos iguales en la misma llamada se crean los dos): §16 habla solo de coincidir con un
  pendiente ya guardado.
- **`comprobar_fase3.sh` admite `BD=`** (por defecto `sebastian_db`, y es lo que el paso 4 usa) solo para ensayarlo contra
  `sebastian_test`. Lo ensayé así con `RAIZ` en el worktree: 4 y 5 salen bien; 1 y 3 fallan a propósito (el worktree no está en `main`
  ni es el servicio). **No lo he ejecutado contra producción.**
- Añadí a los pasos un **paso 0 que exige `comprobar_fase2.sh`**: `fase-3` incluye la fase 2.
- R13 **no está probado con el modelo**, como dice §16: la prueba real es la de Josem. Una cosa que mirar ahí: con `status: "exists"` Alfred
  tendría que decir que ya estaba apuntado, no que lo ha creado.

## Decisiones que necesito

1. **¿Está desplegada la fase 2?** Mi `TOMORROW.md` la daba por pendiente del despliegue de Josem; la memoria del repo dice que está en
   producción desde el 15/11. El paso 0 de la fase 3 lo comprueba con `comprobar_fase2.sh`, pero si no lo está, **hay que hacer antes la
   fase 2** (`fase-3` la contiene y el `ff-only` la metería de golpe).
2. **Josem:** los pasos de arriba, en orden, son tuyos (sudo, merge y reinicio). Yo no los ejecuto. Plazo: 10/12; prueba real antes del 7/12.
3. **Arquitecto:** la pregunta de D52 a Tristras (¿acepta resultados o no?) queda pendiente en su registro, según §15; no la toco.
4. Si el arquitecto prefiere que `exists` no cambie el `status` del lote, es un cambio de una línea y una prueba.
