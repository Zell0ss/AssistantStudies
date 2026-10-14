# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-10-14):** fase 2, H0 con el anexo «esfuerzo medium» entregado
(`docs/fase2/H0-informe.md`). D28 no se adopta: Haiku 5.5 no cumple el criterio ni con `low` (51/55) ni con
`medium` (47/55); el planner vuelve a Haiku 4.5 con `_PLANNER_EXTRA = {}`. SDK/Python aprobado (3.12 + anthropic 1.14).
Hallazgo: `requests` 2.34 rompe `requests-cache` 1.2.1 (el tiempo dejaba de responder): fijado `requests==2.32.5`.
Espera la revisión del arquitecto y el despliegue de Josem (pasos y vuelta atrás en el informe). Worktree:
`/data/AssistantStudies-fase2`.

**Siguiente paso:** el que diga la revisión (decisión pendiente: entorno A = solo `requests`, o B = constraints con
el `pip freeze` de producción). El plan de la fase 2 lo escribe el arquitecto.

**Gotchas:**
- Hay dos venv en el worktree: `sebastian2/.venv` es el **nuevo** (3.12 + anthropic 1.14, con `pytest==9.0.2`
  instalado a mano); el de producción (`/data/AssistantStudies/sebastian2/.venv`, 3.11 + 0.79) sigue sin tocar.
  Para `pytest` desde `sebastian2/`: `.venv/bin/python -m pytest`.
- `config.yaml` del worktree: `sebastian_test`, `sebastian_memory_test` y `tristras_url` `:8013` (nunca `:8003`).
- Gasto de H0: 0,99 $ de 1,2 $ (≈ 0,21 $ de margen): sin margen para otra pasada completa. Cualquier pasada nueva necesita autorización nueva de Josem en esta ventana.
- `tests/golden/test_aclaracion.py` se salta con Haiku 4.5 (no llama nunca a `request_clarification`): ver el anexo.

**Bloqueos:** ninguno.
