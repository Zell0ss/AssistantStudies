# Pending Plans Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When the Orchestrator needs a missing input it cannot obtain from other tools, it saves its full Haiku loop state to the DB, asks the user, and resumes execution seamlessly on the next message.

**Architecture:** A new `request_clarification` tool is added to ALL_TOOLS. When Haiku calls it, the Orchestrator serializes the full Haiku messages array (including the assistant turn with the call) to a new `pending_plans` table and returns an Alfred-style question. On the next user message, the Orchestrator checks for an open plan, uses a mini Haiku call to decide if the message answers the plan or is a new query, and resumes or discards accordingly. Plans expire after 24h, on `/abort`, and on bot restart.

**Tech Stack:** Anthropic SDK (Haiku + Sonnet), MariaDB (SQLite in tests), pyTelegramBotAPI

---

### Task 1: Migration 008 — pending_plans table

**Files:**
- Create: `db/migrations/008_pending_plans.sql`

**Step 1: Create migration file**

```sql
-- Sebastian 2.0 - Pending orchestrator plans
-- Stores Haiku loop state when a required input is missing

CREATE TABLE IF NOT EXISTS pending_plans (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          VARCHAR(64) NOT NULL,
    original_message TEXT NOT NULL,
    messages_json    LONGTEXT NOT NULL,
    question         TEXT NOT NULL,
    missing_field    VARCHAR(128),
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at       DATETIME NOT NULL,
    UNIQUE KEY uq_user_plan (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Check `db/migrations/007_conversations.sql` for format reference.

**Step 2: Verify**

```bash
cat db/migrations/008_pending_plans.sql
```

**Step 3: Commit**

```bash
git add db/migrations/008_pending_plans.sql
git commit -m "feat: add pending_plans migration (008)"
```

---

### Task 2: clarification_tools.py

**Files:**
- Create: `core/tools/clarification_tools.py`
- Modify: `core/tools/__init__.py`
- Test: `tests/test_tools.py` (create)

**Step 1: Write failing tests**

Create `tests/test_tools.py`:

```python
"""Tests for ALL_TOOLS definitions."""
from core.tools import ALL_TOOLS


def test_request_clarification_in_all_tools():
    names = [t["name"] for t in ALL_TOOLS]
    assert "request_clarification" in names


def test_request_clarification_schema():
    tool = next(t for t in ALL_TOOLS if t["name"] == "request_clarification")
    props = tool["input_schema"]["properties"]
    assert "question" in props
    assert "missing_field" in props
    assert tool["input_schema"]["required"] == ["question", "missing_field"]
```

**Step 2: Run to verify they fail**

```bash
cd sebastian2 && source .venv/bin/activate && pytest tests/test_tools.py -v
```

Expected: FAIL — `request_clarification` not found in ALL_TOOLS.

**Step 3: Create clarification_tools.py**

```python
"""Clarification tool definition for Orchestrator."""

CLARIFICATION_TOOLS = [
    {
        "name": "request_clarification",
        "description": (
            "Llama a esta herramienta cuando necesitas un dato del usuario para completar "
            "la tarea y ese dato no está en el mensaje original ni puede obtenerse de otras "
            "herramientas. Úsala como último recurso — primero intenta inferir el dato "
            "(ej: ciudad del usuario por su configuración de tiempo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Pregunta concisa al usuario. Ej: '¿En qué ciudad tienes pilates?'"
                },
                "missing_field": {
                    "type": "string",
                    "description": "Nombre del dato que falta. Ej: 'city', 'date', 'event_name'."
                }
            },
            "required": ["question", "missing_field"]
        }
    }
]
```

**Step 4: Add to `core/tools/__init__.py`**

```python
from .clarification_tools import CLARIFICATION_TOOLS

