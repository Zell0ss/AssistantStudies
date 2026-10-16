# H1 (fase 2) — Informe: esquema, catálogo y calibración

Responde a: c032b00 (PLAN.md, «Para el programador»)

## Hecho

Commits: `2c42e7e` (migraciones 010/011 y pruebas normativas, rojas), `d15c337` (`core/memoria/`,
`crear_colecciones.py`, `calibrar.py`) y el de este informe (salida de la calibración).
**445 tests en verde y 1 en rojo** (`test_normalizar[Cumpleaños-cumpleanos]`: ver Desviaciones §1).
Sin API, salvo la calibración.

- **Migraciones `010_memoria.sql` y `011_memoria_semillas.sql`**, aplicadas a `sebastian_test` y a
  `sebastian_dev` como `sebastian_user`. A producción no. Cada una, dos veces: 10 atributos y 25 alias,
  sin duplicar. 011 son los 5 atributos activos del plan y los 5 del contrato del vault
  (`fuente='contrato_vault'`, tipo `proyecto`), cada uno con su `descripcion` y sus alias. No siembra
  entidades.
- **`core/memoria/`**:
  - `normalizar.py` (§2.4);
  - `embedder.py` (`Embedder` + `OpenAIEmbedder`);
  - `repositorio.py` (alta y consulta de entidades, atributos y alias; `entidad_usuario` crea el «yo»
    una vez);
  - `catalogo.py` (embebe **descripciones**; `buscar_atributos`, `buscar_entidades` con el `user_id` en el
    filtro de Qdrant, `margen`);
  - `ajustes.py` (lee `config.memoria.umbrales` y `propietario_vault`, con los valores provisionales).
- **`scripts/memoria/crear_colecciones.py`**: crea `<base>_catalogo` y `<base>_notas` (1536, coseno). Se
  niega si la base no acaba en `_test` o `_dev`, salvo `--produccion`, **antes** de abrir ningún cliente.
  Repetirlo no falla.
- **Pruebas normativas del plan:** las 6 de `normalizar`, `test_semillas_idempotentes`,
  `test_entidad_por_usuario`, `test_yo_se_crea_una_vez`, `test_crear_colecciones_rechaza_produccion`,
  `test_embedder_es_intercambiable`. Más las mías: alias por usuario, `n` ≠ `ñ`, descripciones y no alias,
  idempotencia del indexado, la maquinaria de calibrar. Los tests unitarios usan `EmbedderFalso` y un
  Qdrant en memoria (`tests/fakes_memoria.py`).
- **Calibración** (`scripts/memoria/calibrar.py`, `tests/golden/calibracion_catalogo.yaml`, 15
  positivas y 15 negativas): salida completa en `docs/fase2/goldens/2026-10-16-calibracion-catalogo.md`.

### Tabla de calibración

Puntuación de la mejor candidata (coseno de `text-embedding-3-small`) contra las descripciones. Margen
exigido en las dos últimas columnas: 0,05.

| umbral | positivas aceptadas | negativas que pasan | pos. con margen | neg. con margen |
|---|---|---|---|---|
| 0,50 | 11/15 | 0/15 | 11/15 | 0/15 |
| 0,55 | 11/15 | 0/15 | 11/15 | 0/15 |
| 0,60 | 6/15 | 0/15 | 6/15 | 0/15 |
| 0,65 | 4/15 | 0/15 | 4/15 | 0/15 |
| 0,70 | 2/15 | 0/15 | 2/15 | 0/15 |
| 0,75 | 1/15 | 0/15 | 1/15 | 0/15 |
| 0,80 a 0,90 | 0/15 | 0/15 | 0/15 | 0/15 |

**Lo que se ve:**
- **La mejor candidata fue la correcta en las 15 positivas.** El orden es bueno; es la escala lo que no
  coincide con el plan.
- **Positivas:** de 0,331 a 0,782 (mediana ≈ 0,58). **Negativas:** de 0,240 a 0,450.
- **Los umbrales provisionales (0,75 y 0,85) aceptarían 1 de 15** y 0 de 15. La rama semántica casi
  nunca reutilizaría ni sustituiría con ellos.
