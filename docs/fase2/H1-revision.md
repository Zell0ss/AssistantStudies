# H1 (fase 2) — Revisión del arquitecto

Responde a: be734d9 (H1-informe)

**Veredicto: aprobado con retoques.** Los retoques son la corrección de una prueba del plan y una
segunda calibración barata, con la regla para fijar los umbrales escrita aquí, para no gastar otra
vuelta. Después de los retoques, H2 sin parar.

## 1. Comprobado contra el código (`2c42e7e`, `d15c337`)

- **010 y 011:**
  - sin `USE`;
  - `ENGINE` y `charset` como las demás;
  - `alias_norm` en `utf8mb4_bin` (desviación 2). Es una buena decisión: sin ella, `ano` y `año`
    chocarían en el `UNIQUE`. Aceptada.
- **`normalizar.py`:** conserva solo la tilde de la `n` después de NFD, quita un único artículo o
  posesivo inicial y deja la palabra si es la única. Correcto.
- **`crear_colecciones.py`:** se niega antes de abrir el cliente. Correcto.
- **`catalogo.py`:** embebe descripciones y filtra por `user_id` en las entidades. Correcto.
- **Desviaciones 3–6:** aceptadas. `ajustes.py` es un buen sitio único para la config.
- **Suite:** lanzada por mí: `445 passed, 1 failed`, y el fallo es el de §2.1.

## 2. Decisiones

### 2.1 «Cumpleaños»: la prueba estaba mal — hueco del plan (arquitecto)

El §2.4 dice que la `ñ` se queda, y el caso «Cumpleaños» → `cumpleanos` lo contradice. **Manda la
regla:**
- la prueba pasa a «Cumpleaños» → `cumpleaños`, y la cambio yo como autor de las normativas;
- el atributo canónico sigue siendo `cumpleanos` (snake_case en ASCII), con el alias `cumpleaños`
  que ya añadiste en 011.

**R1:** aplica este cambio de prueba en un commit propio que cite esta sección.

### 2.2 Umbrales: el orden es bueno y la escala no

Las 15 positivas tienen la candidata correcta en primer lugar. Pero las puntuaciones de
`text-embedding-3-small` contra una sola descripción son bajas (mediana 0,58), y se solapan con
las negativas cercanas en 0,43–0,45. Los provisionales (0,75 y 0,85) dejaban la rama semántica
muerta. Era un hueco mío: los puse a ojo.

**Recuerda** que la escalera empieza por alias exacto, y que el extractor recibe el catálogo y
reutiliza los nombres que ya existen. La rama semántica es el respaldo, no el camino principal.

**R2 · Segunda calibración** (menos de 0,01 $), con dos cambios en el banco:

1. **Más negativas:** añade 10 negativas cercanas más, hasta 25. Que haya del tipo «presión
   arterial» frente a «presión de neumáticos», «cumpleaños de Paco» frente a «cumpleaños» del
   usuario (es la misma entidad o no, no el mismo atributo), «mi coche nuevo» frente a «coche»,
   etcétera.
2. **Tres representaciones del catálogo,** con el mismo banco:
   - **(a)** solo la descripción (como ahora);
   - **(b)** `nombre: descripción`;
   - **(c)** la descripción más 3 frases de ejemplo por atributo y entidad, cada una como punto
     propio con el mismo `id` en el payload. La puntuación de una entrada es la mejor de sus
     puntos.

**Regla para fijar los umbrales, sin volver a mí:**
- elige la representación con más positivas por encima de `max(negativas) + 0,03`, y en caso de
  empate la más sencilla;
- con ella:
  - `reutilizar` = `max(negativas) + 0,03`, redondeado hacia arriba a 0,01, con margen 0,03;
  - `sustituir` = `reutilizar + 0,10`, con margen 0,05.
- Esos valores van a `ajustes.py` como valores por defecto y a `config.example.yaml`, y se quedan
  en `tentativa` (D35).

Si con ninguna representación hay al menos 8 de 15 positivas por encima de `reutilizar`, **para y
cuéntamelo**: la rama semántica no sirve tal cual y hay que hablarlo.

Con la (c), las frases de ejemplo de los atributos que cree el extractor en H2 salen del propio
extractor: añade `ejemplos: [str]` (como mucho 3) al esquema de `registrar_hechos` para los
atributos nuevos. Inclúyelo ya en el contrato de H2.

### 2.3 Recalibrar con el uso: sí

Los umbrales se quedan en `tentativa` y se recalibran con `mem_decisiones` tras dos semanas de uso
real (plan §5). El indicador de falsación de D35 ya lo dice.

### 2.4 OpenAI medido

El presupuesto de la fase incluye OpenAI. **R3:** `OpenAIEmbedder` acumula `usage.total_tokens`
(como `_track_usage`). El harness de goldens y `calibrar.py` imprimen el coste de OpenAI junto al de
Anthropic, a 0,02 $ por millón de tokens para `text-embedding-3-small`, como constante con su
referencia. Desde H2, el coste de OpenAI va medido en los informes.

## Para el programador

Responde a: be734d9 (H1-informe)

H1 aprobado con retoques. En este orden:

1. **R1:** el caso «Cumpleaños» → `cumpleaños` (§2.1).
2. **R3:** la medición de tokens de OpenAI (§2.4).
3. **R2:** la segunda calibración [API, OpenAI] y los umbrales con la regla del §2.2. La tabla de las
   tres representaciones y los umbrales elegidos van en un anexo de este informe
   (`## Anexo — calibración 2`).
   - Si salta el «para» del §2.2, te detienes ahí.
   - Si no, **sigue con H2 sin esperarme**, con el contrato del plan más el campo `ejemplos` del
     extractor.
4. **Para** en H2 con `docs/fase2/H2-informe.md`.
