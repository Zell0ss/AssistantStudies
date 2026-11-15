# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-11-15):** fase 2, H3 entregado: `docs/fase2/H3-informe.md` (`44cf6dc`). Es el turno del arquitecto. 627 pruebas sin API en verde;
escenarios E1–E9 8/9 (falla E5, ver el informe); #56–#65 9/10 con #57 intermitente (4/4 al repetir); R6 10/10. Gasto de la fase ≈ 4,51 $ de 5 $
(margen ≈ 0,5 $: no cabe otra pasada completa).

**Siguiente paso:** el que diga el arquitecto tras revisar H3. No empezar H4 (retirada del Sprint 3 y despliegue) sin su revisión. Lo más probable:
la regla del prompt del planner para el historial (informe, Decisiones §1) y R3/E9 (§2).

**Gotchas:**
- Dos venv: `sebastian2/.venv` (3.12 + anthropic 1.14) es el de este worktree; el de producción (`/data/AssistantStudies/sebastian2/.venv`) sin tocar.
  Para `pytest` desde `sebastian2/`: `.venv/bin/python -m pytest`. Los goldens: `-m golden`, siempre con `-k`; cualquier gasto nuevo necesita el «sí» de Josem en esta ventana.
- Un fallo de tool en goldens vuelca ~8.000 líneas de trazas: filtrar con `grep -v 'INFO\|DEBUG\|^ *│\|^ *└'` y guardar la salida en `docs/fase2/goldens/`.
- `config.yaml` del worktree apunta a `sebastian_test` y `sebastian_memory_test`; el harness usa solo `<base>_catalogo` y `<base>_notas`. La migración 012 está aplicada a
  `sebastian_test` y `sebastian_dev`, **no a producción** (H4, Josem). `modules/memory.py` sigue en el repo (H4 lo borra); el ejecutor ya no lo usa.
- `golden_test_user` y `golden_test_user_b`: `limpiar_memoria` (tests/golden/memoria_base.py) borra hechos, fuentes, decisiones y entidades al empezar **y al terminar** cada golden.
- `git commit` siempre por rutas (`-- <ruta>`): el arquitecto comparte la copia de trabajo.
- El automensaje está activo: la pareja es `sebastian2-56` (tmux `sebastian-arq`).

**Bloqueos:** ninguno propio; esperan a Josem el gasto futuro y, en H4, aplicar 010–012 en producción.
