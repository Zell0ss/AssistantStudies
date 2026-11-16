# H7 — revisión (fase 3, parche)

> Responde a: 3a1e547 (H7-informe). 2026-11-16, arquitecto. La revisé contra el código en `4d20165`.

**Veredicto: aprobado. Josem puede desplegarlo.**

## 1. Lo que comprobé

- **Pruebas sin API:** `pytest -m "not golden"` da **900 en verde**.
- **R17:**
  - La nota solo se toma cuando `tool_results_summary` está vacío, en los dos bucles.
  - Va después de `_TURNO_SIN_HERRAMIENTAS`, con un tope de 600 caracteres.
  - El log solo guarda `chars` (D42).
  - No cambiar la línea `Turn end` está bien.
- **R18:** tu matiz («si ya es de madrugada y esa hora aún no ha llegado, es la de hoy») es correcto, y lo acepto.
- **R19:**
  - Se comprueba antes del INSERT, así que sigue siendo «todos o ninguno».
  - R13 va primero.
  - Sin hora, solo cuenta `fecha_fin`, así que un rango que sigue vivo pasa.
  - Quitar la línea sobrante de H4 está bien.
  - Un efecto a sabiendas: si alguien dicta una preparación cuando uno de los pasos ya ha pasado, el lote entero vuelve `invalid`, y el planner tendrá que quitar ese paso. Lo prefiero a crear un aviso muerto.
- **Arnés:** `ahora:` por golden y `crea_con_fecha_o_pregunta` están bien. Corregir el criterio en cuanto viste el PASS falso es justo lo que pedía.

## 2. Decisiones que pedías

| # | Decisión |
|---|---|
| 1 | **#80 (1 de 3, el planner «confirma» en texto): opción (a), riesgo aceptado.** Alfred no miente y ofrece reintentar. Es el patrón de D43 (imitar el «Anotado» del historial) en los compromisos. El arreglo que funcionó en D43 era una regla al final del prompt; extenderla a compromisos va a la fase 4, con #80 de golden. El indicador está en el log: si `planner_nota` sale más de una vez por semana con «no he podido», se adelanta |
| 2 | **#73 (nota con un resultado): riesgo aceptado hasta la fase 4**, con la regla de uso de Josem. Va a la fila de la fase 4 junto a las frases de D56. Una guardia en código no: el límite entre «resultado» y «dato para la cita» (D56) no se distingue con un filtro |
| 3 | El despliegue se hace con los pasos del informe y lo ejecuta Josem. En la prueba por Telegram vale la frase de «esta noche a la una»: crea un compromiso suelto, no toca la cita 4946, y se borra después |

E10, turno 5 («busca y se para») ya estaba en la fila de la fase 4. Nada nuevo.

## 3. Gasto

**0,51 $.** La fase queda en ≈ 10,53 $ de 11 $. No hay más [API] en la fase 3.

## Para el programador

Responde a: 3a1e547 (H7-informe)

H7 aprobado. No queda nada más: para hasta que te escriba. La fase se cierra el 17/12, cuando compruebe el aviso de la 01:00.
