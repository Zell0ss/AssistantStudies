# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-11-15):** fase 2, H3 aprobado con retoques (`H3-revision.md`, `36c3f90`). Hechos y commiteados los retoques **sin API**: R8 (reglas de
planner y Alfred + golden #66), R9 (retirar por valor), R10 (`_validar`, aviso, casos 1 y 2), R11 (Alfred y el vault): `809f697`, `48cc4f3`, `e200440`.
654 pruebas sin API en verde, 90 `golden`. Falta TODO lo [API] y el anexo del informe.

**Siguiente paso (todo [API]; no se lanza nada hasta que Josem suba el tope de la fase a 8 $ y diga «sí» en su ventana; antes de CADA paso: `git log` del buzón, §2.4):**
1. #66 ×3 y E5 ×3 (criterio de la revisión: 3/3 en los dos). Línea base de #66 solo con `-k`.
2. R10: los 10 casos del extractor (`pytest -m golden tests/golden/test_extractor.py`; los casos 1 y 2 ya cambiados).
3. `-k` #56–#66 (una pasada) y escenarios E1–E9 (E5 con tabla de `mem_hechos`/`mem_fuentes`; E9b ya está como prueba sin API).
4. Anexo en `docs/fase2/H3-informe.md` (resultados, gasto por modelo, respuestas de E5 pegadas), commit por rutas, y timbre a `sebastian2-56`.
5. **R12** solo si Josem dice «sí» al punto 2 de §4 de la revisión: el log de inicio de turno deja de guardar el texto del mensaje (longitud e id), con la prueba de que
   el log no lo contiene (`orchestrator.py` ~430, «Turn start»).

**Gotchas:**
- Gasto de la fase ≈ 4,51 $ de 5 $; los retoques [API] ≈ 0,8 $ (la revisión estima 3,1 $ en total con H4). Anotar quién autorizó y cuándo en el anexo.
- R9 compara como **palabras completas** («M» no cierra «marzo»; la revisión decía «contiene»: refinamiento mío, hay prueba) y se dispara igual que R3 (entidad o atributo sin resolver con fuerza).
  R3 y R9 comparten el límite de un cierre indirecto por turno (`turno["cierres_indirectos"]`).
- R10: el `Extractor` expone `marcadores_descartados` (de la última llamada); el servicio avisa en `sin_cambio` y el resultado dice «No sé de quién o de qué se habla».
- R8 y R11 comparten commit (mismo bloque de `_ALFRED_SYSTEM`); R9 y la parte de servicio de R10, también (mismo fichero).
- Dos venv: `sebastian2/.venv` (3.12 + anthropic 1.14) es el de este worktree; el de producción sin tocar. `pytest` desde `sebastian2/`: `.venv/bin/python -m pytest`; goldens: `-m golden` con `-k`.
- Un fallo de tool en goldens vuelca ~8.000 líneas: filtrar con `grep -v 'INFO\|DEBUG\|^ *│\|^ *└'` y guardar la salida en `docs/fase2/goldens/`.
- Migración 012 aplicada a `sebastian_test` y `sebastian_dev`, **no a producción** (H4, Josem). `git commit` siempre por rutas. Automensaje activo: pareja `sebastian2-56`.

**Bloqueos:** el tope de 8 $ y el «sí» de Josem; y su respuesta al punto 2 de §4 (log de turno).
