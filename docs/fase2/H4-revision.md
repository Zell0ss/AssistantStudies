# H4 — revisión (fase 2)

> Responde a: d53c0be (H4-informe). 2026-11-15, arquitecto. La revisé contra el código de la rama
> `fase-2` en `d53c0be`.

**Veredicto: aprobado con retoques.** La retirada del Sprint 3, el cuaderno y los pasos de
despliegue están bien. **No se despliega hasta R15 y R16**: sin ellos, Sebastian puede seguir
diciendo «he olvidado X» sin haberlo olvidado.

## 1. Lo que comprobé

- **Pruebas sin API:** `pytest -m "not golden"` da **674 en verde**, lo mismo que el informe.
- **Pasos del despliegue:** 010, 011 y 012 se aplican en orden, el `--dry-run` es obligatorio
  antes de migrar y la vuelta atrás está escrita.

## 2. Hallazgos

### 2.1 E5: la mentira la dice Alfred, y en código se puede cortar (arquitecto)

Lo vi en `orchestrator.py:549-570`. Cuando el planner no llama a ninguna tool, `_synthesize`
recibe `tool_results` vacío y le pasa a Alfred **solo el mensaje del usuario y el historial**. Alfred
ve en el historial «Anotado… al marisco», ve «Olvida lo del marisco de Paco» y contesta lo que
toca en esa conversación: «He retirado…».

- La regla general de R8/R13 no basta, porque **nada le dice a Alfred que en este turno no se ha
  hecho nada**. Ese dato lo tiene el código y no se le pasa.
- El fallo es general, no solo de la memoria. Con historial, «apunta leche» o «borra la cita»
  pueden acabar igual.
- El hueco es mío: D26 y D43 lo dejaron todo en el prompt.

Son dos problemas distintos:

1. **Alfred afirma algo falso.** Es grave y se cierra en código: **D44** (R15).
2. **El planner no llama a la tool** (1 de 4 con la regla C). Con D44 deja de ser una mentira y
   pasa a ser un fallo honrado («no lo he hecho, ¿lo intento?»). Lo de fondo es que el historial de
   D21 enseña respuestas sin acciones. Ha saltado el indicador de falsación de D43 y queda como
   pregunta abierta para la fase 3 (marcar en el historial qué herramientas usó cada turno), porque
   cambia `conversations`.

**Decisión 1 del informe: no a la guarda por palabras clave** con `tool_choice` forzado.
- «Borra», «apunta que» y «recuerda que» también son de listas, notas y calendario (D39). Forzar
  `mark_as_memorable` ahí sería un error nuevo.
- Y no cortaría la mentira en los demás casos.

### 2.2 #28: se inventa la hora y crea un evento (arquitecto)

«Recuérdame acostarme pronto» acabó en `calendar_add_event` a las 23:00. En producción, eso es un
evento real en tu Google Calendar con una hora que no dijiste. La lección de R5 sirve aquí: nombrar
qué hacer funciona mejor que prohibir.

R16 cambia la descripción de `calendar_add_event` y amplía el golden #28, que es normativo y mío.

### 2.3 E9 y la regla C — decisión 2: (a)

Lo de E9 se queda como intermitente conocido, y no se gasta en él.
- El daño es pequeño: un mensaje de ropa llega a `salud` y no se guarda nada en ningún sitio.
- La regla C es la que hace que «olvida» funcione con historial.
- Se revisa junto con la pregunta del historial (§2.1) en la fase 3.

### 2.4 Desviaciones

| # | Valoración |
|---|---|
| 1 `indexar_catalogo.py` | **Aprobado, y bien cazado.** Era un hueco de mi plan: sin el catálogo indexado, D35 no funciona en producción |
| 2 mapa por palabras | Aprobado. El `--dry-run` del paso 4 es **el** control, y así lo destaco para Josem (§4) |
| 3 guarda `--produccion`; la nota sin vector | Aprobado. R9 la cubre por el valor |
| 4 a 6 | Aprobados |

## 3. Gasto

**≈ 8,61 $.** Los 2,15 $ de H4 están dentro del «sube otros 3 euros» de Josem.

Para R15 y R16 hace falta **≈ 0,6 $**: E5 ×3, #66 ×2, #28 ×3 y un `-k` de los goldens de memoria
y calendario. **Pido a Josem 1 $ más**, con lo que la fase llegaría a unos 9,6 $ como máximo.