ALL_TOOLS = (
    CALENDAR_TOOLS +
    WEATHER_TOOLS +
    INVENTORY_TOOLS +
    LIST_TOOLS +
    NOTES_TOOLS +
    CLARIFICATION_TOOLS
)
```

**Step 5: Run tests**

```bash
pytest tests/test_tools.py -v
```

Expected: 2 PASS.

**Step 6: Commit**

```bash
git add core/tools/clarification_tools.py core/tools/__init__.py tests/test_tools.py
git commit -m "feat: add request_clarification tool"
```

---

### Task 3: PendingPlanRepository

**Files:**
- Create: `db/pending_plan_repo.py`
- Test: `tests/test_pending_plan_repo.py`

**Step 1: Write failing tests**

Create `tests/test_pending_plan_repo.py`:

```python
"""Tests for PendingPlanRepository."""
import json
import sqlite3
from datetime import datetime, timedelta
import pytest
from tests.test_item_list_module import MySQLCompatibleConnection
from db.pending_plan_repo import PendingPlanRepository

_SCHEMA = '''
    CREATE TABLE pending_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL UNIQUE,
        original_message TEXT NOT NULL,
        messages_json TEXT NOT NULL,
        question TEXT NOT NULL,
        missing_field TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL
    )
'''


@pytest.fixture
def db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    yield MySQLCompatibleConnection(conn)


def _save(repo, user_id="u1", msg="¿paraguas?", messages=None, question="¿ciudad?", field="city"):
    messages_json = json.dumps(messages or [{"role": "user", "content": msg}])
    repo.save(user_id, msg, messages_json, question, field)


def test_save_and_get_active(db):
    repo = PendingPlanRepository(db)
    _save(repo)
    plan = repo.get_active("u1")
    assert plan is not None
    assert plan["question"] == "¿ciudad?"
    assert plan["missing_field"] == "city"
    assert json.loads(plan["messages_json"]) == [{"role": "user", "content": "¿paraguas?"}]


def test_get_active_returns_none_when_no_plan(db):
    repo = PendingPlanRepository(db)
    assert repo.get_active("u1") is None


def test_get_active_ignores_expired(db):
    repo = PendingPlanRepository(db)
    past = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    db._conn.execute(
        "INSERT INTO pending_plans (user_id, original_message, messages_json, question, expires_at)"
        " VALUES (?,?,?,?,?)",
        ("u1", "test", "[]", "?", past)
    )
    db._conn.commit()
    assert repo.get_active("u1") is None


def test_save_overwrites_existing_plan(db):
    repo = PendingPlanRepository(db)
    _save(repo, question="¿ciudad?")
    _save(repo, question="¿fecha?", field="date")
    plan = repo.get_active("u1")
    assert plan["question"] == "¿fecha?"
    assert plan["missing_field"] == "date"


def test_delete_returns_true_when_deleted(db):
    repo = PendingPlanRepository(db)
    _save(repo)
    assert repo.delete("u1") is True
    assert repo.get_active("u1") is None


def test_delete_returns_false_when_no_plan(db):
    repo = PendingPlanRepository(db)
    assert repo.delete("u1") is False


def test_delete_all(db):
    repo = PendingPlanRepository(db)
    _save(repo, user_id="u1")
    _save(repo, user_id="u2")
    count = repo.delete_all()
    assert count == 2
    assert repo.get_active("u1") is None
    assert repo.get_active("u2") is None
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_pending_plan_repo.py -v
```

Expected: FAIL — module not found.

**Step 3: Implement PendingPlanRepository**

Create `db/pending_plan_repo.py`:

```python
"""Repository for pending orchestrator plans."""
from datetime import datetime, timedelta
from loguru import logger

_TTL_HOURS = 24


