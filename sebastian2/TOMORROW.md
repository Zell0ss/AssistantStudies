# tomorrow.md — Sebastian 2.0 (programador)

**Fase 4 (vigilancias), H1 en curso.** Trabajo y buzón en `/data/AssistantStudies-fase4` (rama `fase-4`, `docs/fase4/`); `/data/AssistantStudies` es producción: queda en `main`, limpio, y no se edita nada ahí. Plan: `docs/fase4/PLAN.md` (`0e2c39d`, `plan: arquitecto`).

**Punto de parada:** código y pruebas normativas 1–26 hechos y commiteados (`git log fase-4`); suite completa 1051 pruebas, sin API ni red. Falta, **con el «sí» de Josem en mi ventana**:
1. **[RED]** `python -m scripts.vigilancias.humo_wallapop /data/library/mi-wiki/docs/Obsidian/30-projects/sebastian/vigilancias/mac-mini.yaml` (8 peticiones reales, sin LLM, sin BD).
2. **[API]** `python -m scripts.vigilancias.golden_juez <ese yaml>` (3 pasadas con Haiku 4.5 y 3 con Haiku 5.5; tope 0,30 $). Guardar la salida con redirección a un fichero del scratchpad.
3. Escribir `docs/fase4/H1-informe.md` (Hecho · Gasto · Desviaciones · Decisiones que necesito), con commit, y avisar al arquitecto (`sebastian2-94`, automensaje activo). Parar.

**Gotchas:**
- Gasto de la fase 4: tope 3 $ (aprobado por Josem en la ventana del arquitecto); cada paso [API] se confirma además en mi ventana. Gasto hasta ahora: 0 $.
- `config.yaml` y `.venv` del worktree son copias propias (la BD es `sebastian_test`). Migración 014 aplicada a `sebastian_test` con un script del scratchpad; **no** a producción (el despliegue es de Josem: `ff-only`, 014 a `sebastian_db`, cargar el YAML con `SEBASTIAN_DB_NAME=sebastian_db`, reinicio).
- Editar ficheros con Edit/Write, no con python en Bash (memoria de Josem). `git commit` siempre por rutas.
- Logs de vigilancias: nunca consultas, reglas, títulos ni descripciones (D42); las excepciones, solo su clase. Las pruebas parchean `modules.vigilancias.ronda.logger` y `.juez.logger`.
- `reserved` y `shipping` de Wallapop: el parser acepta booleano u objeto con bandera (`flag`, `item_is_shippable`/`user_allows_shipping`); es una suposición hasta que el [RED] enseñe la forma real.
- PyMySQL devuelve TIME como `timedelta` (`repositorio._hora` lo normaliza); las columnas JSON de MariaDB vuelven como texto. El planificador usa conexión propia del pool, no el singleton.
- Heredado: `-k "golden_1"` casa también `golden_10`; un fallo de tool en goldens vuelca miles de líneas.
