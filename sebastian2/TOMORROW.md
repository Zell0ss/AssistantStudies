# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-10-14):** fase 1 reabierta para H4 (D26 honestidad de Alfred, D27 goldens
sin servicios reales). H4 implementado y con informe (`docs/fase1/H4-informe.md`); espera la revisión
del arquitecto y, después, el despliegue de Josem (los dos comandos están al final del informe).
Worktree `/data/AssistantStudies-fase1` recreado por el arquitecto; no quitarlo hasta que cierre H4.

**Siguiente paso:** el que diga la revisión de H4. Nada de la fase 2 sin su plan.

**Gotchas:**
- Tests: `/data/AssistantStudies/sebastian2/.venv/bin/python -m pytest` desde `sebastian2/`
  (409 verdes). Goldens [API]: `-m golden`, ≈ 1,06 $ la pasada completa (55 + 3 de síntesis).
- **El `config.yaml` del worktree lleva `tristras_url` en `:8013` a propósito:** nunca `:8003`.
  El harness ya lo neutraliza (D27), pero no lo cambies.
- Gasto de H4: 1,06 $ (tope 1 $, superado en 0,06 $: ver el informe). Cualquier pasada nueva
  necesita autorización nueva.
- `limpiar(7)` borra de toda la tabla `conversations` (no por usuario).

**Bloqueos:** ninguno.
