# tomorrow.md — Sebastian 2.0 (programador)

**Fase 4 (vigilancias), H1 en curso.** Trabajo y buzón en `/data/AssistantStudies-fase4` (rama `fase-4`, `docs/fase4/`); `/data/AssistantStudies` es producción: queda en `main`, limpio, y no se edita nada ahí. Plan: `docs/fase4/PLAN.md` (`0e2c39d`, `plan: arquitecto`).

**Punto de parada:** **H1 ENTREGADO** (`docs/fase4/H1-informe.md`, `4008966`, responde a `0e2c39d`): código y pruebas 1–26 (`7dcd8ec`), piezas de [RED]/[API] (`e646495`), 1051 pruebas. [RED] 8/8 sin errores (20 únicos, 10 pasan el filtro; 3 consultas con 0); [API] Haiku 4.5 3/3, Haiku 5.5 1/3, gasto 0,0177 $ (fase 4 ≈0,018 $ de 3 $; autorizó Josem el 2026-11-20, «Si y si!»). **Parado hasta la revisión.** El despliegue (pasos en el informe; ojo, la variable es `SEBASTIAN_DB_NAME`, no `DB_NAME`) es de Josem. Si el arquitecto aprueba un retoque del marco del juez (ids en el `cierre`, cifras inventadas), repetir `golden_juez` pide otro «sí» de Josem (≈0,02 $).

**Gotchas:**
- Gasto de la fase 4: tope 3 $ (aprobado por Josem en la ventana del arquitecto); cada paso [API] se confirma además en mi ventana. Gasto hasta ahora: 0 $.
- `config.yaml` y `.venv` del worktree son copias propias (la BD es `sebastian_test`). Migración 014 aplicada a `sebastian_test` con un script del scratchpad; **no** a producción (el despliegue es de Josem: `ff-only`, 014 a `sebastian_db`, cargar el YAML con `SEBASTIAN_DB_NAME=sebastian_db`, reinicio).
- Editar ficheros con Edit/Write, no con python en Bash (memoria de Josem). `git commit` siempre por rutas.
- Logs de vigilancias: nunca consultas, reglas, títulos ni descripciones (D42); las excepciones, solo su clase. Las pruebas parchean `modules.vigilancias.ronda.logger` y `.juez.logger`.
- `reserved` y `shipping` de Wallapop: el parser acepta booleano u objeto con bandera (`flag`, `item_is_shippable`/`user_allows_shipping`); es una suposición hasta que el [RED] enseñe la forma real.
- PyMySQL devuelve TIME como `timedelta` (`repositorio._hora` lo normaliza); las columnas JSON de MariaDB vuelven como texto. El planificador usa conexión propia del pool, no el singleton.
- Heredado: `-k "golden_1"` casa también `golden_10`; un fallo de tool en goldens vuelca miles de líneas.
