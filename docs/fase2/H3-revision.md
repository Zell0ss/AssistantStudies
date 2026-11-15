# H3 — revisión (fase 2)

> Responde a: 44cf6dc (H3-informe). 2026-11-15, arquitecto. La revisé contra el código de la rama
> `fase-2` en `042b01a`.

**Veredicto: aprobado con retoques.** La lectura, el índice, el vault y la purga de D42 están bien
hechos. El fallo de E5 es serio: Sebastian dice que ha hecho algo que no ha hecho. Hay que
arreglarlo antes de H4.

## 1. Lo que comprobé

- **Pruebas sin API:** `pytest -m "not golden"` da **627 en verde**, lo mismo que dice el informe.
- **Migración 012:** coincide con el contrato §3.1 y es idempotente. Usa
  `ADD FOREIGN KEY IF NOT EXISTS`, que es lo correcto en MariaDB 10.6.
- **D41:**
  - `guardar` crea una fuente por llamada y la purga al final si no dejó ningún hecho
    (`servicio.py:67-71`).
  - El literal llega por `ToolExecutor.mensaje_del_turno`, que se fija una vez por turno
    (`orchestrator.py:425`). Es la costura mínima que pedí.
- **D42:**
  - `retirar_y_purgar` cierra el hecho, vacía su valor y el de toda su cadena, y purga cada fuente
    sin hechos vigentes, todo en una transacción (`repositorio.py`).
  - Los vectores se borran después del commit, y si falla se registra un `warning` sin el texto.
  - R3 también pasa por `_retirar`, así que no hay un camino que cierre sin purgar.
- **R5:** veo bien la segunda redacción. Que funcionase nombrar la tool de destino, cuando la
  prohibición sola no bastó, es una lección que sirve para otras descripciones.

## 2. Hallazgos

### 2.1 E5: el planner da por hecho lo que pide el usuario, y Alfred lo afirma (arquitecto)

Pasa en 5 de 6 pasadas con historial y en 0 de 1 sin él. El historial de D21 lleva el texto del
asistente («Anotado…», «Retirado…») y el planner lo imita sin llamar a la tool. Después Alfred
afirma «Retiro la alergia…» sin que haya ningún resultado de herramienta.

- Va contra D26 (no afirmar lo que no se ha consultado o hecho en el turno).
- Además, ese texto falso entra en `conversations` y alimenta los turnos siguientes.
- El hueco es mío: D21 no previó que el historial enseña a contestar sin actuar.

Registro **D43 (tentativa)** en ADR-MEMORIA. **Decisión 1 del informe: sí**, a las dos reglas que
propones, más una prueba (R8).

### 2.2 E9 pasa por suerte (programador ✓, hueco del plan: arquitecto)

**Decisión 2: (a).** Un `retirar` que no resuelve la entidad con fuerza busca **también entre los
hechos vigentes** del usuario, además de entre las notas (R9).

### 2.3 Lo que D42 no borra (arquitecto)

Hay tres sitios donde el texto olvidado sigue existiendo. Ninguno es fallo de implementación:

- **Una fuente con varios hechos.** Si se olvida uno y el otro sigue vigente, la fuente conserva el
  texto entero. Lo pedí así en §3.2. Es un límite conocido y lo resolverá la consolidación de la
  fase 3.
- **`conversations`** guarda el literal 7 días (D23).
- **El log de inicio de turno** guarda los primeros 200 caracteres de cada mensaje
  (`orchestrator.py:430`). Es anterior a esta fase.

No bloquea H4. Lo anoto en D42 y se lo pregunto a Josem (§4).

### 2.4 Pasada completa antes de leer el buzón (programador)

La pasada completa (1,79 $) se lanzó sin volver a mirar el buzón, cuando el encargo ya estaba
commiteado. La convención §6 pide mirarlo antes de cada paso con gasto que dure. Sirvió (destapó
tres defectos), pero dejó la fase sin margen. Desde ahora: **antes de cada paso [API], `git log`
del buzón.**

### 2.5 Resto de decisiones del informe

| # | Decisión |
|---|---|
| 3 (i) | **Sí.** `_validar` descarta los hechos cuya entidad es un marcador (`<UNKNOWN>`, vacía o entre `<>`). Si no queda ninguno, la respuesta dice que no sabe de quién se habla (R10) |
| 3 (ii) | **Sí, las dos.** Son pruebas normativas mías, así que las cambio yo: el caso 1 pasa a «contiene el hecho esperado» y el caso 2 nombra el coche en la frase (R10) |
| 4 | De acuerdo: es una red, no una prueba. Nada que hacer |
| 5 | **Sí.** La línea de D37 en Alfred dice que no puede cambiar el vault: «si está mal, hay que corregirlo en `proyecto.md`» (R11) |
| 6 | **Sí,** #43 queda como intermitente conocido, igual que #28 |
| 7 | **Confirmo las dos:** `historial` no enseña lo olvidado, que es coherente con D42, y toda nota se embebe. Lo segundo fue un hueco de mi plan |
| 8 | De acuerdo: va a H4 |
| desv. 10 | No hace falta unificar los fixtures |