class PendingPlanRepository:
    """Stores and retrieves pending Haiku loop state per user."""

    def __init__(self, db):
        self._db = db

    def save(self, user_id: str, original_message: str, messages_json: str,
             question: str, missing_field: str | None = None) -> None:
        """Insert or replace the open plan for this user."""
        expires_at = (datetime.now() + timedelta(hours=_TTL_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
        cur = self._db.cursor()
        cur.execute(
            """
            INSERT INTO pending_plans
                (user_id, original_message, messages_json, question, missing_field, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE
                original_message = VALUES(original_message),
                messages_json    = VALUES(messages_json),
                question         = VALUES(question),
                missing_field    = VALUES(missing_field),
                expires_at       = VALUES(expires_at)
            """,
            (user_id, original_message, messages_json, question, missing_field, expires_at)
        )
        self._db.commit()
        logger.debug(f"Saved pending plan for user {user_id!r}: {question!r}")

    def get_active(self, user_id: str) -> dict | None:
        """Return the active (non-expired) plan for user, or None."""
        cur = self._db.cursor()
        cur.execute(
            "SELECT * FROM pending_plans WHERE user_id = ? AND expires_at > ?",
            (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def delete(self, user_id: str) -> bool:
        """Delete the plan for user. Returns True if a row was deleted."""
        cur = self._db.cursor()
        cur.execute("DELETE FROM pending_plans WHERE user_id = ?", (user_id,))
        self._db.commit()
        deleted = cur.rowcount > 0
        if deleted:
            logger.debug(f"Deleted pending plan for user {user_id!r}")
        return deleted

    def delete_all(self) -> int:
        """Delete all plans (used at bot startup). Returns count deleted."""
        cur = self._db.cursor()
        cur.execute("DELETE FROM pending_plans")
        self._db.commit()
        count = cur.rowcount
        logger.info(f"Cleared {count} pending plans on startup")
        return count
```

**Note on SQLite tests:** `MySQLCompatibleConnection` wraps SQLite which doesn't support `ON DUPLICATE KEY UPDATE`. The `UNIQUE KEY` on `user_id` means the INSERT fails on duplicate. The test for overwrite (`test_save_overwrites_existing_plan`) may need the repo to use `INSERT OR REPLACE` syntax for SQLite compatibility, OR the test fixture can use a custom subclass. Check how other modules handle this — follow the existing pattern in the project.

If `MySQLCompatibleConnection` doesn't translate `ON DUPLICATE KEY UPDATE`, change the `save()` implementation to do a `DELETE` then `INSERT` (works in both engines):

```python
def save(self, user_id, original_message, messages_json, question, missing_field=None):
    expires_at = (datetime.now() + timedelta(hours=_TTL_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
    cur = self._db.cursor()
    cur.execute("DELETE FROM pending_plans WHERE user_id = ?", (user_id,))
    cur.execute(
        "INSERT INTO pending_plans (user_id, original_message, messages_json, question, missing_field, expires_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, original_message, messages_json, question, missing_field, expires_at)
    )
    self._db.commit()
    logger.debug(f"Saved pending plan for user {user_id!r}: {question!r}")
```

**Step 4: Run tests**

```bash
pytest tests/test_pending_plan_repo.py -v
```

Expected: 7 PASS.

**Step 5: Commit**

```bash
git add db/pending_plan_repo.py tests/test_pending_plan_repo.py
git commit -m "feat: add PendingPlanRepository"
```

---

### Task 4: Orchestrator — serialization helpers + _ask_user()

**Files:**
- Modify: `core/orchestrator.py`
- Test: `tests/test_orchestrator.py`

These helpers are needed because Anthropic SDK response objects (content blocks) can't be JSON-serialized directly. They must be converted to dicts before storing in the DB.

**Step 1: Write failing tests**

Add to `tests/test_orchestrator.py`:

```python
from core.orchestrator import _messages_to_json, _messages_from_json


def test_messages_roundtrip_plain_string():
    messages = [{"role": "user", "content": "Hola"}]
    assert _messages_from_json(_messages_to_json(messages)) == messages


def test_messages_roundtrip_dict_content():
    messages = [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": [{"type": "text", "text": "Señor"}]},
    ]
    result = _messages_from_json(_messages_to_json(messages))
    assert result[1]["content"][0]["text"] == "Señor"


def test_messages_to_json_handles_sdk_objects():
    """SDK objects with model_dump() are serialized as dicts."""
    sdk_obj = MagicMock()
    sdk_obj.model_dump.return_value = {"type": "text", "text": "hi"}
    messages = [{"role": "assistant", "content": [sdk_obj]}]
    result = _messages_from_json(_messages_to_json(messages))
    assert result[0]["content"][0]["type"] == "text"
    assert result[0]["content"][0]["text"] == "hi"
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_orchestrator.py::test_messages_roundtrip_plain_string -v
```

Expected: FAIL — `_messages_to_json` not importable.

**Step 3: Add helpers and _ask_user() to orchestrator.py**

Add at module level (above the `Orchestrator` class):

```python
def _messages_to_json(messages: list) -> str:
    """Serialize Haiku messages to JSON. Converts SDK objects via model_dump()."""
    serializable = []
    for msg in messages:
        content = msg["content"]
        if isinstance(content, list):
            content = [
                block.model_dump() if hasattr(block, 'model_dump') else block
                for block in content
            ]
        serializable.append({"role": msg["role"], "content": content})
    return json.dumps(serializable, ensure_ascii=False)


def _messages_from_json(json_str: str) -> list:
    """Deserialize messages JSON. Anthropic API accepts plain dicts."""
    return json.loads(json_str)
```

Add to `Orchestrator` class:

```python
def _ask_user(self, question: str) -> str:
    """Have Alfred ask the user for clarification in his characteristic style."""
    response = self._client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        system=_ALFRED_SYSTEM,
        messages=[{"role": "user", "content": f"Necesito preguntarle esto al usuario: {question}"}]
    )
    return response.content[0].text.strip()
```

**Step 4: Run tests**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: all existing tests still pass + 3 new PASS.

**Step 5: Commit**

```bash
git add core/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add message serialization helpers and _ask_user to Orchestrator"
```

---

### Task 5: Orchestrator — detect request_clarification, save plan

**Files:**
- Modify: `core/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write failing test**

Add to `tests/test_orchestrator.py`:

```python
@patch('core.orchestrator.Anthropic')
@patch('core.orchestrator.PendingPlanRepository')
def test_request_clarification_saves_plan_and_asks_user(mock_repo_cls, mock_anthropic_cls, db):
    """When Haiku calls request_clarification, plan is saved and Alfred asks the question."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_active.return_value = None  # no existing plan

    # Haiku calls request_clarification; Alfred reformulates the question
    mock_client.messages.create.side_effect = [
        _make_tool_use_response(
            'request_clarification', 'rc_1',
            {'question': '¿En qué ciudad?', 'missing_field': 'city'}
        ),
        _make_text_response('¿En qué ciudad tiene usted pilates, señor?'),
    ]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    result = orch.handle("¿paraguas a pilates?")

    # Plan was saved
    mock_repo.save.assert_called_once()
    args = mock_repo.save.call_args[0]
    assert args[0] == '99999'                   # user_id
    assert args[1] == '¿paraguas a pilates?'    # original_message
    # args[2] is messages_json (str)
    assert args[3] == '¿En qué ciudad?'         # question
    assert args[4] == 'city'                    # missing_field

    # Result is the Alfred-style question
    assert isinstance(result, str)
    assert len(result) > 0
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_orchestrator.py::test_request_clarification_saves_plan_and_asks_user -v
```

Expected: FAIL.

**Step 3: Modify Orchestrator**

Add import at top of `orchestrator.py`:

```python
from db.pending_plan_repo import PendingPlanRepository
```

In `Orchestrator.__init__()`, add after `self._executor`:

```python
self._repo = PendingPlanRepository(db)
```

In `Orchestrator.handle()`, inside `for block in tool_blocks`, add BEFORE the existing `try` block:

```python
if block.name == "request_clarification":
    # Save loop state including the assistant turn that made the call
    messages_to_save = messages + [{"role": "assistant", "content": response.content}]
    self._repo.save(
        self._user_id,
        user_message,
        _messages_to_json(messages_to_save),
        block.input["question"],
        block.input.get("missing_field"),
    )
    return self._ask_user(block.input["question"])
```

This must be the first check inside the `for block in tool_blocks` loop, before `try:`.

**Step 4: Run tests**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: all PASS.

**Step 5: Commit**

```bash
git add core/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: detect request_clarification in Orchestrator, save plan"
```

---

### Task 6: Orchestrator — check and resume pending plan

**Files:**
- Modify: `core/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write failing tests**

Add to `tests/test_orchestrator.py`:

```python
@patch('core.orchestrator.Anthropic')
@patch('core.orchestrator.PendingPlanRepository')
def test_plan_resumed_when_user_answers(mock_repo_cls, mock_anthropic_cls, db):
    """When there is an open plan and user answers it, loop resumes from saved state."""
    import json as _json
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo

    saved_messages = [
        {"role": "user", "content": "¿paraguas a pilates?"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "rc_1", "name": "request_clarification",
             "input": {"question": "¿En qué ciudad?", "missing_field": "city"}}
        ]}
    ]
    mock_repo.get_active.return_value = {
        "original_message": "¿paraguas a pilates?",
        "messages_json": _json.dumps(saved_messages),
        "question": "¿En qué ciudad?",
        "missing_field": "city",
    }

    # is_plan_reply → "SI", then Haiku runs weather tool, then synthesizes
    mock_client.messages.create.side_effect = [
        _make_text_response("SI"),                                          # is_plan_reply check
        _make_tool_use_response('weather_get', 'w1', {'city': 'Madrid'}),   # Haiku resumes
        _make_text_response("Tengo el tiempo"),                             # Haiku done
        _make_text_response("Lleve paraguas, señor."),                      # Alfred
    ]

    with patch('core.tool_executor.ToolExecutor.execute', return_value={'rain': 80}):
        from core.orchestrator import Orchestrator
        orch = Orchestrator(db, '99999')
        result = orch.handle("Madrid")

    mock_repo.delete.assert_called_once_with('99999')
    assert isinstance(result, str)


@patch('core.orchestrator.Anthropic')
@patch('core.orchestrator.PendingPlanRepository')
def test_plan_discarded_on_new_query(mock_repo_cls, mock_anthropic_cls, db):
    """When Haiku decides the message is a new query, the plan is deleted and fresh flow runs."""
    import json as _json
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo

    mock_repo.get_active.return_value = {
        "original_message": "¿paraguas a pilates?",
        "messages_json": _json.dumps([{"role": "user", "content": "¿paraguas?"}]),
        "question": "¿En qué ciudad?",
        "missing_field": "city",
    }

    mock_client.messages.create.side_effect = [
        _make_text_response("NO"),                      # is_plan_reply check
        _make_text_response("No se necesitan tools"),   # fresh Haiku
        _make_text_response("Buenos días, señor."),     # Alfred
    ]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    result = orch.handle("qué tiempo hace en Sevilla")

    mock_repo.delete.assert_called_once_with('99999')
    assert isinstance(result, str)
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_orchestrator.py::test_plan_resumed_when_user_answers -v
```

Expected: FAIL.

**Step 3: Add _is_plan_reply() to Orchestrator**

```python
def _is_plan_reply(self, user_message: str, plan_question: str) -> bool:
    """Ask Haiku whether the user message answers the pending plan question."""
    response = self._client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system="Responde solo 'SI' o 'NO', sin más texto.",
        messages=[{"role": "user", "content": (
            f"Pregunta pendiente: '{plan_question}'.\n"
            f"Mensaje del usuario: '{user_message}'.\n"
            f"¿Es el mensaje una respuesta directa a la pregunta pendiente?"
        )}]
    )
    return response.content[0].text.strip().upper().startswith('S')
```

**Step 4: Add plan check at start of handle()**

At the very beginning of `Orchestrator.handle()`, before `messages = [...]`:

```python
# ── Pending plan check ────────────────────────────────────────────────────
plan = self._repo.get_active(self._user_id)
if plan:
    if self._is_plan_reply(user_message, plan["question"]):
        return self._resume_plan(plan, user_message)
    else:
        self._repo.delete(self._user_id)
        # Fall through to normal handling
# ─────────────────────────────────────────────────────────────────────────
```

**Step 5: Add _resume_plan() to Orchestrator**

```python
def _resume_plan(self, plan: dict, user_answer: str) -> str:
    """Resume a pending plan by injecting the user's answer as a tool_result."""
    messages = _messages_from_json(plan["messages_json"])
    original_message = plan["original_message"]

    # Find the request_clarification tool_use_id from the last assistant message
    last_content = messages[-1]["content"]
    rc_block = next(
        b for b in last_content
        if isinstance(b, dict)
        and b.get("type") == "tool_use"
        and b.get("name") == "request_clarification"
    )

    # Inject user's answer as the tool_result for that call
    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": rc_block["id"],
            "content": user_answer
        }]
    })

    # Resume the tool loop
    tool_results_summary = []
    for iteration in range(_MAX_ITERATIONS):
        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_planner_system(),
            tools=ALL_TOOLS,
            messages=messages
        )

        tool_blocks = [b for b in response.content if b.type == 'tool_use']

        if response.stop_reason == 'end_turn' or not tool_blocks:
            break

        # Check if Haiku needs yet another clarification
        rc = next((b for b in tool_blocks if b.name == 'request_clarification'), None)
        if rc:
            messages_to_save = messages + [{"role": "assistant", "content": response.content}]
            self._repo.save(
                self._user_id,
                original_message,
                _messages_to_json(messages_to_save),
                rc.input["question"],
                rc.input.get("missing_field"),
            )
            return self._ask_user(rc.input["question"])

        # Execute tools normally
        tool_results = []
        had_error = False
        for block in tool_blocks:
            try:
                logger.debug(
                    f"Calling tool {block.name} | input: "
                    f"{json.dumps(block.input, ensure_ascii=False)}"
                )
                raw = self._executor.execute(block.name, block.input)
                result_content = json.dumps(raw, default=str, ensure_ascii=False)
                tool_results_summary.append({"tool": block.name, "input": block.input, "result": raw})
                logger.info(f"Tool {block.name} → {result_content[:200]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_content
                })
            except Exception as e:
                logger.error(f"Tool {block.name} failed: {e}")
                had_error = True
                break

        if had_error:
            break

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    self._repo.delete(self._user_id)
    return self._synthesize(original_message, tool_results_summary)
