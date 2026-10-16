# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-10-16):** fase 2, H1 entregado (`docs/fase2/H1-informe.md`): migraciones 010/011 aplicadas a
`sebastian_test` y `sebastian_dev`, `core/memoria/`, `crear_colecciones.py`, calibración hecha (salida en
`docs/fase2/goldens/`). 1 test normativo en rojo a propósito (`Cumpleaños`, contradicción del plan §2.4; decide el arquitecto).

**Siguiente paso:** el que diga el arquitecto tras revisar H1. No empezar H2 sin su revisión. Los umbrales los fija él.

**Gotchas:**
- Hay dos venv en el worktree: `sebastian2/.venv` es el **nuevo** (3.12 + anthropic 1.14, con `pytest==9.0.2`
  instalado a mano; ya viene en el freeze); el de producción (`/data/AssistantStudies/sebastian2/.venv`, 3.11 + 0.79) sigue sin tocar.
  Para `pytest` desde `sebastian2/`: `.venv/bin/python -m pytest`.
- `config.yaml` del worktree: `sebastian_test`, `sebastian_memory_test` y `tristras_url` `:8013` (nunca `:8003`).
- Gasto de la fase 2: ≈ 0,001 $ de 5 $ (tope autorizado). Antes, gasto de H0: 1,09 $ de 1,2 $ (≈ 0,11 $ de margen): sin margen para otra pasada completa. Cualquier pasada nueva necesita autorización nueva de Josem en esta ventana.
- `tests/golden/test_aclaracion.py` se salta con Haiku 4.5 (no llama nunca a `request_clarification`): ver el anexo.

**Bloqueos:** ninguno.
