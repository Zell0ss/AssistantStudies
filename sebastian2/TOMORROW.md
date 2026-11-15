# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-11-15):** fase 2, H3: retoques de `H3-revision.md` (`36c3f90`) hechos y entregados como anexo de `docs/fase2/H3-informe.md`. Es el turno del
arquitecto. 655 pruebas sin API en verde. [API]: #66 3/3, E5 3/3, R10 10/10, escenarios 8/9 (E9: el planner mandó el primer turno a `salud`). Hecho: R8–R12
(`809f697`, `48cc4f3`, `e200440`, `fe443e6`, `2ec6667`).

**Siguiente paso:** el que diga el arquitecto. No empezar H4 (retirada del Sprint 3 y despliegue) sin su revisión. Lo más probable: confirmar la regla del planner
(desviación de R8), E9, la frase con la que Alfred cuenta que no hizo algo, y los tres logs de error que aún guardan el mensaje.

**Gotchas:**
- **Gasto de la fase ≈ 6,46 $.** Autorizado por Josem: tope original 5 $ y, el 2026-11-15, «Si, hasta 2€» (gastado 1,95 $ de eso). La revisión pedía subir a 8 $, pero Josem no lo dijo en mi
  ventana: **nada [API] sin un «sí» nuevo de Josem**. H4 (pasada completa de 66 goldens y escenarios) cuesta ≈ 2,3 $ y no cabe. Antes de cada paso [API]: `git log` del buzón.
- La regla del planner (D43) vive en `_REGLA_ACCIONES_CON_HISTORIAL` (`core/orchestrator.py`), **al final** del prompt: con la regla en medio o al principio, el planner contestaba en texto «He retirado…».
- R9 compara por palabras completas y comparte con R3 el límite de un cierre indirecto por turno (`turno["cierres_indirectos"]`). R10: `Extractor.marcadores_descartados`.
- `-k "golden_1 or …"` casa también `golden_10`…`golden_19` (subcadena): usar `golden_01`… no existe; mejor ids con más dígitos o `-k "golden_66"`.
- Dos venv: `sebastian2/.venv` (3.12 + anthropic 1.14) es el de este worktree; el de producción sin tocar. `pytest` desde `sebastian2/`: `.venv/bin/python -m pytest`; goldens: `-m golden` con `-k`.
- Un fallo de tool en goldens vuelca ~8.000 líneas: filtrar con `grep -v 'INFO\|DEBUG\|^ *│\|^ *└'` y guardar la salida en `docs/fase2/goldens/`.
- Migración 012 aplicada a `sebastian_test` y `sebastian_dev`, **no a producción** (H4, Josem). `git commit` siempre por rutas. Automensaje activo: pareja `sebastian2-56`.

**Bloqueos:** ninguno propio; el gasto de H4 espera a Josem.
