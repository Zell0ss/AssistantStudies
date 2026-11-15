# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-11-15):** fase 2, H4 aprobado con retoques (`H4-revision.md`, `6223100`). Hechos y commiteados los retoques **sin API**: R15 (D44, `_TURNO_SIN_HERRAMIENTAS`,
`047f2aa`) y R16 (`calendar_add_event` no inventa la hora, golden #28 ampliado, `fb0cd6f`). 683 pruebas sin API en verde. Falta el [API] y el anexo de `H4-informe.md`.

**Siguiente paso (todo [API]; solo con el «sí» de Josem a ≈ 1 $ en su ventana, y `git log` del buzón antes de cada paso):**
1. E5 ×3 (`-k E5` en `tests/golden/test_escenarios_memoria.py`). Criterio: en ningún caso Alfred afirma haber retirado algo que sigue vigente en la BD; pasa si se retira o si Alfred dice que no lo hizo.
2. #66 ×2 y #28 ×3 (`-k golden_66`, `-k golden_28`).
3. `-k` con ids exactos de los goldens de calendario (#7, #8, #9, #40, #50) y #56–#66: los ids de pytest llevan dos dígitos (`golden_07`, `golden_40`, `golden_56`…).
4. Anexo en `docs/fase2/H4-informe.md` (resultados, gasto por modelo, quién autorizó y cuándo), commit por rutas y timbre a `sebastian2-56`. Luego, el despliegue lo ejecuta Josem: no desplegar, no fusionar, no reiniciar.

**Gotchas:**
- **Gasto de la fase ≈ 8,61 $.** Josem: tope 5 $; «hasta 2 €»; «otros 3 euros si hace falta» (gastado 2,15 $ de esos, ≈ 0,85 $ sin usar). La revisión pide un «sí» a 1 $ en mi ventana para R15/R16 (≈ 0,6 $): no lo doy por dado. Antes de cada paso [API], `git log` del buzón.
- `migrar_sprint3.py` casa por palabras normalizadas y **no he visto los textos reales de producción**: el `--dry-run` del paso 4 es el control (los pasos le dicen a Josem que pare si algo sale «sin mapa»).
- `indexar_catalogo.py` y el paso 5 son una adición mía al plan (en producción nadie indexa los atributos semilla).
- La regla del planner (D43) vive en `_REGLA_ACCIONES_CON_HISTORIAL` (`core/orchestrator.py`), al final del prompt. Evidencia: puede mandar el primer turno de E9 a `salud`.
- `-k "golden_1"` casa también `golden_10`…: usar ids exactos. Un fallo de tool en goldens vuelca miles de líneas: filtrar con `grep -v 'INFO\|DEBUG\|^ *│\|^ *└\|Turn end'`.
- Dos venv: `sebastian2/.venv` (3.12 + anthropic 1.14) es el de este worktree; el de producción, el de H0 si Josem ya lo desplegó (el paso 0 de los pasos lo comprueba).
- Migración 012 aplicada a `sebastian_test` y `sebastian_dev`, **no a producción**. `git commit` siempre por rutas. Automensaje activo: pareja `sebastian2-56`.

**Bloqueos:** ninguno propio; el gasto nuevo y el despliegue esperan a Josem.