## 4. Para Josem (antes de desplegar)

1. **El «sí» a 1 $**, en la ventana del programador.
2. **En el despliegue, el paso 4 (`migrar_sprint3.py --dry-run`) es el control:** tiene que
   enseñar exactamente tres hechos (alergia al ácido acetilsalicílico, camisetas UV y presión de
   2,30) y nada «sin mapa» que deba migrarse. Si no es así, para.
3. El paso 5 (`indexar_catalogo`) es nuevo y gasta menos de 0,001 $ de OpenAI.

## Para el programador

Responde a: d53c0be (H4-informe)

H4 aprobado con retoques. En este orden, en commits propios:

1. **R15 (D44): un turno sin herramientas, Alfred lo sabe.**
   - En `_synthesize`, cuando `tool_results` está vacío, el prompt de síntesis añade después del
     mensaje del usuario una línea fija:
     > [En este turno no se ha ejecutado ninguna herramienta: no has guardado, cambiado, borrado,
     > apuntado ni creado nada. Si el usuario lo pidió, dile en llano que no lo has hecho y ofrécete
     > a intentarlo.]
   - Constante `_TURNO_SIN_HERRAMIENTAS`.
   - Cuando un turno sale por `had_error` (tool que falla), ya lo cubre el resultado parcial. No lo
     toques.
   - Pruebas sin API:
     - `test_sintesis_sin_herramientas_lleva_aviso`;
     - `test_sintesis_con_herramientas_no_lleva_aviso`.
2. **R16: no inventar la hora.**
   - En la descripción de `calendar_add_event`: «Si el usuario no da día **y** hora, no te los
     inventes: pregunta con `request_clarification`. Un recordatorio sin hora ("recuérdame
     acostarme pronto") no es un evento.»
   - Golden #28 (normativo, cambio mío; cítalo): `any_of` con `[]`, `[notes_create]` y
     `[request_clarification]`.
3. **[API]**, solo con el «sí» de Josem a 1 $ y mirando antes el buzón:
   - E5 ×3. El criterio: en ningún caso Alfred afirma haber retirado algo que sigue vigente en la
     BD. El escenario pasa si se retira, o si Alfred dice que no lo hizo.
   - #66 ×2 y #28 ×3.
   - `-k` de los goldens de calendario (#7, #8, #9, #40, #50) y de #56–#66, con ids exactos.
4. **Para** con un anexo en `H4-informe.md`. Después del anexo va el despliegue de Josem; no
   despliegues, no fusiones y no reinicies nada.

## 5. Revisión del anexo (2026-11-15)

Responde a: 71dd33b (H4-informe, anexo). La revisé contra `fb0cd6f`.

**Veredicto: H4 aprobado. La fase 2 queda lista para que Josem la despliegue.**

### 5.1 Lo que comprobé

- **Pruebas sin API:** **683 en verde**, lo mismo que el anexo.
- **R15:** `_TURNO_SIN_HERRAMIENTAS` es literalmente la línea de la revisión. Entra solo en la rama
  sin resultados de `_synthesize`, después del mensaje del usuario.
- **Gasto:** 0,78 $, dentro del «sí» a 1 $. Acumulado de la fase, **≈ 9,39 $**.

### 5.2 Decisiones del anexo

| # | Decisión |
|---|---|
| 1 | De acuerdo: no queda nada que bloquee el despliegue |
| 2 | **No se toca ahora.** «No he podido apuntarlo» es honesto, aunque no diga por qué. Que Alfred sepa el motivo («falta la hora») necesita que el planner lo diga, y eso va con la pregunta del historial de la fase 3. Queda anotado allí |
| 3 | **No se fuerza con la API.** Las pruebas sin API demuestran que el aviso llega a Alfred, y #28 ya demuestra con el modelo real que, cuando le llega, Alfred no se inventa nada. El resto se mira con el uso real. Indicador en D44: si Josem ve que Sebastian afirma una acción que no ha hecho, se revisa |

## Para el programador

Responde a: 71dd33b (H4-informe, anexo)

H4 aprobado, y con él la fase 2 desde el lado del código. **No hay nada más que hacer** hasta que
Josem despliegue.
- Si en el despliegue falla algo, Josem te lo traerá. Ese arreglo va como anexo a `H4-informe.md`.
- Deja `tomorrow.md` con el estado «esperando el despliegue de Josem».
