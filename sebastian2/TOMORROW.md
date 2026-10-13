# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-10-14):** fase 1 completa en la rama `fase-1` (worktree
`/data/AssistantStudies-fase1`), H1–H3 aprobados por el arquitecto (`ac9f04b`). Nada pendiente
para el programador.

**Siguiente paso:** lo hace Josem — `sebastian2/deploy/PASOS-CON-SUDO.md` §«Fase 1» (pasos 1–6),
`deploy/comprobar_fase1.sh` y la prueba por Telegram («¿qué tiempo hace en Madrid?» → «¿y mañana?»).
Hasta entonces, no quitar el worktree: si la prueba falla, se arregla ahí. Si falla, mirar primero
`logcentral query --source sebastian --level error` y el warning «No se pudo leer el historial».

**Gotchas:**
- Tests: `/data/AssistantStudies/sebastian2/.venv/bin/python -m pytest` desde `sebastian2/`
  (401 verdes). Los goldens son [API]: `-m golden`, ≈ 0,94 $ la pasada completa (52).
- Gasto de la fase: ≈ 1,9 $ de 2 $. **Sin margen para otra pasada completa sin nueva autorización.**
- El `config.yaml` del worktree es una copia que apunta a `sebastian_test`; no tocar el de producción.
- `limpiar(7)` borra de toda la tabla `conversations` (no por usuario).

**Bloqueos:** ninguno.
