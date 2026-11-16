# tomorrow.md — Sebastian 2.0 (programador)

**Punto de parada (2026-11-16): H1 DE LA FASE 3 ENTREGADO, ESPERANDO LA REVISIÓN DEL ARQUITECTO.** Informe: `docs/fase3/H1-informe.md`. Rama `fase-3`, worktree `/data/AssistantStudies-fase3`. 731 pruebas sin API en verde (683 antes).
**No empezar H2 sin la revisión de H1.** Buzón: `git log -1 --format='%h %ad %s' --date=short --name-only -- 'docs/fase3/H*-revision.md' 'docs/fase3/H*-encargo.md' 'docs/fase3/H*-informe.md' docs/fase3/PLAN.md`.

**Fase 2 (aparte):** aprobada y a la espera del despliegue de Josem (`deploy/PASOS-CON-SUDO.md`, «Fase 2»; control clave: el `--dry-run` del paso 4). Si falla algo, Josem lo trae y el arreglo va como anexo a `docs/fase2/H4-informe.md`, en la rama `fase-2` (`/data/AssistantStudies-fase2`).

**Gotchas (fase 3):**
- **Gasto de la fase 3: 0,00 $ de 4 $** (Josem, 2026-11-16, en la ventana del arquitecto). Cada paso [API] se confirma además en mi ventana. Antes del primer [API] de H3: comprobar con la skill `claude-api` que `claude-haiku-4-5-20251001` y `claude-sonnet-4-6` siguen servidos y los precios (1/5 $ y 3/15 $ por millón).
- Migración 013 aplicada a `sebastian_test` y `sebastian_dev`, **no a producción** (el despliegue es H4, de Josem). `git commit` siempre por rutas.
- `.venv` y `config.yaml` del worktree de la fase 3 son copias propias (el `config.yaml` apunta a `sebastian_test`).
- La FK `compromisos.evento_id → events` no tiene ON DELETE y bloquea el borrado del evento aunque el compromiso esté cancelado: `cancelar_por_eventos_borrados` pone `evento_id = NULL` (desviación 1 del informe; pendiente de la respuesta del arquitecto). Cualquier `DELETE FROM events` nuevo (fixtures incluidos) tiene que pasar por ahí o borrar antes los compromisos.
- Los datos de las pruebas son inventados: el caso de la colonoscopia usa fechas y pasos, ningún nombre, teléfono ni centro reales.
- PyMySQL devuelve las columnas TIME como `timedelta`: `_hora()` en `modules/compromisos.py` las normaliza.
- H2 usará `CompromisosModule.pendientes()` (momentos tipados) y `armar_resumen(usuario, ahora)` como función pura, con bot falso y reloj inyectado; ninguna prueba manda a Telegram de verdad.
- Heredado de la fase 2: `-k "golden_1"` casa también `golden_10`…: usar ids exactos. Un fallo de tool en goldens vuelca miles de líneas: filtrar con `grep -v 'INFO\|DEBUG\|^ *│\|^ *└\|Turn end'`.

**Bloqueos:** ninguno propio; H2 espera la revisión de H1.
