"""Golden regression harness — fixtures.

CRITICAL SAFETY GUARDRAIL: this harness performs real writes/deletes (golden #3
deletes notes) and must NEVER touch sebastian_db (production). The `test_db`
fixture asserts the connected schema is exactly TEST_DB_NAME before yielding a
connection to anything — if that assertion fails, the whole session aborts
immediately. This is a hard assert, not a naming convention.

Same guardrail extends to memory (Sprint 3): golden #20 writes a real point via
mark_as_memorable, so `memory_config` refuses to run unless the isolated
TEST_MEMORY_COLLECTION collection actually exists in Qdrant, and never resolves
to the real 'sebastian_memory' collection.
"""
from datetime import date, timedelta

import pymysql
import pytest

from utils.config import get_config

TEST_DB_NAME = "sebastian_test"
TEST_MEMORY_COLLECTION = "sebastian_memory_test"
GOLDEN_USER_ID = "golden_test_user"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "golden: end-to-end orchestrator regression tests (real Anthropic API calls, real sebastian_test DB)",
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print the golden → expected → actual → PASS/FAIL report + X/14 summary."""
    try:
        from tests.golden.test_goldens import GOLDEN_RESULTS
    except ImportError:
        return
    if not GOLDEN_RESULTS:
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

    passed_count = sum(1 for r in GOLDEN_RESULTS if r["passed"])
    total = len(GOLDEN_RESULTS)
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
def memory_config():
    """Config dict pointing memory tools at the ISOLATED sebastian_memory_test collection.
    Hard-aborts if that collection isn't reachable — golden #20 writes a real point via
    mark_as_memorable, and this guardrail exists to keep that off 'sebastian_memory'."""
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
        client.get_collection(TEST_MEMORY_COLLECTION)
    except Exception:
        pytest.exit(
            f"REFUSING TO RUN GOLDEN HARNESS: Qdrant collection '{TEST_MEMORY_COLLECTION}' "
            "not found (create it before running — see SPRINT3-MEMORIA.md Phase 3). This "
            "guardrail exists because golden #20 writes real points and must never silently "
            "fall back to the real 'sebastian_memory' collection.",
            returncode=1,
        )

    base_config["memory_collection"] = TEST_MEMORY_COLLECTION
    return base_config


@pytest.fixture(scope="session")
def memory_fixtures(memory_config):
    """Seed deterministic memories in the isolated test collection. Session-scoped: wipes
    and recreates sebastian_memory_test at the start of each session for determinism."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    from modules.memory import MemoryModule

    qdrant_url = memory_config.get("qdrant_url", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)
    client.delete_collection(TEST_MEMORY_COLLECTION)
    client.create_collection(
        TEST_MEMORY_COLLECTION,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        on_disk_payload=True,
    )

    mem = MemoryModule(
        collection_name=TEST_MEMORY_COLLECTION,
        openai_api_key=memory_config["openai_apikey"],
        qdrant_url=qdrant_url,
    )
    mem.store("Mi cuñado Paco es alérgico a los frutos secos", tags=["familia", "salud"])
    mem.store("A mi señor le gusta el vino tinto de Ribera del Duero", tags=["preferencias"])
    mem.store("El cumpleaños de Rebe es en marzo", tags=["familia", "fechas"])

    return {"memory_collection": TEST_MEMORY_COLLECTION}


@pytest.fixture
def orchestrator_runner(test_db, golden_fixtures, memory_config, memory_fixtures):
    """Returns a callable run(phrase) -> (tool_call_sequence, response_dict).

    Records the tool-call sequence by wrapping ToolExecutor.execute (real dispatch
    still runs — side effects land in sebastian_test / sebastian_memory_test) and
    Orchestrator._ask_user (the only path reached when request_clarification is
    chosen, since the Orchestrator intercepts that tool before it ever reaches
    ToolExecutor).
    """
    from unittest.mock import patch

    from core.orchestrator import Orchestrator
    from core.tool_executor import ToolExecutor

    def _run(phrase: str):
        calls = []
        original_execute = ToolExecutor.execute
        original_ask_user = Orchestrator._ask_user

        def recording_execute(self, tool_name, tool_input):
            calls.append(tool_name)
            return original_execute(self, tool_name, tool_input)

        def recording_ask_user(self, question):
            calls.append("request_clarification")
            return original_ask_user(self, question)

        with patch.object(ToolExecutor, "execute", recording_execute), \
             patch.object(Orchestrator, "_ask_user", recording_ask_user):
            orch = Orchestrator(test_db, golden_fixtures["user_id"], config=memory_config)
            response = orch.handle(phrase)

        return calls, response

    return _run