## 3. Gasto

**≈ 4,51 $ de 5 $**, con la autorización bien anotada. Las cifras cuadran con las salidas guardadas.

Lo que queda **no cabe** en el tope:

| Paso | Estimación |
|---|---|
| Retoques de H3: #66, E5 ×3, `-k` #56–#66 y los 10 casos del extractor | ≈ 0,8 $ |
| H4: pasada completa de goldens (66) y escenarios antes del despliegue | ≈ 2,3 $ |

Total ≈ 3,1 $. **Pido a Josem subir el tope de la fase a 8 $.** Mientras no lo diga, no se lanza
nada [API].

## 4. Para Josem

1. **Tope de gasto:** subir a 8 $. Sin eso, los retoques se quedan sin probar con la API.
2. **D42, lo que no borra** (§2.3): ¿quieres que el log de inicio de turno deje de guardar el
   texto del mensaje? Yo diría que sí, y es barato: pasaría a guardar la longitud y el id. Lo
   de `conversations` (7 días) lo dejaría como está.

## Para el programador

Responde a: 44cf6dc (H3-informe)

H3 aprobado con retoques. Hazlos en este orden, en commits propios. Los pasos **[API]**, solo
cuando Josem suba el tope (§3) y diga «sí» en tu ventana, y mirando el buzón antes de cada uno
(§2.4).

1. **R8 (D43): acciones con historial.**
   - Prompt del planner: «Si el usuario pide guardar, corregir u olvidar algo, llama a
     `mark_as_memorable` **aunque el historial parezca que ya se hizo**: el historial es lo que se
     dijo, no lo que se ha hecho en este turno.»
   - `_ALFRED_SYSTEM`: «No afirmes que has guardado, corregido, olvidado, apuntado o creado nada si
     en este turno no hay un resultado de herramienta que lo diga. Si el usuario lo pidió y no hay
     resultado, di que no lo has hecho.»
   - Golden **#66**, normativo: historia de E4 (los tres turnos) y la frase «Olvida lo del marisco
     de Paco», en modo `exact`, esperando `[mark_as_memorable]`.
   - Prueba sin API: `test_alfred_no_afirma_sin_resultado`, que comprueba que la regla está en el
     prompt.
   - **[API]** #66 ×3 y E5 ×3. El criterio es 3/3 en los dos.
2. **R9: retirar busca también entre los hechos vigentes.**
   - Un `retirar` sin entidad resuelta con fuerza, y sin nota que supere el umbral de R3, busca
     entre los hechos vigentes del usuario aquellos cuyo valor normalizado (§2.4) **contiene** el
     valor que se quiere retirar, ya normalizado.
   - Si hay **un solo** candidato, se retira (con purga, por `_retirar`) con la regla
     `retirar_valor`. Si hay varios, es `sin_cambio` y se pregunta cuál. Si no hay ninguno, el aviso
     de siempre.
   - Sigue la regla de uno por turno, compartida con R3.
   - Pruebas: `test_retirar_por_valor_unico`, `test_retirar_por_valor_ambiguo_no_toca` y
     `test_retirar_por_valor_respeta_uno_por_turno`.
   - Escenario **E9b**: «Uso camisetas UV para bañarme», guardado como `preferencia` (fuerza el
     extractor falso en una prueba sin API), y luego «Olvida lo de las camisetas UV». Tiene que
     quedar cerrado y purgado.
3. **R10: extractor.**
   - `_validar` descarta las entidades marcador. Prueba:
     `test_validar_descarta_entidad_marcador`.
   - Los dos casos normativos cambian como dice §2.5 (3 ii). Es un cambio mío; cítalo en el
     commit.
   - **[API]** Los 10 casos.
4. **R11:** la línea de D37 en Alfred, con su prueba de contenido.
5. **[API]** `-k` #56–#66 (una pasada) y los escenarios E1–E9.
6. **Para** con un anexo en `H3-informe.md`: resultados, gasto por modelo y las respuestas de E5
   pegadas. Si Josem dice «sí» al punto 2 de §4, añade el cambio del log de turno como **R12**, con
   la prueba de que el log no contiene el mensaje.

## 5. Revisión del anexo (2026-11-15)

Responde a: d4b3054 (H3-informe, anexo). La revisé contra `2ec6667` y los commits anteriores.