- **Las 4 positivas por debajo de 0,50** son las más coloquiales: «las ruedas del coche» (0,445), «mi
  cuñado» (0,435), «que le gusta beber» (0,434) y «no puede comer frutos secos» (0,331). Se solapan con las
  negativas más altas: «el número de hijos» (0,450), «la presión arterial» (0,446) y «el seguro del
  coche» (0,413).
- **Hasta 0,45 no hay ninguna negativa por encima** del umbral, pero con 15 negativas es poca prueba.
- El margen casi no separa: las negativas altas tienen margen 0,05 a 0,2, igual que muchas positivas.

## Gasto

- **Anthropic: 0 $. OpenAI: < 0,001 $, estimado, no medido.** Fueron 46 textos cortos (16 descripciones y 30
  expresiones, unos 700 tokens) con `text-embedding-3-small` a 0,02 $ por millón. El script no registra
  uso; si lo quieres medido, se lo añado.
- **Acumulado de la fase 2: ≈ 0,001 $ de 5 $.**

## Desviaciones

1. **Contradicción en el plan §2.4 (una prueba normativa en rojo).** Dice que la `ñ` se queda, y las
   pruebas piden «año» → `año` **y** «Cumpleaños» → `cumpleanos`. No caben las dos sin una regla que
   distinga las palabras. Implementé la regla escrita (la `ñ` se queda, también en «año»), no toqué la
   prueba y añadí a 011 el alias `cumpleaños` para que el atributo `cumpleanos` se resuelva. Propongo
   cambiar el caso a «Cumpleaños» → `cumpleaños`; lo decides tú.
2. **`alias_norm` en `utf8mb4_bin`** (010). La colación por defecto (`unicode_ci`) igualaría `ano` y `año`
   en el `UNIQUE` y en las búsquedas, y el normalizador conserva la `ñ` a propósito. Añadí también
   `ENGINE=InnoDB … utf8mb4` como las otras migraciones. El resto de 010 es el SQL del plan.
3. **Migraciones aplicadas con `pymysql` como `sebastian_user`**, no con `db/setup_db.sh`: ese script usa
   `sudo mysql` y yo no tengo sudo. Las dos BD ya existían y el usuario tiene permisos. `setup_db.sh` las
   aplicará solo, porque recorre `db/migrations/*.sql`.
4. **Calibración con un Qdrant en memoria**, sin escribir en el servidor ni en la BD. Mismo coseno, y no
   deja colecciones sueltas. Las expresiones de ejemplo del plan («las ruedas del coche» →
   `presion_neumaticos`) apuntan a atributos que no son semilla. El YAML trae 6 atributos más
   (`catalogo_extra`: `presion_neumaticos`, `matricula`, `telefono`, `direccion`, `profesion`,
   `fecha_revision`) y se embeben junto a las semillas. El catálogo de la calibración tiene 16 entradas.
5. **Módulo no previsto en §2.6: `ajustes.py`**, para leer `config.memoria` en un solo sitio. Y `EmbedderFalso`,
   `qdrant_en_memoria` y `QdrantQueDejaMarca` en `tests/fakes_memoria.py`.
6. **`config.example.yaml`** lleva la sección `memoria` (comentada). El `config.yaml` de producción no hace
   falta tocarlo: sin ella rigen los valores por defecto.

## Decisiones que necesito

1. **Los umbrales.** Con esta escala, ¿los fijas tú sobre la tabla? Dos observaciones para decidir: los
   provisionales (0,75 y 0,85) dejan la rama semántica casi muerta, y el solape entre las positivas más
   coloquiales y las negativas más altas está en 0,43 a 0,45. Si quieres más resolución, puedo probar
   otras formas de embeber (nombre + descripción, o dos o tres frases de ejemplo por atributo) con otra
   pasada de calibración (< 0,01 $).
2. **El caso «Cumpleaños».** ¿Lo cambias a `cumpleaños`, o prefieres que el normalizador pliegue la `ñ`
   (entonces «año» → `ano` y se cambia la regla)?
