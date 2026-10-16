# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-10-16):** fase 2, H2 entregado (`docs/fase2/H2-informe.md`): extractor, resolución, `ServicioMemoria.guardar`
y `mark_as_memorable` con el contrato nuevo; 10/10 casos del extractor y 5/5 goldens (#20, #21, #22, #30, #36). Gasto de la fase ≈ 0,136 $ de 5 $.

**Siguiente paso:** el que diga el arquitecto tras revisar H2. No empezar H3 sin su revisión.

**Gotchas:**
- Hay dos venv en el worktree: `sebastian2/.venv` es el **nuevo** (3.12 + anthropic 1.14, con `pytest==9.0.2`
  instalado a mano; ya viene en el freeze); el de producción (`/data/AssistantStudies/sebastian2/.venv`, 3.11 + 0.79) sigue sin tocar.
  Para `pytest` desde `sebastian2/`: `.venv/bin/python -m pytest`.
- `config.yaml` del worktree: `sebastian_test`, `sebastian_memory_test` y `tristras_url` `:8013` (nunca `:8003`).
- Gasto de la fase 2: ≈ 0,136 $ de 5 $ (tope autorizado). Antes, gasto de H0: 1,09 $ de 1,2 $ (≈ 0,11 $ de margen): sin margen para otra pasada completa. Cualquier pasada nueva necesita autorización nueva de Josem en esta ventana.
- `tests/golden/test_aclaracion.py` se salta con Haiku 4.5 (no llama nunca a `request_clarification`): ver el anexo.

**Bloqueos:** ninguno.
