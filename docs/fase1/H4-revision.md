# H4 (fase 1) — Revisión del arquitecto

Responde a: 9ebd519 (H4-informe)

**Veredicto: aprobado.** Listo para que Josem haga el merge y reinicie.

## 1. Comprobado contra el código

- **T4.1 (`4b5a858`, `_planner_system`):** la regla de capacidades queda limitada a «lo que
  Sebastian sabe HACER». Una regla nueva manda a `search_memory` las preguntas sobre el usuario.
  #23 sigue en `none` y #53–#55 van a `search_memory`. Correcto.
- **T4.2 (`_ALFRED_SYSTEM`):** las tres ideas de D26 están, y además la razón («pudiste
  equivocarte, y repetirlo lo convertiría en un hecho»). Eso ayuda al modelo a generalizar. Las 9
  respuestas del test de síntesis, leídas una a una, no inventan nada, y el caso H3 ignora la
  ficha inventada del historial. Que suenen todas parecidas es un precio aceptable.
- **D27 (`fa07cbc`):**
  - `aislamiento.neutralizar_servicios_externos()` fuerza Tristras al puerto 9 con un token
    falso, y YouTube (workdir y `Clippings/`) a un directorio temporal.
  - `config_de_goldens` la aplica y el runner usa esa config.
  - `test_el_harness_usa_la_neutralizacion` cierra el hueco de «test que pasa sin proteger
    nada». Bien visto.
  - La clave `youtube_clippings_path` es opcional, y sin ella el comportamiento es el de siempre.
  - **Orden:** `fa07cbc` va antes de la pasada [API] de las 17:43Z.
- **Red en los tests unitarios:** comprobado con un plugin que bloquea los `connect()`. Es más de
  lo que pedía el encargo, y es la prueba buena.
- **LogCentral de Tristras:** 0 líneas en la ventana de la pasada. Sirve como prueba, porque
  Tristras loguea cada ingesta.
- **Suite:** lanzada por mí: `409 passed, 58 deselected`. Pasada final: 55/55
  (`docs/fase1/goldens/2026-10-14-final-h4.txt`).

## 2. Hallazgos

### 2.1 El presupuesto del encargo estaba mal — arquitecto

El encargo estimaba 0,3–0,6 $ por pasada completa. Desde H2 (0,94 $ con 52 goldens) se sabía que
una pasada completa ronda el **1 $**, porque el planner manda todas las tools en cada iteración.
El exceso de 0,06 $ viene de ahí, no de la ejecución. **Se acepta:** Josem dio el «sí» sabiendo
que serían unos 1,0 $.

**Regla para los planes siguientes:** presupuestar **1,1 $ por pasada completa** de goldens
(≈ 0,02 $ por golden), y pasar solo los goldens nuevos con `-k` cuando baste.

### 2.2 «D26» dentro del texto de los prompts — hueco del encargo (arquitecto), sin cambio

El encargo pedía que los prompts «contengan la referencia D26», y la frase se podía leer como
«en el texto». Ahora el modelo ve «(D26)». No ha salido en ninguna respuesta, y sirve de ancla
para el test unitario. **Se queda así.** Si algún día aparece en una respuesta a Josem, se pasa a
comentario y el test lee el código fuente.

## 3. Estado de D26 y D27

- **D26 sigue `tentativa`** hasta que el uso real confirme su indicador de falsación: que no
  vuelva a afirmar nada del usuario que no esté en la memoria ni lo haya dicho él.
- **D27, `vigente`.**

## Para el programador

Responde a: 9ebd519 (H4-informe)

H4 aprobado. Nada más que hacer hasta que Josem despliegue y pruebe. No quites el worktree. Si la
prueba por Telegram falla, va en un anexo del informe de H4.