3. **Calibración con tu catálogo real.** 15+15 parejas son pocas, y las descripciones de los atributos
   que cree el extractor en H2 serán distintas de las que yo escribí. ¿Te vale que los umbrales queden
   `tentativa` y se recalibren con `mem_decisiones` (como dice el plan §5)?

Paro aquí. No empiezo H2 hasta tu revisión.

## Anexo — calibración 2

Responde a: 16382e2 (H1-revision, «Para el programador»)

**Hecho (R1, R3, R2):** `R1` en `4504834` (prueba «Cumpleaños» → `cumpleaños`, cita §2.1); `R3` en `eaf6bfe`
(`OpenAIEmbedder` y el harness de goldens acumulan `usage.total_tokens`, a 0,02 $ por millón); `R2` en
`b553f57` (código) y en el commit de este anexo (salida y umbrales). 459 tests en verde.

**Cambios en el banco:** 15 positivas y **25 negativas** (10 nuevas: «mi coche nuevo», «el coche de mi
hermano», «la presión del agua en la ducha», «la fecha de entrega del pedido», «la dirección de correo
electrónico», «el número de la cuenta bancaria», «la edad de Paco», «el trabajo de fin de máster», «el
estado del tráfico», «el código postal»). Tres frases de ejemplo por atributo (16 atributos), ninguna
repite una expresión del banco. Salida completa:
`docs/fase2/goldens/2026-10-16-calibracion-catalogo-2.md`.

### Las tres representaciones, con la regla del §2.2

| representación | max(negativas) | corte (+0,03) | `reutilizar` | positivas sobre el corte | positivas ≥ `reutilizar` |
|---|---|---|---|---|---|
| **a** (descripción) | 0,544 | 0,574 | 0,58 | **11/15** | 10/15 |
| b (`nombre: descripción`) | 0,540 | 0,570 | 0,58 | 7/15 | 6/15 |
| c (descripción + 3 ejemplos) | 0,629 | 0,659 | 0,66 | 6/15 | 6/15 |

**Gana la (a), la más sencilla y la que ya había** (11 positivas sobre el corte, frente a 7 y 6). No salta
el «para» del §2.2: hay 10 de 15 positivas por encima de `reutilizar` (el mínimo era 8).

**Umbrales fijados (tentativa, D35):**
- `reutilizar` = **0,58**, margen **0,03** (max negativas 0,544 = «el código postal» frente a `direccion`;
  + 0,03 = 0,574, hacia arriba 0,58);
- `sustituir` = **0,68**, margen **0,05**.

Ya están en `ajustes.py` (valores por defecto, con `test_ajustes_memoria.py`) y en `config.example.yaml`.

**Lo que vi, para tu seguimiento:**
- **Los ejemplos empeoran en vez de mejorar.** La (c) sube las positivas por encima de 0,50 (13/15), pero
  también las negativas (8/25 pasan en 0,50; max 0,629): una frase de ejemplo de otro atributo se parece
  demasiado a una expresión cercana. La (b) pierde, porque el nombre en snake_case aporta poco.
- **Con la (a) no hay negativas por encima de 0,55**, y con 0,58 pasan 10 de 15 positivas. Las 5 que
  quedan fuera son las coloquiales («no puede comer frutos secos», «mi cuñado», «las ruedas del
  coche»…): irán a `nota` y a `mem_decisiones`, y se verán en la recalibración con el uso (§2.3).
- **`ejemplos` en el extractor (H2):** lo incluyo en el contrato como pediste, pero con la (a) no se
  embebe: el catálogo guarda solo la descripción. No añado columna `ejemplos` al esquema.

**Gasto:** Anthropic 0 $. **OpenAI medido: 981 tokens × 0,02 $/millón = 0,00002 $.** El script lo imprime.
Acumulado de la fase 2: **≈ 0,0001 $ de 5 $** (la primera calibración, estimada en < 0,001 $, y esta).

**Desviación:** el `H1-revision §2.2` pedía `max(negativas) + 0,03` «por encima»; implementé «por encima»
como estricto (`>`), y para el corte de 0,574 da el mismo resultado que `>=`.

Sigo con H2 sin esperar, como indica la revisión.
