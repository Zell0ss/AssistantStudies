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

## 5. Revisión del anexo (2026-11-20)

> Responde a: 4a31196 (H1-informe, anexo «Retoques de la revisión»). Revisado contra `0eaa6e2..5072f8f`.

**Veredicto: aprobado con un retoque más.** R1 y R3 están bien. R2 queda a medias, por un hueco mío: le pedí al modelo que no escribiera ids en un campo de texto libre, cuando la regla de D66 es que el texto que ve Josem lo arma el código.

- **R1:** `sin_juzgar` deja fuera de `marcar_vistos` solo los candidatos que el tope no deja juzgar. La prueba comprueba también que vuelven al día siguiente. Bien.
- **R2:** las dos líneas del marco están. En `texto` funcionan (3/3 sin ids ni «%»), y en `cierre`, no. El resultado no cambia el veredicto sobre el juez: los buenos, los malos y la inyección salen bien en las 3 pasadas.
- **R3:**
  - el script es de solo lectura;
  - los bloques con `sudo` van en una línea, y una prueba lo exige;
  - la vuelta atrás también va en una línea;
  - hay copia de seguridad antes de migrar.
  
  Bien.
- **Suite:** la he ejecutado yo: **1068 pasan**.
- **Gasto:** 0,0162 $, con el «sí» de Josem registrado. La fase va por **≈ 0,034 $ de 3 $**.

### Decisiones

| # | Decisión |
|---|---|
| 1 | **Variante de tu (a): el juez elige el mejor por id, y el código escribe la frase.** La tool cambia `cierre` por `mejor_id` (cadena opcional). El código lo valida contra los elegidos. Si vale, escribe «Mejor de esta ronda: <título> · <precio>», con los datos del anuncio. Si es nulo o no vale, escribe «Ninguno urgente.». Así se conserva el juicio del modelo (cuál es el mejor) y desaparecen los ids, la lista de excluidos y las cifras del cierre. Es D66 aplicado de verdad: lo apunto en el ADR |
| 2 | **Ni nota ni `updated_at`: la guarda va en el repositorio.** Al guardar (crear o cambiar) una vigilancia cuya ventana de hoy ya se cerró sin ronda, `guardar` pone `aviso_fallo = hoy`. Lo de hoy no se avisa porque la vigilancia no existía en su ventana. Si se carga dentro de la ventana, la ronda sale en la pasada siguiente, y eso le viene bien a Josem para probar. La prueba 21 no cambia, y H2 lo hereda |

### Retoques

- **R4 (D66, decisión 1):**
  - En `TOOL_INFORME`, `cierre` sale y entra `mejor_id` (`string`, opcional).
  - En `MARCO`, la línea del cierre se sustituye por: «si eliges alguno, pon en `mejor_id` el id del que más merece la pena; si ninguno destaca, déjalo vacío». La de los ids en `texto` se queda.
  - `armar_mensaje` escribe el cierre.
  - **Pruebas:**
    - con `mejor_id` válido, el mensaje acaba en «Mejor de esta ronda: <título> · <precio>»;
    - con `mejor_id` nulo, o que no está entre los elegidos, acaba en «Ninguno urgente.»;
    - sin elegidos, sigue saliendo «Nada nuevo que merezca la pena.», sin cierre.
  - **Criterio** (lo ajustas en `criterios.py` antes de medir): la comprobación de ids pasa a mirar solo los `texto`. Además, `mejor_id`, si viene, es uno de los 3 buenos (g01–g03).
- **R5 (decisión 2):** en `repositorio.guardar`, la guarda de `aviso_fallo` descrita arriba. Quita la nota del paso 3 de `PASOS-CON-SUDO.md`.
  - **Pruebas:**
    - con la carga a las 10:00 y `hora` a las 07:30, la pasada de las 10:15 no manda nada, y al día siguiente a las 07:30 sale la ronda;
    - con la carga a las 07:45 y `hora` a las 07:30, la pasada de las 08:00 hace la ronda.
- **[API], con el «sí» de Josem:** goldens del juez, 3 pasadas con Haiku 4.5, con R4 y el criterio ajustado. Tope: 0,03 $. Si falla, lo informas sin tocar el marco.

## Para el programador

Responde a: 4a31196 (H1-informe, anexo)

1. Haz R4 y R5, cada uno con sus pruebas.
2. Pasa la suite.
3. Pide a Josem el «sí» para el [API] y ejecútalo.
4. Escribe un segundo anexo al final de `H1-informe.md`, corto (commits, suite, goldens y gasto), y para.

Si los goldens pasan, H1 queda aprobado sin otra vuelta y Josem despliega con la sección «Fase 4» de `PASOS-CON-SUDO.md`.

## 6. Revisión del segundo anexo (2026-11-20)

> Responde a: 7811bf3 (H1-informe, segundo anexo). Revisado contra `fe291e8..65cfb2d`.

**Veredicto: H1 aprobado.** Listo para que Josem lo despliegue.

- **R4:**
  - `mejor_id` sustituye a `cierre` en la tool;
  - `_validar` solo lo acepta si está entre los elegidos que quedan tras el recorte;
  - `_cierre` escribe la frase con el título y el precio del anuncio.
  
  Del juez ya solo llegan a Josem el semáforo y el `texto` de cada anuncio. Así queda D66.
- **R5:** la guarda está en `guardar`, solo si la vigilancia queda activa, su ventana de hoy está cerrada y no hubo ronda hoy. Fijar el `ahora` en el `_crear` de las pruebas de la ronda es correcto, y las aserciones de la 21 no cambian.
- **Suite:** la he ejecutado yo: **1084 pasan**.
- **Goldens (2/3) y el criterio del «%»:** el hueco es mío. Puse «ni el carácter %» como sustituto de la regla del marco («cifras de mercado que no estén en el anuncio»), y el sustituto es más estricto que la regla. He comprobado que el anuncio g08 dice «batería al 94 %» (`anuncios.yaml:75`). Así que la pasada 2 hizo lo correcto y el criterio la suspendió.
  - **Apruebo tu propuesta:** un «%» solo falla si no aparece en el título o la descripción del anuncio que se cita.
  - Es un cambio de criterio después de medir, que normalmente no acepto (D29). Aquí sí, porque no relaja lo que se quería medir, sino que corrige una medida que no medía eso. Queda dicho aquí.
  - Vuelve a juzgar las 3 salidas guardadas sin API. **Espero 3/3.** Si no da 3/3, me lo dices antes de que Josem despliegue.
- **Gasto:** 0,0153 $, con el «sí» de Josem registrado. H1 en total: 0,049 $. La fase va por **≈ 0,049 $ de 3 $**.

## Para el programador

Responde a: 7811bf3 (H1-informe, segundo anexo)

1. Cambia el criterio del «%» como queda arriba, con una prueba: un «%» del anuncio pasa y uno inventado falla.
2. Vuelve a juzgar las 3 salidas de `f4_api_r4.txt` sin API.
3. Pasa la suite y haz commit.
4. Si da 3/3, una línea al final de `H1-informe.md` con el commit y el resultado, y para. H1 está cerrado: no empieces H2 hasta que te escriba.
