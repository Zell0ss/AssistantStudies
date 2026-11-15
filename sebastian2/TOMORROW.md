# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-11-15):** fase 2, H3 implementado y commiteado en `fase-2` (hasta `691c03b`), **sin `H3-informe.md` todavía**
(escribirlo pasa el turno al arquitecto: solo cuando estén las pasadas [API] de abajo). 626 pruebas sin API en verde.
Hecho: R1–R4 (de la sesión anterior), R3 (retirar nota por similitud), `vault.py`, `consultar`/`search_memory` nuevo, índice del
planner (D36), harness sobre MariaDB, escenarios E1–E9, R5 (goldens #64–#65, sin lanzar), R6 (regla 5 del extractor, sin repasar los 10
casos), R7 (migración 012 `mem_fuentes`, `mensaje` hasta el servicio, purga de D42; E5 ampliado, sin lanzar).

**Siguiente paso (todo [API]: necesita el «sí» de Josem en su ventana y el tope):**
1. `-k` de #64 y #65 (línea base de R5). Si #65 falla por `mark_as_memorable`: añadir a su descripción «citas y eventos con fecha, aunque
   diga "recuerda que"» y repetir `-k` #56–#65. Si falla por `salud`: NO arreglar, pegarlo en el informe.
2. R6: los 10 casos del extractor (`pytest -m golden tests/golden/test_extractor.py`).
3. Escenarios E1–E9 (`tests/golden/test_escenarios_memoria.py`); pegar las respuestas y la tabla de `mem_hechos`/`mem_fuentes` tras E5.
4. Escribir `docs/fase2/H3-informe.md` (Hecho · Gasto · Desviaciones · Decisiones que necesito) y commit por rutas.

**Para el informe (no está escrito en ningún otro sitio):**
- Pasada completa (63 goldens + E1–E9 + honestidad) ya hecha, **antes** de leer `H3-encargo.md` (error de orden mío: no volví a mirar el buzón
  antes de lanzarla): 62/63 (#43 intermitente: con índice 2/3, sin índice 1/3), `docs/fase2/goldens/2026-11-15-completa-h3-resumen.txt`.
  Línea base #56–#63 sobre `7affdd3` (worktree temporal, ya retirado): 7/8, falla #62 (planner elige `search_memory`).
- Bugs que destapó y arreglé (`eaffa3d`): punto huérfano de entidad en `<base>_catalogo` (FK al guardar), `search_memory` sin `query`
  (KeyError), y mi línea de `_ALFRED_SYSTEM` hacía que Alfred dijera «permítame consultarlo» (honestidad H1).
- Extractor (R4): 8/10 tras el cambio de prompt; casos 1 y 2 intermitentes (A/B: el 2 es igual de ruidoso sin R4). Además devuelve a veces la
  entidad literal `<UNKNOWN>`, que crearía una entidad con ese nombre.
- E5: con historial el planner imita a Alfred y contesta «He retirado…» sin llamar a la tool (0/3), sin historial sí la llama (1/1).
- E9: «Uso camisetas UV…» se guarda como `preferencia`, no como `nota`; R3 solo busca notas → no aplica. Hueco de diseño.
- E6: la BD sale bien siempre (`crear_atributo`, `pending`); que Alfred nombre lo nuevo (D16) es intermitente.
- E8: Alfred ofrece «corrijo el vault» (D37: Sebastian no lo escribe).
- Gasto: ≈ 3,1 $ en esta ventana (medido 2,88 $ + ≈ 0,22 $ estimado: no capturé la tabla de E5×2 y #43×1) + 0,136 $ antes = **≈ 3,24 $ de 5 $**.
  Autorizado por Josem el 2026-11-15 en esta ventana («Si, adelante»), sin cifra: lo tomé como el tope vigente de 5 $.
- Desviaciones: toda nota (atributo `nota`) se embebe en `<base>_notas`, no solo las de resolución débil (R3 lo necesita); `search_memory`
  admite atributo sin entidad; umbral de notas en la consulta = `reutilizar.puntuacion` (0,58, tentativo); índice solo de entidades con hechos
  vigentes; vault solo para el propietario (`cuaderno_chat_id`); el historial no muestra lo olvidado (D42); tests reescritos: los de
  `search_memory` del ejecutor (contrato nuevo), `test_sin_memory_collection_falla` (ahora sobre `_servicio_memoria`), E6 compara sin tildes.

**Gotchas:**
- Dos venv: `sebastian2/.venv` (3.12 + anthropic 1.14) es el de este worktree; el de producción (`/data/AssistantStudies/sebastian2/.venv`) sin tocar.
  Para `pytest` desde `sebastian2/`: `.venv/bin/python -m pytest`. Los goldens: `-m golden`, siempre con `-k` para acotar el gasto.
- `config.yaml` del worktree apunta a `sebastian_test` y `sebastian_memory_test`; el harness ya no usa la colección plana, solo
  `<base>_catalogo` y `<base>_notas` (se recrean en cada sesión). Migración 012 aplicada a `sebastian_test` y `sebastian_dev`; **no a producción** (H4, Josem).
- Los escenarios y los goldens usan `golden_test_user` y `golden_test_user_b`; `limpiar_memoria` (tests/golden/memoria_base.py) borra hechos, fuentes,
  decisiones y entidades de los dos al empezar cada golden.
- `git commit` siempre por rutas (`-- <ruta>`): el arquitecto comparte la copia de trabajo y deja commits mientras trabajo.
- `.venv/bin/python -m pytest -m golden …` imprime ~8.000 líneas de trazas si falla una tool: filtrar con `grep -v 'INFO\|DEBUG'` y guardar en `docs/fase2/goldens/`.

**Bloqueos:** el «sí» de Josem al gasto de los pasos 1–3 y la decisión sobre el tope (quedan ≈ 1,76 $; los pasos 1–3 son ≈ 0,6–0,85 $; repetir
la pasada completa de 65 goldens, como pide el encargo, serían ≈ 1,9 $ más y no cabe).
