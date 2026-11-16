"""Golden regression harness — fixtures.

CRITICAL SAFETY GUARDRAIL: this harness performs real writes/deletes (golden #3
deletes notes) and must NEVER touch sebastian_db (production). The `test_db`
fixture asserts the connected schema is exactly TEST_DB_NAME before yielding a
connection to anything — if that assertion fails, the whole session aborts
immediately. This is a hard assert, not a naming convention.

Same guardrail extends to memory: golden #20 writes real facts via mark_as_memorable,
so `config_de_goldens` refuses to run unless Qdrant is reachable, and never resolves
to the real 'sebastian_memory' base. Since fase 2 (H3) the memory is MariaDB
(sebastian_test) plus `<base>_catalogo` and `<base>_notas` in Qdrant, recreated every
session; there is no flat `sebastian_memory_test` collection any more.
"""
import time
from contextlib import ExitStack
from datetime import date, datetime, timedelta

import pymysql
import pytest

from tests.golden.aislamiento import neutralizar_servicios_externos
from tests.golden.estado import limpiar_agenda, limpiar_sembrado, sembrar_estado
from tests.golden.memoria_base import (
    USUARIO_B, limpiar_atributos_de_conversacion, limpiar_memoria, sembrar_memoria_base,
)
from utils.config import get_config

TEST_DB_NAME = "sebastian_test"
TEST_MEMORY_COLLECTION = "sebastian_memory_test"
GOLDEN_USER_ID = "golden_test_user"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "golden: end-to-end orchestrator regression tests (real Anthropic API calls, real sebastian_test DB)",
    )


