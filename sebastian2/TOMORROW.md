# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-11-15):** fase 2, H4: retoques R15 y R16 entregados como anexo de `docs/fase2/H4-informe.md`. Es el turno del arquitecto y, después, el despliegue de Josem
(`deploy/PASOS-CON-SUDO.md` «Fase 2» y `deploy/comprobar_fase2.sh`). 683 pruebas sin API en verde. [API]: E5 3/3, #66 2/2, #28 3/3, calendario y #56–#66 16/16.
No se ha desplegado, fusionado ni reiniciado nada y no se ha tocado producción.

**Siguiente paso:** el que diga el arquitecto o Josem. No hay trabajo del programador pendiente. Si se pide, lo posible: forzar el camino de R15 en E5 (planner parcheado para no llamar a la tool) y la redacción de #28.

**Gotchas:**
- **Gasto de la fase ≈ 9,39 $, sin autorización para más.** Josem: tope 5 $; «hasta 2 €»; «otros 3 euros si hace falta» (2,15 $ de H4); y un «Si» a ≈ 1 $ para R15/R16 (0,78 $ gastados). Nada [API] sin un «sí» nuevo en mi ventana, y `git log` del buzón antes de cada paso.
- `migrar_sprint3.py` casa por palabras normalizadas y **no he visto los textos reales de producción**: el `--dry-run` del paso 4 es el control (los pasos le dicen a Josem que pare si algo sale «sin mapa»).
- `indexar_catalogo.py` y el paso 5 son una adición mía al plan (en producción nadie indexa los atributos semilla).
- La regla del planner (D43) vive en `_REGLA_ACCIONES_CON_HISTORIAL` (`core/orchestrator.py`), al final del prompt. Evidencia: puede mandar el primer turno de E9 a `salud`.
- `-k "golden_1"` casa también `golden_10`…: usar ids exactos. Un fallo de tool en goldens vuelca miles de líneas: filtrar con `grep -v 'INFO\|DEBUG\|^ *│\|^ *└\|Turn end'`.
- Dos venv: `sebastian2/.venv` (3.12 + anthropic 1.14) es el de este worktree; el de producción, el de H0 si Josem ya lo desplegó (el paso 0 de los pasos lo comprueba).
- Migración 012 aplicada a `sebastian_test` y `sebastian_dev`, **no a producción**. `git commit` siempre por rutas. Automensaje activo: pareja `sebastian2-56`.

**Bloqueos:** ninguno propio; el gasto nuevo y el despliegue esperan a Josem.