```

**Step 6: Run tests**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: all PASS.

**Step 7: Commit**

```bash
git add core/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: resume pending plan in Orchestrator"
```

---

### Task 7: /abort command in bot handler

**Files:**
- Modify: `bot/handlers.py`

**Step 1: Add /abort handler inside setup_handlers()**

Following the pattern of existing command handlers in `bot/handlers.py`:

```python
@bot.message_handler(commands=['abort'])
def handle_abort(message):
    if not authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, "No estás autorizado.")
        return
    try:
        conn = get_connection()
        from db.pending_plan_repo import PendingPlanRepository
        repo = PendingPlanRepository(conn)
        deleted = repo.delete(str(message.chat.id))
        if deleted:
            bot.reply_to(message, "Plan cancelado, señor.")
        else:
            bot.reply_to(message, "No hay ningún plan pendiente.")
    except Exception as e:
        logger.error(f"/abort failed: {e}")
        bot.reply_to(message, "Error al cancelar el plan.")
```

Place this handler BEFORE the catch-all `handle_text` handler (handlers are matched in order).

**Step 2: Verify manually** (no automated test needed for this handler — it follows the exact same pattern as all others already tested)

```bash
grep -n "abort" bot/handlers.py
```

Expected: handler visible in file.

**Step 3: Commit**

```bash
git add bot/handlers.py
git commit -m "feat: add /abort command to cancel pending plan"
```

---

### Task 8: Bot startup cleanup

**Files:**
- Modify: `sebastian_bot.py`

**Step 1: Add cleanup call at startup**

In `sebastian_bot.py`, find the section just before `bot.infinity_polling()`. Add:

```python
# Clear all pending plans on startup (plans are session-scoped)
try:
    from db.connection import get_connection
    from db.pending_plan_repo import PendingPlanRepository
    PendingPlanRepository(get_connection()).delete_all()
except Exception as e:
    logger.warning(f"Could not clear pending plans on startup: {e}")
```

**Step 2: Verify**

```bash
grep -n "delete_all\|pending_plans" sebastian_bot.py
```

**Step 3: Commit**

```bash
git add sebastian_bot.py
git commit -m "feat: clear pending plans on bot startup"
```

---

### Task 9: Run full test suite

**Step 1: Run all tests**

```bash
cd sebastian2 && source .venv/bin/activate && pytest tests/ -v 2>&1 | tail -30
```

Expected: All new tests pass. Pre-existing failures (item_list/handlers/integration, ~15) unchanged.

**Step 2: Update MEMORY.md**

Update the "Current state" section in `memory/MEMORY.md`:
- Add pending plans feature ✅
- Update test count

**Step 3: Final commit if anything straggling**

```bash
git status
```
