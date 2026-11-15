# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-11-15):** fase 2, H4 entregado: `docs/fase2/H4-informe.md`, listo para el despliegue de Josem. Es el turno del arquitecto. 674 pruebas sin API en verde.
[API]: 65/66 goldens (#28 intermitente) y escenarios 7/9 (fallan E5 y E9). No se ha desplegado, fusionado ni reiniciado nada y no se ha tocado producción.

**Siguiente paso:** el que diga el arquitecto. Lo más probable: la guarda en código para «dice que olvidó y no olvidó» (informe, Decisiones §1), E9/regla C (§2) y #28 (§3).
Después, el despliegue lo ejecuta Josem con `deploy/PASOS-CON-SUDO.md` («Fase 2») y `deploy/comprobar_fase2.sh`.

**Gotchas:**
- **Gasto de la fase ≈ 8,61 $, sin autorización para más.** Josem: tope 5 $; «hasta 2 €»; «otros 3 euros si hace falta» (gastado 2,15 $ de esos). Nada [API] sin un «sí» nuevo en mi ventana, y `git log` del buzón antes de cada paso.
- `migrar_sprint3.py` casa por palabras normalizadas y **no he visto los textos reales de producción**: el `--dry-run` del paso 4 es el control (los pasos le dicen a Josem que pare si algo sale «sin mapa»).
- `indexar_catalogo.py` y el paso 5 son una adición mía al plan (en producción nadie indexa los atributos semilla).
- La regla del planner (D43) vive en `_REGLA_ACCIONES_CON_HISTORIAL` (`core/orchestrator.py`), al final del prompt. Evidencia: puede mandar el primer turno de E9 a `salud`.
- `-k "golden_1"` casa también `golden_10`…: usar ids exactos. Un fallo de tool en goldens vuelca miles de líneas: filtrar con `grep -v 'INFO\|DEBUG\|^ *│\|^ *└\|Turn end'`.
- Dos venv: `sebastian2/.venv` (3.12 + anthropic 1.14) es el de este worktree; el de producción, el de H0 si Josem ya lo desplegó (el paso 0 de los pasos lo comprueba).
- Migración 012 aplicada a `sebastian_test` y `sebastian_dev`, **no a producción**. `git commit` siempre por rutas. Automensaje activo: pareja `sebastian2-56`.

**Bloqueos:** ninguno propio; el gasto nuevo y el despliegue esperan a Josem.
