# H1j — revisión (fase 4, D74)

> Responde a: 0b7d605 (H1j-informe). 2026-11-20, arquitecto. Revisado contra `1ee757c..0b7d605` y la suite.

**Veredicto: no aprobado todavía.** Vamos por tu opción 1, con otra frase.

- **R25:** está en el sitio correcto y la parte de guardar no cambia. Bien.
- **El script de goldens:** usa el planner real y datos inventados. Que G4 y G5 lleven historial (tu desviación 1) me parece bien: es más exigente.
- **Suite:** la he ejecutado yo: **1210 pasan**.
- **Gasto:** 0,0385 $. Quedan 0,0615 $ de los 0,10 autorizados por Josem para este hito. La segunda vuelta cabe ahí: no hace falta otro «sí».

## Lectura de G2

Tu hipótesis encaja con la traza de producción. Una pregunta por un dato concreto, ya contestada en el historial, el planner la trata como conversación y **copia** la respuesta. La frase de R25 nombra el caso («¿cuál es mi…?»), pero no prohíbe copiar.

**No quiero una frase hecha a medida de Telegram:** se ajustaría a los goldens y no generalizaría. La regla tiene que prohibir el gesto, copiar del historial un dato de memoria, y no un ejemplo concreto.

## R25b — la frase

Sustituye la frase de R25 por esta, en el mismo sitio:

> «Si el usuario pregunta qué consta de él, de su gente, de sus cosas o de sus proyectos, sea en general («¿qué sabes de…?») o un dato concreto («¿cuál es mi…?», «¿cuándo es…?», «¿dónde…?»), tu respuesta de este turno tiene que ser una llamada a `search_memory`. Vale también si en el historial ya se preguntó y se contestó: **nunca contestes un dato de memoria copiándolo del historial**, porque lo que se dijo en otro turno no es fuente (D26).»

## Goldens, segunda vuelta (≤ 0,06 $, dentro de lo autorizado)

- **G2**, 2 pasadas.
- **G2b**, 1 pasada, **nueva** para ver si generaliza:
  - pregunta: «¿Cuándo es mi cumpleaños?»;
  - índice: `yo (tú): cumpleanos, telegram_id, nota`;
  - historial: la misma pregunta ya contestada, «Su cumpleaños es el 12 de marzo, señor.».
- **G1, G3 y G4**, 1 pasada cada uno.

En total son 6 llamadas. **Criterio:** 3/3 en G2 y G2b, y G1, G3 y G4 sin regresión. Si G2 sigue fallando, para y dilo. No retoques la frase por tu cuenta.

## Para el programador

Responde a: 0b7d605 (H1j-informe)

1. Haz R25b. Actualiza la prueba de la frase y pasa la suite.
2. Lanza la segunda vuelta de goldens, dentro de 0,06 $.
3. Escribe un anexo corto al final de `H1j-informe.md`, con:
   - el resultado de cada pasada;
   - el gasto;
   - las órdenes de despliegue si aprueba.
4. Para.
