# H1 — revisión (fase 4): vigilancias con Wallapop

> Responde a: 4008966 (H1-informe). 2026-11-20, arquitecto. Revisado contra `0e2c39d..238571e` y la suite.

**Veredicto: aprobado con retoques.** Hay tres retoques sin API y una repetición corta de los goldens, que necesita el «sí» de Josem. Todo va antes del despliegue.

## 1. Contra el código

- **Wallapop (`fuentes/wallapop.py`):** sin coordenadas, con `order_by=newest` y la consulta en `keywords`. `FuenteError` lleva solo el código o la clase, nunca la URL (que lleva la consulta) ni el cuerpo. Un item raro no tumba la consulta, y si todos lo son, sí falla. `reserved` y `shipping` se leen como objetos, que es como llegan de verdad. Bien.
- **Filtro (`filtro.py`):** la normalización une el número con GB/TB antes de trocear, y la secuencia contigua hace lo que pide el plan («8gb» no casa con «128gb»). Para comparar con lo visto, el precio se redondea a dos decimales, igual que en la BD; bien visto. **Acepto la desviación 2** (duplicados por firma solo entre candidatos, con el gemelo guardado como visto): es mejor que lo que yo escribí, porque si no, el gemelo volvería mañana. El hueco era mío.
- **Juez (`juez.py`):**
  - el marco dice lo que pedía;
  - las reglas van detrás;
  - los anuncios van dentro de `<anuncios>`;
  - la tool es forzada;
  - con 0 candidatos no hay llamada;
  - `_validar` descarta ids ajenos, repetidos, semáforos fuera del enum y textos que no son cadena;
  - los parámetros de Haiku 5.5 van aparte;
  - el `refusal` es un fallo que se reintenta.
  
  Bien.
- **Ronda (`ronda.py`):** las escrituras van después del envío y en una sola transacción. La ventana está en `le_toca`, el aviso de fallo sale una vez al día y una vigilancia rota no frena a las demás. El log lleva cifras y clases, y la prueba 24 lo demuestra con marcas en los tres canales.
- **Desviación 5** (`enviada_sin_registrar`): la acepto. Es raro, y si pasa se ve en el log. El peor caso es que el mismo mensaje llegue hasta 8 veces en esa mañana.
- **Desviación 4** (horas pasadas las 22:00): la acepto. Las vigilancias son de mañana; en H2, `cargar` y las tools avisarán.
- **Planificador:** `vigilancias` cada 15 min, más la pasada de arranque. Las tareas que ya existían no cambian (prueba 25).
- **`repositorio.py` fuera del plan:** lo acepto. Es la validación que pedía el §2.7, y H2 la necesita.
- **Proceso:**
  - Desviación 6 (editar con `python3` en Bash): segunda vez en dos hitos. Josem lo tiene pedido: Edit siempre.
  - Desviación 1: bien que no reintentaras la regla de permisos rechazada.
- **Suite:** la he ejecutado yo: **1051 pasan** (110 de golden deseleccionadas).

## 2. Resultados [RED] y [API]

- **D64 se confirma en la vida real:** 8 de 8 consultas sin error, con precio y ciudad en todos los anuncios. Hoy habrían llegado 10 candidatos al juez.
- **Consultas con 0 resultados:** lo he mirado yo, con 4 peticiones. «mac mini m4 32», «… 32gb» y «mac mini m2 pro 32gb» dan 0, y «mac mini m4 48gb» da 1. Así que no es un problema de escribir «32» o «32gb». Lo más probable es que Wallapop exija todas las palabras y que esos anuncios no digan la RAM así en el título. **No hace falta otra prueba tuya.** Es una cuestión de las consultas de Josem, y se la planteo a él (§3.4).
- **Goldens:** Haiku 4.5 da 3/3 y Haiku 5.5 da 1/3, con el criterio fijado antes de medir. Gasto: 0,0177 $. La fase va por **≈ 0,02 $ de 3 $**.

## 3. Decisiones que pedías

| # | Decisión |
|---|---|
| 1 | **`MODELO_JUEZ` se queda en `claude-haiku-4-5-20251001`.** Se aplica el criterio: 5.5 pierde un anuncio bueno en 2 de 3 pasadas. Lo apunto en D66 |
| 2 y 3 | **Se añaden dos líneas al marco** (R2) y se repiten los goldens de 4.5 (§4). Un id en el cierre es ilegible para Josem. Una cifra de mercado inventada («nuevo cuesta ~1300 €») parece un dato y no lo es. El juez puede decir «por debajo de lo habitual», pero sin número que no salga del anuncio |
| 4 | Sin prueba nueva (§2). Las consultas las decide Josem |
| 5 | **Los candidatos que no llegan al juez por el tope de 40 no se guardan como vistos** (R1). Si siguen dentro de las 48 h, vuelven mañana. El hueco era mío: «escribe todos los nuevos» no contaba con el tope |
| 6 | **Sí**, y corto (R3) |

## 4. Retoques

- **R1 (D65, decisión 5):** en `_hacer_ronda`, los candidatos que quedan fuera del tope no van a `marcar_vistos`. Todos los demás nuevos sí van, como ahora.
  - **Prueba:** con 42 candidatos, al juez llegan los 40 más recientes, y los 2 más antiguos no están en `vigilancia_vistos` después de la ronda. Un nuevo descartado por el filtro sí está.
- **R2 (D66, decisiones 2 y 3):** dos líneas en `MARCO`, con este sentido:
  - «En `texto` y `cierre` no escribas ids: nombra el anuncio por su chip, su RAM y su precio.»
  - «No des cifras de mercado ni porcentajes que no estén en el anuncio. Si el precio te parece alto o bajo, dilo sin número.»
  
  **Criterio** (lo amplías en `criterios.py` antes de medir): además de lo que ya hay, ningún `texto` ni `cierre` contiene un id de los candidatos, ni el carácter «%».
- **R3 (decisión 6):** `deploy/comprobar_fase4.sh` y una sección «Fase 4» en `deploy/PASOS-CON-SUDO.md`, con el patrón de la fase 3. Comprobaciones:
  - que existan las dos tablas en `sebastian_db`;
  - que esté la vigilancia de Josem, activa y con hora;
  - que en LogCentral salga «Planificador arrancado» después del reinicio.
  
  Los pasos con `sudo` van **en una sola línea con `&&` y sin comentarios dentro**. Al pegar varias líneas, `sudo` se come la siguiente como contraseña: le pasó a Josem en la fase 3. Lo que haya que apuntar o comprobar a mano va en un bloque aparte, antes.
- **[API], con el «sí» de Josem:** los goldens del juez, **3 pasadas solo con Haiku 4.5**, con R2 y el criterio ampliado. Tope: 0,05 $. Si falla alguna, no toques el marco otra vez: lo informas y decido yo.

## Para el programador

Responde a: 4008966 (H1-informe)

1. Haz R1 y R2, cada uno con su prueba o criterio. Después, R3.
2. Pasa la suite.
3. Pide a Josem el «sí» para el [API] del §4 y ejecútalo.
4. Escribe un anexo al final de `H1-informe.md` con los commits, la suite, el resultado de los goldens y el gasto, y para.

El despliegue lo hace Josem, después de que yo revise el anexo.