**Veredicto: H3 aprobado y cerrado.** Quedan dos retoques sin API, que van al principio de H4.

### 5.1 Lo que comprobé

- **Pruebas sin API:** **655 en verde**, lo mismo que dice el anexo.
- **Regla del planner:** `_REGLA_ACCIONES_CON_HISTORIAL` (`orchestrator.py:104`) va al final del
  prompt (`:134`), después del índice.
- **Regla de Alfred:** `orchestrator.py:161`.
- **R12:** el log de inicio de turno ya no lleva el texto. Siguen con él los tres logs de error de
  `handle()` (`:419`, `:424` y `:430`), como dices.
- **E5, de punta a punta:** 3/3, y la BD queda exactamente como pide D42.

### 5.2 Decisiones del anexo

| # | Decisión |
|---|---|
| 1 | **Confirmo la regla C.** Mi texto, en mitad del prompt, daba 0/6: el hueco era mío. Acotarla a «dato de memoria» fue lo correcto, y la verificación de 27 goldens lo respalda. La lección (una regla de comportamiento con historial va al final del prompt, justo antes de decidir) queda en D43 |
| 2 | **No se gasta en esto ahora.** E9 entra en la pasada completa de H4. Si allí vuelve a ir a `salud`, se repite ×3 con y sin la regla C para separar las dos causas, y se informa. No se arregla nada por tu cuenta |
| 3 | **Sí, en llano (R13).** Texto para Alfred: «Si el usuario pidió guardar, corregir u olvidar y en este turno no hay resultado, dile en llano que no lo has hecho y ofrécete a intentarlo de nuevo. No menciones herramientas, resultados ni reglas.» Lleva prueba de contenido, que también compruebe que la regla no contiene «resultado de herramienta» en la frase que se le pide decir |
| 4 | **Sí (R14).** Es el mismo caso que D42 y entra en el «sí» de Josem al log de turno: los tres logs de error guardan la longitud, no el texto. Lleva prueba |
| 5 | Es de Josem (§5.3) |
| 6 | **Sí,** #62 se apunta como intermitente conocido, con #43 y #28 |
| desv. 2 | **Bien visto**, con palabras completas. Mi «contiene» habría cerrado «marzo» al olvidar «M» |
| desv. 4 | Anotado. Para no repetirlo, en `-k` usa los ids exactos (`golden_1 and not golden_1[0-9]`, o el patrón que tenga el harness) |

### 5.3 Gasto

Josem autorizó «hasta 2 €» y se gastaron 1,95 $, así que bien. Lo de subirlo a 8 $ era mi
propuesta, no su «sí», e hiciste bien en no usarlo.

**Acumulado: ≈ 6,46 $.** H4 necesita unos 2,3 $: la pasada completa de 66 goldens (≈ 1,8 $) y
E1–E9 (≈ 0,5 $). **Pido a Josem ≈ 2,5 $ para H4**, con lo que la fase llegaría a unos 9 $. Sin ese
«sí» en tu ventana, H4 se prepara entero pero no se lanza ninguna pasada.

### 5.4 Lo que añado a H4 (arquitecto: el plan es anterior a D41)

- **Paso 4.2 del plan:** se aplican **010, 011 y 012**, en ese orden.
- **Hechos migrados** (`migrar_sprint3.py`): llevan `fuente_id = NULL` y `origen='migracion'`. No
  se inventa una fuente.
- **`deploy/comprobar_fase2.sh`:** comprueba también que existen `mem_fuentes` y
  `mem_hechos.fuente_id`.
- **`test_migrar_sprint3_mapa`:** además comprueba que la alergia al ácido acetilsalicílico queda
  como `alergia`. Con R6 es memoria.

## Para el programador

Responde a: d4b3054 (H3-informe, anexo)

H3 aprobado y cerrado. **Adelante con H4**, en este orden:

1. **R13** (la redacción de Alfred, §5.2-3) y **R14** (los logs de error, §5.2-4), sin API, con
   sus pruebas y en commits propios.
2. **H4** según el plan §3, con lo añadido en §5.4. Todo lo que no gasta va primero: migración,
   cuaderno, borrar `modules/memory.py`, `PASOS-CON-SUDO.md`, `comprobar_fase2.sh` y las pruebas
   normativas.
3. **[API]**, solo con el «sí» de Josem a ≈ 2,5 $ en tu ventana y mirando antes el buzón: la
   pasada completa de 66 goldens y E1–E9. Si E9 vuelve a ir a `salud`, aplica §5.2-2 dentro del
   mismo tope.
4. **Para** en `docs/fase2/H4-informe.md`, listo para el despliegue de Josem. No despliegues, no
   fusiones y no reinicies nada.
