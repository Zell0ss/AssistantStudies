# H2 (fase 1) — Revisión del arquitecto

Responde a: fa2874e (H2-informe)

**Veredicto: aprobado con retoques.** Los dos retoques son de rastro y de pruebas, sin API. H3
puede empezar en cuanto estén.

## 1. Comprobado contra el código (`6626f7a`, `bcbbcb1`, `10d3f57`)

- **`db/conversation_repo.py`:** se ajusta al contrato del PLAN §3. El corte y el `created_at`
  usan el mismo reloj de Python (desviación 1, aceptada). `limpiar` solo borra por fecha.
- **Orquestador:**
  - El historial va delante del mensaje en el planner y en la síntesis.
  - `_resume_plan` no lo lleva.
  - `handle()` guarda solo cuando no hay excepción, así que las respuestas de error de API no
    entran.
  - Al log solo va el número de intercambios, y en los `warning` el tipo de excepción
    (desviación 3, aceptada y bien pensada).
- **Harness:**
  - La fixture `_historial_limpio` borra `conversations` del usuario de golden antes de cada
    golden.
  - `sembrar_historia` respeta el orden.
  - #50–#52 se escribieron antes del código, y la línea base muestra lo esperado: #50 y #51
    fallan sin historial y #52 pasa.
- **R1:** la tabla de uso sale de `_track_usage`, con su test sin red. Hecho.
- **Suite:** lanzada por mí en el worktree: `399 passed, 52 deselected`. Pasada final de goldens:
  52/52, según la salida guardada.

## 2. Hallazgos

### 2.1 La salida de la pasada final no tiene commit — programador

`docs/fase1/goldens/2026-10-13-final-h2.txt` está en la copia de trabajo pero **sin commit**,
aunque el informe la cita como prueba del 52/52 y del gasto. Es justo lo que pedía R2.

**Pido (R4):** commit de ese fichero, solo de ese (`-- <ruta>`).

### 2.2 La desviación 2 no tiene prueba — programador

Se descartan los intercambios con un lado vacío y no se guarda texto vacío. Es una buena
decisión, porque la API rechaza contenido vacío y un turno roto así no debe envenenar los
siguientes, pero no hay ningún test que la sujete.

**Pido (R5)**, dos tests de regresión en `tests/test_orchestrator.py`, sin red:
- `test_historial_descarta_intercambio_con_lado_vacio`: con un intercambio `("hola", "")` y otro
  normal, el planner recibe solo el normal.
- `test_no_guarda_respuesta_vacia`: si la síntesis devuelve `""`, la tabla queda vacía.

### 2.3 Desviación 4 (guardar la reanudación) — respuesta a «Decisiones que necesito» 2

**Se queda así.** El turno anterior ya guardó `(mensaje original, pregunta de Alfred)`, así que
la reanudación guarda `(respuesta, resultado)` y el historial queda como una conversación
coherente:

| | |
|---|---|
| user | ¿qué tiempo hace? |
| assistant | ¿En qué ciudad, señor? |
| user | Madrid |
| assistant | En Madrid… |

Es lo que pide D24 (las aclaraciones entran). No hace falta ninguna decisión nueva.

### 2.4 Limitación aceptada, sin cambio (arquitecto)

Las horas son locales y sin zona. En el cambio de hora (25-oct) la ventana de 2 h puede quedar
desplazada una hora durante esa noche. No merece código; queda anotado aquí.

## 3. Gasto — respuesta a «Decisiones que necesito» 1

- **No hace falta otra pasada completa.** H2 está en 52/52, R4 y R5 no tocan prompts ni tools, y
  H3 no lleva goldens.
- **No se pide autorización adicional.**
- La fase cierra con unos **1,9 $** de 2 $: 0,98 $ medidos y unos 0,9 $ de la pasada de H1,
  estimados a posteriori con la medición de H2. Gracias por corregir la estimación de H1.

## Para el programador

Responde a: fa2874e (H2-informe)

H2 aprobado. En este orden:

1. **R4:** commit de `docs/fase1/goldens/2026-10-13-final-h2.txt` (§2.1).
2. **R5:** los dos tests de regresión de §2.2.
3. **H3** según el PLAN §4, con **R3** de la H1-revision §2.3:
   - en el paso 4 de `PASOS-CON-SUDO.md`, qué significa el `KeyError` al arrancar;
   - poner al día `docs/COMANDOS.md`, `docs/DEPLOYMENT_CHECKLIST.md` y `db/verify_database.sh`.
   - `deploy/comprobar_fase1.sh`, de solo lectura.
   - **Nada de sudo ni de tocar producción**: lo ejecuta Josem.
4. **Para** en H3 con `docs/fase1/H3-informe.md`, listo para que Josem despliegue.
