# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-10-14):** fase 2, H0 entregado (`docs/fase2/H0-informe.md`): evaluación de Haiku 5.5
como planner (D28: 51/55 goldens, 4 fallos estables → criterio 1 no cumplido; coste y latencia sí) y Python 3.12 +
anthropic 1.14 (417 tests, sin cambios de código). Espera la revisión del arquitecto y, después, el despliegue
de Josem (pasos y vuelta atrás al final del informe). Worktree: `/data/AssistantStudies-fase2`.

**Siguiente paso:** el que diga la revisión. Si D28 no se adopta: `_MODELO_PLANNER = "claude-haiku-4-5-20251001"`
y `_PLANNER_EXTRA = {}` (`effort` da 400 en Haiku 4.5), en un commit aparte antes del merge. El plan de la fase 2
lo escribe el arquitecto.

**Gotchas:**
- Hay dos venv en el worktree: `sebastian2/.venv` es el **nuevo** (3.12 + anthropic 1.14, con `pytest==9.0.2`
  instalado a mano); el de producción (`/data/AssistantStudies/sebastian2/.venv`, 3.11 + 0.79) sigue sin tocar.
  Para `pytest` desde `sebastian2/`: `.venv/bin/python -m pytest`.
- `config.yaml` del worktree: `sebastian_test`, `sebastian_memory_test` y `tristras_url` `:8013` (nunca `:8003`).
- Gasto de H0: 0,40 $ de 1,2 $. Cualquier pasada nueva necesita autorización nueva de Josem en esta ventana.
- Los goldens #21, #28, #48, #49 fallan de forma estable con Haiku 5.5: no se reescriben sin decisión del arquitecto.

**Bloqueos:** ninguno.
