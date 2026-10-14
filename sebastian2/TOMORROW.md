# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-10-14):** fase 2, H0 con el anexo 2 («entorno fijado») entregado
(`docs/fase2/H0-informe.md`). D28 no se adopta (planner en Haiku 4.5). `requirements.txt` es el freeze completo del
`.venv` (Python 3.12 + anthropic 1.14 + requests 2.32.5; reproduce el venv exactamente). Listo para que Josem lo
despliegue (pasos y vuelta atrás al final del anexo 2). Worktree: `/data/AssistantStudies-fase2`.

**Siguiente paso:** el que diga el arquitecto tras revisar el anexo 2. El plan de la fase 2 lo escribe él.

**Gotchas:**
- Hay dos venv en el worktree: `sebastian2/.venv` es el **nuevo** (3.12 + anthropic 1.14, con `pytest==9.0.2`
  instalado a mano; ya viene en el freeze); el de producción (`/data/AssistantStudies/sebastian2/.venv`, 3.11 + 0.79) sigue sin tocar.
  Para `pytest` desde `sebastian2/`: `.venv/bin/python -m pytest`.
- `config.yaml` del worktree: `sebastian_test`, `sebastian_memory_test` y `tristras_url` `:8013` (nunca `:8003`).
- Gasto de H0: 1,09 $ de 1,2 $ (≈ 0,11 $ de margen): sin margen para otra pasada completa. Cualquier pasada nueva necesita autorización nueva de Josem en esta ventana.
- `tests/golden/test_aclaracion.py` se salta con Haiku 4.5 (no llama nunca a `request_clarification`): ver el anexo.

**Bloqueos:** ninguno.
