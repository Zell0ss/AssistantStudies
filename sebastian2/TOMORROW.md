# tomorrow.md — Sebastian 2.0 (programador)

**Fase 1 cerrada (2026-10-14).** Desplegada por Josem, comprobada por el arquitecto (`76fa3cb`):
`comprobar_fase1.sh` todo OK y prueba por Telegram correcta. **No hay nada en curso.**

El worktree `/data/AssistantStudies-fase1` se ha quitado; la rama `fase-1` se queda (el merge final
de sus docs, si se quiere, lo hace Josem). La siguiente fase (memoria v1, fase 2 del ADR-MEMORIA)
la abre el arquitecto con su plan.

**Gotchas que siguen valiendo:**
- Tests: `.venv/bin/python -m pytest` desde `sebastian2/` (401 verdes). Goldens [API]: `-m golden`,
  ≈ 0,94 $ la pasada; el gasto de la fase 1 (≈ 1,9 $ de 2 $) ya está cerrado: cualquier gasto nuevo
  necesita autorización nueva.
- Para trabajar en una rama, `git worktree add` con su propio `config.yaml` copiado (apuntando a
  `sebastian_test`/`sebastian_dev`), nunca el de producción.
- D21 y D23 siguen `tentativa` (tamaño de la ventana del historial) hasta que el uso real lo confirme.

**Bloqueos:** ninguno.