def _imprimir_escenarios(terminalreporter):
    """Fase 2 H3: los escenarios con estado pegan en el informe las respuestas de cada turno."""
    try:
        from tests.golden.test_escenarios_memoria import RESULTADOS
    except ImportError:
        return
    if not RESULTADOS:
        return
    terminalreporter.write_sep("=", "ESCENARIOS DE MEMORIA (turnos, tools y respuestas de Alfred)")
    for r in RESULTADOS:
        terminalreporter.write_line("")
        terminalreporter.write(f"{r['id']} ", bold=True)
        terminalreporter.write_line(r["titulo"])
        for frase, tools, texto in r["turnos"]:
            terminalreporter.write_line(f"  Usuario:   {frase}")
            terminalreporter.write_line(f"  Tools:     {' → '.join(tools) if tools else '(ninguna)'}")
            terminalreporter.write_line(f"  Alfred:    {texto}")
        for linea in r.get("bd", []):
            terminalreporter.write_line(f"  BD:        {linea}")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print the golden → expected → actual → PASS/FAIL report + X/14 summary."""
    try:
        from tests.golden.test_goldens import GOLDEN_RESULTS
    except ImportError:
        return
    from tests.golden.uso import USO
    _imprimir_escenarios(terminalreporter)
    if not GOLDEN_RESULTS:
        if USO.por_modelo or USO.tokens_embedding:
            terminalreporter.write_sep("=", "USO DE LA API (Anthropic: Orchestrator._track_usage; OpenAI: embeddings.create)")
            for linea in USO.tabla():
                terminalreporter.write_line(linea)
        return

    terminalreporter.write_sep("=", "GOLDEN REGRESSION REPORT")
    for r in GOLDEN_RESULTS:
        status = "PASS" if r["passed"] else "FAIL"
        color = "green" if r["passed"] else "red"
        terminalreporter.write_line("")
        terminalreporter.write(f"#{r['id']:02d} [{status}] ", **{color: True, "bold": True})
        terminalreporter.write_line(f"mode={r['mode']}")
        terminalreporter.write_line(f"  Frase:     {r['phrase']}")
        terminalreporter.write_line(f"  Esperado:  {r['expected']}")
        terminalreporter.write_line(f"  Real:      {r['actual']}")
        terminalreporter.write_line(f"  Valida:    {r['validates']}")
        terminalreporter.write_line(f"  Alfred:    {r['response_text'][:200]}")
        for texto in r.get("planner_sin_tools", []):          # H3c R10: solo en el informe del test, nunca en el log (D42)
            terminalreporter.write_line(f"  Planner sin tool: {texto[:400]!r}")
        if r.get("ventanas"):                                 # H5: informativo, no hace fallar nada
            terminalreporter.write_line(f"  time_window: {r['ventanas']}")
        for entrada in r.get("creaciones", []):               # H7: qué fecha y hora se creó (solo en el informe del test)
            terminalreporter.write_line(f"  compromisos_crear: {entrada}")

    passed_count = sum(1 for r in GOLDEN_RESULTS if r["passed"])
    total = len(GOLDEN_RESULTS)
    terminalreporter.write_sep("=", "USO DE LA API (Anthropic: Orchestrator._track_usage; OpenAI: embeddings.create)")
    for linea in USO.tabla():
        terminalreporter.write_line(linea)
    terminalreporter.write_sep(
        "=", f"RESUMEN: {passed_count}/{total} PASS",
        green=(passed_count == total), red=(passed_count != total), bold=True,
    )


@pytest.fixture(scope="session")
def test_db():
    """Raw connection to the ISOLATED sebastian_test schema. Hard-aborts if misconfigured."""
    creds = get_config()["mariadb"]
    conn = pymysql.connect(
        host=creds["host"],
        port=creds["port"],
        user=creds["user"],
        password=creds["password"],
        database=TEST_DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    cur = conn.cursor()
    cur.execute("SELECT DATABASE() AS db")
    actual_db = cur.fetchone()["db"]
    if actual_db != TEST_DB_NAME:
        conn.close()
        pytest.exit(
            f"REFUSING TO RUN GOLDEN HARNESS: connected database is '{actual_db}', "
            f"expected exactly '{TEST_DB_NAME}'. This guardrail exists because golden #3 "
            f"deletes notes — running this against sebastian_db would delete real data.",
            returncode=1,
        )
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def golden_fixtures(test_db):
    """Seed deterministic fixtures for golden_test_user. Session-scoped: seeded once,
    goldens run in file order (1..19) and don't depend on each other's side effects
    except #3 (deletes notes 1017/1018) and #19 (completes task 9001) — nothing later
    depends on those existing/being open."""
    from modules.calendar import CalendarModule
    from modules.inventory import InventoryModule

    db = test_db
    user_id = GOLDEN_USER_ID
    cur = db.cursor()

    # Wipe this user's data first — isolated schema, safe to nuke and reseed.
    cur.execute("DELETE FROM notes WHERE user_id = %s", (user_id,))
    # Fase 3 (D50): los compromisos apuntan a events con una FK sin ON DELETE; van antes que los eventos.
    cur.execute("DELETE FROM compromisos WHERE user_id = %s", (user_id,))
    cur.execute("DELETE FROM events WHERE user_id = %s", (user_id,))
    cur.execute(
        "DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = %s)",
        (user_id,),
    )
    cur.execute("DELETE FROM lists WHERE user_id = %s", (user_id,))
    # project_tasks is NOT user-scoped (shared with glasspannel) — isolated by project name instead.
    cur.execute("DELETE FROM project_tasks WHERE project = %s", ("saxhero",))
    db.commit()

    # Notes 1017 / 1018 — explicit IDs required by golden #3.
    cur.execute(
        "INSERT INTO notes (id, user_id, content, tags) VALUES (%s, %s, %s, %s)",
        (1017, user_id, "Nota de prueba 1017 (golden harness fixture)", None),
    )
    cur.execute(
        "INSERT INTO notes (id, user_id, content, tags) VALUES (%s, %s, %s, %s)",
        (1018, user_id, "Nota de prueba 1018 (golden harness fixture)", None),
    )
    db.commit()

    # Inventory: Actimel
    inv = InventoryModule(db, user_id, "inventario", "inventory")
    inv.add("Actimel", quantity=2, unit="unidades", threshold=1)

    # Calendar: teatro event tomorrow, with one QR ticket
    tomorrow = date.today() + timedelta(days=1)
    cal = CalendarModule(db, user_id)
    added = cal.add_event(title="teatro", event_date=tomorrow, event_time="20:00")
    event_id = added["event_id"]
    cal.add_ticket(event_id, {"type": "QR_CODE", "value": "GOLDEN-TEST-TICKET-001"})

    # Tasks: one open task in "saxhero" (golden #15) + one with a fixed id to complete (golden #19).
    cur.execute(
        "INSERT INTO project_tasks (project, title, priority) VALUES (%s, %s, %s)",
        ("saxhero", "Practicar escalas (golden harness fixture)", "normal"),
    )
    cur.execute(
        "INSERT INTO project_tasks (id, project, title, priority) VALUES (%s, %s, %s, %s)",
        (9001, "saxhero", "Tarea a completar (golden harness fixture)", "normal"),
    )
    db.commit()

    return {
        "user_id": user_id,
        "tomorrow": tomorrow.isoformat(),
        "event_id": event_id,
        "note_ids": [1017, 1018],
    }


@pytest.fixture(scope="session")
def config_de_goldens(tmp_path_factory):
    """Config dict pointing memory tools at the ISOLATED sebastian_memory_test collection.
    Hard-aborts if that collection isn't reachable — golden #20 writes a real point via
    mark_as_memorable, and this guardrail exists to keep that off 'sebastian_memory'.

    D27: además neutraliza los servicios con escritura que salen de la config (Tristras, Clippings
    del vault, workdir de YouTube): ver tests/golden/aislamiento.py."""
    from qdrant_client import QdrantClient

    if TEST_MEMORY_COLLECTION == "sebastian_memory":
        pytest.exit(
            "REFUSING TO RUN GOLDEN HARNESS: TEST_MEMORY_COLLECTION must not equal the "
            "real 'sebastian_memory' collection name.",
            returncode=1,
        )

    base_config = dict(get_config())
    qdrant_url = base_config.get("qdrant_url", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)
    try:
        client.get_collections()
    except Exception:
        pytest.exit(
            f"REFUSING TO RUN GOLDEN HARNESS: Qdrant ({qdrant_url}) is not reachable. The harness "
            f"recreates '{TEST_MEMORY_COLLECTION}_catalogo' and '{TEST_MEMORY_COLLECTION}_notas' every session.",
            returncode=1,
        )

    base_config["memory_collection"] = TEST_MEMORY_COLLECTION
    # D27: ni Tristras ni el vault real (Clippings) ni el workdir de YouTube, sea cual sea el config.yaml.
    return neutralizar_servicios_externos(base_config, tmp_path_factory.mktemp("goldens"))


@pytest.fixture(scope="session")
def memory_fixtures(config_de_goldens, test_db):
    """Fase 2 (D34): la memoria nueva vive en MariaDB y en `<base>_catalogo` y `<base>_notas`. Se recrean en
    cada sesión (determinismo) y se indexan las descripciones de los atributos semilla (la BD de test ya los
    trae: migración 011). Ya no hay colección plana `sebastian_memory_test`."""
    from qdrant_client import QdrantClient

    from core.memoria.catalogo import Catalogo
    from core.memoria.embedder import OpenAIEmbedder
    from core.memoria.repositorio import RepositorioMemoria
    from scripts.memoria.crear_colecciones import crear_colecciones, nombres
    from tests.golden.uso import USO

    qdrant_url = config_de_goldens.get("qdrant_url", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)

    # El catálogo se indexa desde la BD: antes de indexar, fuera lo que una sesión anterior dejó de más.
    limpiar_memoria(test_db, GOLDEN_USER_ID, USUARIO_B)
    limpiar_atributos_de_conversacion(test_db)

    for nombre in nombres(TEST_MEMORY_COLLECTION):
        try:
            client.delete_collection(nombre)
        except Exception:
            pass
    crear_colecciones(client, TEST_MEMORY_COLLECTION)
    embedder = OpenAIEmbedder(config_de_goldens["openai_apikey"])
    Catalogo(RepositorioMemoria(test_db), embedder, client, TEST_MEMORY_COLLECTION).indexar_atributos()
    USO.registrar_embeddings(embedder.tokens)

    return {"memory_collection": TEST_MEMORY_COLLECTION}


@pytest.fixture(autouse=True)
def _historial_limpio(request, test_db):
    """H2 (D21): el orquestador guarda cada turno en `conversations`. Sin esto, cada golden vería
    el historial del anterior. Solo actúa en los goldens (marca `golden`)."""
    if request.node.get_closest_marker("golden") is None:
        yield
        return
    cur = test_db.cursor()
    cur.execute("DELETE FROM conversations WHERE user_id IN (%s, %s)", (GOLDEN_USER_ID, USUARIO_B))
    test_db.commit()
    # Fase 2: lo que mark_as_memorable escribió en un golden anterior (hechos, decisiones, entidades de los
    # usuarios de goldens) no puede condicionar al siguiente. Los atributos creados se quedan: son catálogo.
    limpiar_memoria(test_db, GOLDEN_USER_ID, USUARIO_B)
    # H3b: el estado sembrado por un golden no condiciona al siguiente. Del usuario de goldens solo se borra lo sembrado
    # (el «teatro» de `golden_fixtures` es de sesión); la agenda del usuario B (E10) se vacía entera.
    limpiar_sembrado(test_db)
    limpiar_agenda(test_db, USUARIO_B)
    yield
    limpiar_sembrado(test_db)
    limpiar_agenda(test_db, USUARIO_B)
    # Y también al terminar: lo que deja un golden (entidades del usuario de goldens) no puede ver el siguiente
    # `pytest` sin API, cuyas pruebas del catálogo cuentan entidades en toda la BD de test.
    limpiar_memoria(test_db, GOLDEN_USER_ID, USUARIO_B)


@pytest.fixture
def memoria_base(test_db):
    """La memoria de test de los goldens (H3 plan §3 H3.2): «yo» y los tres hechos de siempre, en MariaDB.
    Función, no sesión: `_historial_limpio` vacía la memoria antes de cada golden y esto la vuelve a sembrar."""
    sembrar_memoria_base(test_db, GOLDEN_USER_ID)


def sembrar_historia(db, user_id: str, historia: list) -> None:
    """Inserta la `historia` de un golden en `conversations`, en orden, con created_at de hace
    pocos minutos (el último intercambio, hace 1 min)."""
    ahora = datetime.now()
    cur = db.cursor()
    for i, par in enumerate(historia):
        hace = timedelta(minutes=len(historia) - i)
        cur.execute(
            "INSERT INTO conversations (user_id, user_msg, bot_reply, created_at) VALUES (%s, %s, %s, %s)",
            (user_id, par["user"], par["bot"], (ahora - hace).strftime("%Y-%m-%d %H:%M:%S")),
        )
    db.commit()


def _hacer_runner(test_db, user_id_por_defecto: str, config_por_defecto: dict):
    """Returns a callable run(phrase, historia=None, *, user_id=None, config=None) -> (tool_call_sequence, response).

    Records the tool-call sequence by wrapping ToolExecutor.execute (real dispatch
    still runs — side effects land in sebastian_test / sus colecciones de test) and
    Orchestrator._ask_user (the only path reached when request_clarification is
    chosen, since the Orchestrator intercepts that tool before it ever reaches
    ToolExecutor). `user_id` y `config` permiten a los escenarios cambiar de usuario (E7)
    o de vault (E8) sin tocar el resto.
    """
    from unittest.mock import patch

    from anthropic.resources.messages import Messages
    from openai.resources.embeddings import Embeddings

    from core.orchestrator import Orchestrator
    from core.tool_executor import ToolExecutor
    from modules.compromisos import CompromisosModule
    from tests.golden.uso import USO

    def _run(phrase: str, historia: list | None = None, *, user_id: str | None = None, config: dict | None = None,
             estado: dict | None = None, ahora: str | None = None):
        user_id = user_id or user_id_por_defecto
        if historia:
            sembrar_historia(test_db, user_id, historia)
        if estado:                                        # H3b: los eventos y compromisos que la historia da por hechos
            sembrar_estado(test_db, user_id, estado)
        calls = []
        ventanas = []     # H5: el `time_window` de cada `calendar_list_events`, que es lo que de verdad comprueba R14 (#77, #78)
        creaciones = []   # H7: la entrada de cada `compromisos_crear` (#79, #80)
        original_execute = ToolExecutor.execute
        original_ask_user = Orchestrator._ask_user
        original_track_usage = Orchestrator._track_usage
        original_log_turn_end = Orchestrator._log_turn_end

        def recording_execute(self, tool_name, tool_input):
            calls.append(tool_name)
            if tool_name == "calendar_list_events":
                ventanas.append(str(tool_input.get("time_window")))
            if tool_name == "compromisos_crear":              # H7: #79 y #80 comprueban QUÉ día y hora se creó
                creaciones.append(dict(tool_input))
            return original_execute(self, tool_name, tool_input)

        def recording_ask_user(self, question):
            calls.append("request_clarification")
            return original_ask_user(self, question)

        def midiendo_uso(self, response, model):
            USO.registrar(response, model)
            return original_track_usage(self, response, model)

        def midiendo_latencia(self, turn_start, iterations, outcome):
            # Misma cuenta que la línea «Turn end» de producción (fase 2 H0, D28).
            USO.registrar_latencia(round((time.perf_counter() - turn_start) * 1000, 1))
            return original_log_turn_end(self, turn_start, iterations, outcome)

        original_embeddings_create = Embeddings.create

        def midiendo_embeddings(self, *args, **kwargs):
            # Mide cualquier camino a OpenAI (OpenAIEmbedder del catálogo y de las notas), no solo uno.
            respuesta = original_embeddings_create(self, *args, **kwargs)
            USO.registrar_embeddings(getattr(getattr(respuesta, "usage", None), "total_tokens", 0))
            return respuesta

        # H3c (R10): lo que dice el planner cuando cierra una llamada SIN tool_use (el modo «sin tool» de #50, #67 y E10).
        # Solo se guarda en la respuesta del test, para el informe: nunca va al log (D42).
        original_messages_create = Messages.create
        planner_sin_tools = []

        def capturando_planner(self, *args, **kwargs):
            respuesta = original_messages_create(self, *args, **kwargs)
            try:                                              # informativa: un fallo aquí nunca rompe una ejecución de pago
                if kwargs.get("tools") and not any(getattr(b, "type", None) == "tool_use" for b in respuesta.content):
                    planner_sin_tools.append(
                        " ".join(b.text for b in respuesta.content if getattr(b, "type", None) == "text"))
            except Exception:
                pass
            return respuesta

        with ExitStack() as pila, \
             patch.object(Embeddings, "create", midiendo_embeddings), \
             patch.object(Messages, "create", capturando_planner), \
             patch.object(ToolExecutor, "execute", recording_execute), \
             patch.object(Orchestrator, "_ask_user", recording_ask_user), \
             patch.object(Orchestrator, "_track_usage", midiendo_uso), \
             patch.object(Orchestrator, "_log_turn_end", midiendo_latencia):
            if ahora:
                # H7 (#79, #80): «esta noche a la una» depende de la hora del día. El planner ve esta hora en su prompt y
                # `compromisos_crear` (R19) juzga contra ella: las dos tienen que ser la misma. Solo los goldens que
                # traen `ahora` la fijan; el resto sigue con el reloj real.
                fijo = datetime.fromisoformat(ahora)
                pila.enter_context(patch("core.orchestrator._now_str",
                                         lambda: f"Hoy es {fijo:%Y-%m-%d} y son las {fijo:%H:%M}."))
                pila.enter_context(patch.object(CompromisosModule, "_ahora", lambda self: fijo))
            orch = Orchestrator(test_db, user_id, config=config or config_por_defecto)
            response = orch.handle(phrase)

        if isinstance(response, dict) and planner_sin_tools:
            response["planner_sin_tools"] = planner_sin_tools
        if isinstance(response, dict) and ventanas:
            response["ventanas"] = ventanas
        if isinstance(response, dict) and creaciones:
            response["creaciones"] = creaciones
        return calls, response

    return _run


@pytest.fixture
def orchestrator_runner(test_db, golden_fixtures, config_de_goldens, memory_fixtures, memoria_base):
    """Los goldens de una frase: con la memoria base sembrada (Paco, el vino, Rebe)."""
    return _hacer_runner(test_db, golden_fixtures["user_id"], config_de_goldens)


@pytest.fixture
def escenario_runner(test_db, config_de_goldens, memory_fixtures):
    """Los escenarios con estado (H3 plan §3 H3.4): empiezan con la memoria **vacía** (la autouse
    `_historial_limpio` ya la vació) y sin atributos de conversaciones anteriores. Varios turnos seguidos
    comparten estado: el historial va a `conversations` y los hechos, a MariaDB."""
    limpiar_atributos_de_conversacion(test_db)
    return _hacer_runner(test_db, GOLDEN_USER_ID, config_de_goldens)
