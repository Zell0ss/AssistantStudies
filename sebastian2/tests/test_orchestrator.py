"""Tests for Orchestrator — tool use loop."""
import json
import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from tests.test_item_list_module import MySQLCompatibleConnection
from core.orchestrator import _messages_to_json, _messages_from_json, _planner_system, _ALFRED_SYSTEM
from core.tools import build_capabilities_digest


def test_planner_system_includes_capabilities_digest():
    assert build_capabilities_digest() in _planner_system()


def test_alfred_system_includes_capabilities_digest():
    assert build_capabilities_digest() in _ALFRED_SYSTEM


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


@pytest.fixture(autouse=True)
def _sin_indice_de_memoria():
    """Estos tests usan SQLite sin tablas `mem_*`: sin esto el índice (D36) fallaría y dejaría un `warning`
    que enmascararía los de los tests de historial. Los tests del índice lo sobrescriben con su `patch`."""
    with patch('core.orchestrator.indice_memoria', return_value=""):
        yield


@pytest.fixture
def db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE user_settings (
            user_id TEXT PRIMARY KEY,
            sprite_skin TEXT DEFAULT 'default',
            weather_location TEXT DEFAULT 'Madrid',
            weather_lat REAL DEFAULT 40.4168,
            weather_lon REAL DEFAULT -3.7038,
            weather_country TEXT DEFAULT 'ES'
        );
        INSERT INTO user_settings VALUES
            ('99999','default','Madrid',40.4168,-3.7038,'ES');
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_msg TEXT NOT NULL,
            bot_reply TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS pending_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            original_message TEXT NOT NULL,
            messages_json TEXT NOT NULL,
            question TEXT NOT NULL,
            missing_field TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL
        );
    ''')
    conn.commit()
    yield MySQLCompatibleConnection(conn)


def _make_text_response(text):
    """Minimal mock Anthropic response with just text (stop_reason=end_turn)."""
    msg = MagicMock()
    msg.stop_reason = 'end_turn'
    content_block = MagicMock()
    content_block.type = 'text'
    content_block.text = text
    msg.content = [content_block]
    return msg


def _make_tool_use_response(tool_name, tool_id, tool_input):
    """Mock Anthropic response requesting a single tool call."""
    msg = MagicMock()
    msg.stop_reason = 'tool_use'
    content_block = MagicMock()
    content_block.type = 'tool_use'
    content_block.name = tool_name
    content_block.id = tool_id
    content_block.input = tool_input
    content_block.model_dump.return_value = {
        'type': 'tool_use',
        'id': tool_id,
        'name': tool_name,
        'input': tool_input,
    }
    msg.content = [content_block]
    return msg


@patch('core.orchestrator.Anthropic')
@patch('core.orchestrator.ToolExecutor')
def test_accepts_config_override_and_passes_to_tool_executor(mock_tool_executor_cls, mock_anthropic_cls, db):
    """Orchestrator accepts an optional config override, passed through to ToolExecutor
    (needed by the golden harness to point memory tools at an isolated Qdrant collection)."""
    from core.orchestrator import Orchestrator
    fake_config = {'anthropic_apikey': 'sk-fake', 'memory_collection': 'sebastian_memory_test'}
    orch = Orchestrator(db, '99999', config=fake_config)
    # Fase 2 (D31): ademas, el ejecutor recibe un `on_usage` que lleva el uso del extractor de memoria a
    # `_track_usage` (telemetria del turno).
    mock_tool_executor_cls.assert_called_once()
    args, kwargs = mock_tool_executor_cls.call_args
    assert args == (db, '99999') and kwargs['config'] == fake_config
    kwargs['on_usage'](MagicMock(usage=MagicMock(input_tokens=5, output_tokens=2)), 'claude-haiku-4-5-20251001')
    assert orch._turn_usage['tokens_in'] == 5 and 'claude-haiku-4-5-20251001' in orch._turn_usage['models']


@patch('core.orchestrator.Anthropic')
def test_simple_no_tools_returns_synthesis(mock_anthropic_cls, db):
    """When Haiku returns text without tool_use, Alfred synthesizes the response."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # Planner: text only (no tools), then synthesizer
    mock_client.messages.create.side_effect = [
        _make_text_response("No se necesitan herramientas"),
        _make_text_response("Buenos días, señor."),
    ]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    result = orch.handle("Hola")

    assert isinstance(result, dict)
    assert len(result["text"]) > 0
    assert result["images"] == []


@patch('core.orchestrator.Anthropic')
@patch('core.tool_executor.ToolExecutor.execute')
@patch('core.orchestrator.logger')
def test_tool_steps_are_logged(mock_logger, mock_execute, mock_anthropic_cls, db):
    """Calling a tool logs its input at DEBUG and a name/status/latency summary at INFO."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_execute.return_value = [{'event_id': 42, 'title': 'Teatro'}]
    mock_client.messages.create.side_effect = [
        _make_tool_use_response('calendar_search_events', 'tool_1', {'query': 'teatro'}),
        _make_text_response("Tengo toda la info"),
        _make_text_response("El teatro es el miércoles."),
    ]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    orch.handle("¿cuándo es el teatro?")

    all_debug_calls = [str(c) for c in mock_logger.debug.call_args_list]
    # INFO calls for tool steps go through logger.bind(tool=..., latency_ms=...).info(...)
    bound_info_calls = [str(c) for c in mock_logger.bind.return_value.info.call_args_list]
    assert any("calendar_search_events" in c and "input=" in c for c in all_debug_calls)
    assert any("calendar_search_events" in c and "→" in c for c in bound_info_calls)


@patch('core.orchestrator.Anthropic')
@patch('core.tool_executor.ToolExecutor.execute')
def test_single_tool_call_then_synthesis(mock_execute, mock_anthropic_cls, db):
    """Tool use block triggers executor, result feeds back, Sonnet synthesizes."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_execute.return_value = [
        {'event_id': 42, 'title': 'Teatro', 'date': '2026-03-05', 'time': '19:30'}
    ]

    mock_client.messages.create.side_effect = [
        _make_tool_use_response('calendar_search_events', 'tool_1', {'query': 'teatro'}),
        _make_text_response("Tengo toda la info"),
        _make_text_response("El teatro es el miércoles a las 19:30, señor."),
    ]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    result = orch.handle("¿cuándo es el teatro?")

    mock_execute.assert_called_once_with('calendar_search_events', {'query': 'teatro'})
    assert isinstance(result, dict)
    assert len(result["text"]) > 0
    assert result["images"] == []


@patch('core.orchestrator.Anthropic')
def test_max_iterations_stops_loop(mock_anthropic_cls, db):
    """Loop stops after MAX_ITERATIONS even if model keeps requesting tools."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    tool_response = _make_tool_use_response('inventory_list', 'tool_1', {})
    final_text = _make_text_response("Listo, señor.")
    # 8 tool_use responses + 1 synthesizer = 9 total create() calls
    mock_client.messages.create.side_effect = [tool_response] * 8 + [final_text]

    with patch('core.tool_executor.ToolExecutor.execute', return_value=[]):
        from core.orchestrator import Orchestrator
        orch = Orchestrator(db, '99999')
        result = orch.handle("infinite loop test")

    assert isinstance(result, dict)
    assert result["images"] == []


@patch('core.orchestrator.Anthropic')
def test_tool_executor_error_handled_gracefully(mock_anthropic_cls, db):
    """If tool execution fails, error is noted and synthesis still happens."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_client.messages.create.side_effect = [
        _make_tool_use_response('calendar_search_events', 'tool_1', {'query': 'x'}),
        _make_text_response("Lo siento señor."),
    ]

    with patch('core.tool_executor.ToolExecutor.execute', side_effect=Exception("DB down")):
        from core.orchestrator import Orchestrator
        orch = Orchestrator(db, '99999')
        result = orch.handle("busca algo")

    assert isinstance(result, dict)


class TestOrchestratorEndToEnd:
    """Full compound-query flow with mocked Anthropic API and mocked module calls."""

    @pytest.fixture
    def db(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.executescript('''
            CREATE TABLE user_settings (
                user_id TEXT PRIMARY KEY,
                sprite_skin TEXT DEFAULT 'default',
                weather_location TEXT DEFAULT 'Madrid',
                weather_lat REAL DEFAULT 40.4168,
                weather_lon REAL DEFAULT -3.7038,
                weather_country TEXT DEFAULT 'ES'
            );
            INSERT INTO user_settings VALUES
                ('99999','default','Madrid',40.4168,-3.7038,'ES');
            CREATE TABLE IF NOT EXISTS pending_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                original_message TEXT NOT NULL,
                messages_json TEXT NOT NULL,
                question TEXT NOT NULL,
                missing_field TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL
            );
        ''')
        conn.commit()
        yield MySQLCompatibleConnection(conn)

    @patch('core.orchestrator.Anthropic')
    @patch('core.tool_executor.ToolExecutor.execute')
    def test_paraguas_al_teatro_flow(self, mock_execute, mock_anthropic_cls, db):
        """
        Full compound query: search calendar for 'teatro', get weather for that date.
        Verifies Orchestrator calls both tools and synthesizes using the data.
        """
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        def execute_side_effect(tool_name, tool_input):
            if tool_name == 'calendar_search_events':
                return [{'event_id': 42, 'title': 'Teatro Jovellanos',
                         'date': '2026-03-05', 'time': '19:30', 'all_day': False}]
            if tool_name == 'weather_forecast_for_date':
                return {'dates': ['2026-03-05'], 'precip_prob': [75],
                        'temp_max': [14.0], 'temp_min': [9.0], 'windgusts': [40.0]}
            return []

        mock_execute.side_effect = execute_side_effect

        # Haiku: requests calendar search, then weather, then done
        mock_client.messages.create.side_effect = [
            _make_tool_use_response('calendar_search_events', 't1', {'query': 'teatro'}),
            _make_tool_use_response('weather_forecast_for_date', 't2', {'date': '2026-03-05'}),
            _make_text_response('Tengo la información necesaria.'),
            # Synthesizer (Sonnet)
            _make_text_response(
                'Sí señor. El Teatro Jovellanos es el miércoles a las 19:30. '
                'Hay un 75% de probabilidad de lluvia. ☂️ Lleve paraguas.'
            ),
        ]

        from core.orchestrator import Orchestrator
        orch = Orchestrator(db, '99999')
        result = orch.handle("¿necesito llevar paraguas al teatro?")

        # Both tools were called
        called_tools = [c[0][0] for c in mock_execute.call_args_list]
        assert 'calendar_search_events' in called_tools
        assert 'weather_forecast_for_date' in called_tools

        # calendar_search_events was called with 'teatro'
        calendar_call = next(c for c in mock_execute.call_args_list
                             if c[0][0] == 'calendar_search_events')
        assert calendar_call[0][1] == {'query': 'teatro'}

        # weather_forecast_for_date was called with the date from the calendar result
        weather_call = next(c for c in mock_execute.call_args_list
                            if c[0][0] == 'weather_forecast_for_date')
        assert weather_call[0][1] == {'date': '2026-03-05'}

        # Final response is a dict with text and no ticket images
        assert isinstance(result, dict)
        assert len(result["text"]) > 10
        assert result["images"] == []


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
    assert isinstance(result, dict)
    assert len(result["text"]) > 0


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
    assert isinstance(result, dict)
    assert len(result["text"]) > 0


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

    # Result is a dict — text is the Alfred-style question, no images
    assert isinstance(result, dict)
    assert len(result["text"]) > 0
    assert result["images"] == []


# ── Fase 1 H2: historial entre turnos (D21–D24) ──────────────────────────────────────────────

def _sembrar(db, pares, user_id='99999'):
    from db.conversation_repo import ConversationRepository
    repo = ConversationRepository(db)
    for u, b in pares:
        repo.guardar(user_id, u, b)


def _filas_conversations(db, user_id='99999'):
    cur = db.cursor()
    cur.execute("SELECT user_msg, bot_reply FROM conversations WHERE user_id = %s ORDER BY id", (user_id,))
    return [(f['user_msg'], f['bot_reply']) for f in cur.fetchall()]


_HISTORIAL_DOS = [("u1", "a1"), ("u2", "a2")]
_MENSAJES_DOS = [
    {"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"},
    {"role": "user", "content": "u2"}, {"role": "assistant", "content": "a2"},
]


@patch('core.orchestrator.Anthropic')
def test_planner_recibe_historial_antes_del_mensaje(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")]
    _sembrar(db, _HISTORIAL_DOS)

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("mensaje actual")

    planner = mock_client.messages.create.call_args_list[0]
    assert planner.kwargs['messages'] == _MENSAJES_DOS + [{"role": "user", "content": "mensaje actual"}]


@patch('core.orchestrator.Anthropic')
def test_sintesis_recibe_historial(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")]
    _sembrar(db, _HISTORIAL_DOS)

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("mensaje actual")

    mensajes = mock_client.messages.create.call_args_list[1].kwargs['messages']
    assert mensajes[:4] == _MENSAJES_DOS
    assert mensajes[-1]["role"] == "user"
    assert "mensaje actual" in mensajes[-1]["content"]
    assert len(mensajes) == 5


@patch('core.orchestrator.Anthropic')
def test_handle_guarda_intercambio(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("Buenas, señor.")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("hola")

    assert _filas_conversations(db) == [("hola", "Buenas, señor.")]


@patch('core.orchestrator.Anthropic')
def test_handle_guarda_pregunta_de_aclaracion(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [
        _make_tool_use_response('request_clarification', 't1', {'question': '¿Qué ciudad?'}),
        _make_text_response("¿De qué ciudad, señor?"),
    ]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("¿qué tiempo hace?")

    assert _filas_conversations(db) == [("¿qué tiempo hace?", "¿De qué ciudad, señor?")]


@patch('core.orchestrator.Anthropic')
def test_error_de_api_no_se_guarda(mock_anthropic_cls, db):
    from anthropic import APIConnectionError
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = APIConnectionError(request=MagicMock())

    from core.orchestrator import Orchestrator
    result = Orchestrator(db, '99999').handle("hola")

    assert "no puedo conectar" in result["text"]
    assert _filas_conversations(db) == []


@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
def test_fallo_al_leer_historial_no_rompe_turno(mock_anthropic_cls, mock_logger, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok, señor")]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    orch._conversations.recientes = MagicMock(side_effect=RuntimeError("bd caída"))
    result = orch.handle("hola")

    assert result["text"] == "ok, señor"
    planner = mock_client.messages.create.call_args_list[0]
    assert planner.kwargs['messages'] == [{"role": "user", "content": "hola"}]
    assert mock_logger.warning.called


@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
def test_fallo_al_guardar_no_rompe_turno(mock_anthropic_cls, mock_logger, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok, señor")]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    orch._conversations.guardar = MagicMock(side_effect=RuntimeError("bd caída"))
    result = orch.handle("hola")

    assert result["text"] == "ok, señor"
    assert mock_logger.warning.called


@patch('core.orchestrator.Anthropic')
def test_resume_plan_sin_historial(mock_anthropic_cls, db):
    from db.pending_plan_repo import PendingPlanRepository
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    _sembrar(db, _HISTORIAL_DOS)
    guardados = [
        {"role": "user", "content": "¿qué tiempo hace?"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "rc1", "name": "request_clarification",
                                           "input": {"question": "¿Qué ciudad?"}}]},
    ]
    PendingPlanRepository(db).save('99999', "¿qué tiempo hace?", _messages_to_json(guardados), "¿Qué ciudad?")
    mock_client.messages.create.side_effect = [
        _make_text_response("S"),            # _is_plan_reply
        _make_text_response("listo"),        # planner
        _make_text_response("Madrid, señor."),  # síntesis
    ]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("Madrid")

    planner = mock_client.messages.create.call_args_list[1]
    mensajes = planner.kwargs['messages']
    assert mensajes[0] == guardados[0]
    assert len(mensajes) == 3
    assert mensajes[2]['content'][0]['type'] == 'tool_result'
    assert not any(m.get('content') in ("u1", "a1", "u2", "a2") for m in mensajes)


@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
def test_log_no_lleva_contenido_del_historial(mock_anthropic_cls, mock_logger, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")]
    _sembrar(db, [("ZZ-SECRETO pregunta", "ZZ-SECRETO respuesta")])

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("hola")

    mock_client.messages.create.call_args_list[0]  # el historial sí viaja a la API…
    assert "ZZ-SECRETO" in str(mock_client.messages.create.call_args_list[0])
    assert mock_logger.info.called or mock_logger.bind.called
    todo_el_log = str(mock_logger.mock_calls)
    assert "ZZ-SECRETO" not in todo_el_log  # …pero nunca al log


@patch('core.orchestrator.Anthropic')
def test_historial_descarta_intercambio_con_lado_vacio(mock_anthropic_cls, db):
    # H2-revision R5: la API rechaza contenido vacío; un intercambio roto no debe envenenar los turnos.
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")]
    _sembrar(db, [("hola", ""), ("u2", "a2")])

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("mensaje actual")

    planner = mock_client.messages.create.call_args_list[0]
    assert planner.kwargs['messages'] == [
        {"role": "user", "content": "u2"}, {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "mensaje actual"},
    ]


@patch('core.orchestrator.Anthropic')
def test_no_guarda_respuesta_vacia(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("hola")

    assert _filas_conversations(db) == []


# ── Fase 1 H4: D26, Sebastian no se inventa al usuario ───────────────────────────────────────

def test_planner_system_lleva_la_regla_d26():
    from core.orchestrator import _planner_system
    texto = _planner_system()
    assert "D26" in texto
    assert "preguntas sobre el usuario" in texto
    assert "search_memory" in texto


def test_alfred_system_lleva_la_regla_d26():
    assert "D26" in _ALFRED_SYSTEM
    assert "no es una fuente" in _ALFRED_SYSTEM
    assert "no me consta" in _ALFRED_SYSTEM


# ── Fase 2 H0: Haiku 5.5 como planner (D28) ──────────────────────────────────────────────────

def _bloque(tipo, **campos):
    b = MagicMock()
    b.type = tipo
    for k, v in campos.items():
        setattr(b, k, v)
    return b


def _respuesta(bloques, stop_reason='end_turn', **extra):
    r = MagicMock()
    r.stop_reason = stop_reason
    r.content = bloques
    for k, v in extra.items():
        setattr(r, k, v)
    return r


@patch('core.orchestrator.Anthropic')
def test_planner_usa_modelo_unico(mock_anthropic_cls, db):
    """D28: planner, _resume_plan y _is_plan_reply usan _MODELO_PLANNER (y su output_config)."""
    from core.orchestrator import Orchestrator, _MODELO_PLANNER, _PLANNER_EXTRA
    from db.pending_plan_repo import PendingPlanRepository
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # (a) turno normal: planner + síntesis
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")]
    Orchestrator(db, '99999').handle("hola")
    planner, sintesis = mock_client.messages.create.call_args_list
    assert planner.kwargs['model'] == _MODELO_PLANNER
    assert sintesis.kwargs['model'] == "claude-sonnet-4-6"

    # (b) reanudación: _is_plan_reply + planner de _resume_plan + síntesis
    mock_client.reset_mock()
    guardados = [
        {"role": "user", "content": "¿qué tiempo hace?"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "rc1", "name": "request_clarification",
                                           "input": {"question": "¿Qué ciudad?"}}]},
    ]
    PendingPlanRepository(db).save('99999', "¿qué tiempo hace?", _messages_to_json(guardados), "¿Qué ciudad?")
    mock_client.messages.create.side_effect = [
        _make_text_response("SI"), _make_text_response("listo"), _make_text_response("Madrid, señor."),
    ]
    Orchestrator(db, '99999').handle("Madrid")
    es_respuesta, planner, sintesis = mock_client.messages.create.call_args_list
    assert es_respuesta.kwargs['model'] == _MODELO_PLANNER
    assert planner.kwargs['model'] == _MODELO_PLANNER
    assert sintesis.kwargs['model'] == "claude-sonnet-4-6"
    # Haiku 5.5 piensa por defecto: el esfuerzo bajo viaja en las tres llamadas del planner.
    for llamada in (es_respuesta, planner):
        for clave, valor in _PLANNER_EXTRA.items():
            assert llamada.kwargs[clave] == valor


@patch('core.orchestrator.Anthropic')
@patch('core.tool_executor.ToolExecutor.execute')
def test_respuesta_con_thinking_primero(mock_execute, mock_anthropic_cls, db):
    """D28: [thinking, tool_use] → se ejecuta la tool y el siguiente `messages` lleva el thinking tal cual."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_execute.return_value = [{'event_id': 1}]
    thinking = _bloque('thinking', thinking="", signature="firma-1")
    uso = _bloque('tool_use', name='calendar_search_events', id='t1', input={'query': 'teatro'})
    mock_client.messages.create.side_effect = [
        _respuesta([thinking, uso], stop_reason='tool_use'),
        _make_text_response("listo"),
        _make_text_response("El teatro es mañana."),
    ]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("¿cuándo es el teatro?")

    mock_execute.assert_called_once_with('calendar_search_events', {'query': 'teatro'})
    segundo = mock_client.messages.create.call_args_list[1].kwargs['messages']
    assistant = segundo[-2]
    assert assistant["role"] == "assistant"
    assert assistant["content"][0] is thinking          # tal cual, sin tocar ni reordenar
    assert assistant["content"] == [thinking, uso]
    assert segundo[-1]["content"][0]["type"] == "tool_result"


@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
def test_is_plan_reply_con_thinking_primero(mock_anthropic_cls, mock_logger, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    thinking = _bloque('thinking', thinking="", signature="f")

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')

    mock_client.messages.create.return_value = _respuesta([thinking, _bloque('text', text="SI")])
    assert orch._is_plan_reply("Madrid", "¿Qué ciudad?") is True

    mock_client.messages.create.return_value = _respuesta([thinking], stop_reason='max_tokens')
    mock_logger.reset_mock()
    assert orch._is_plan_reply("Madrid", "¿Qué ciudad?") is False
    assert mock_logger.warning.called


@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
@patch('core.tool_executor.ToolExecutor.execute')
def test_refusal_del_planner(mock_execute, mock_anthropic_cls, mock_logger, db):
    """D28: stop_reason=refusal → warning con la categoría (sin el mensaje), sin tools, y se sintetiza."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    rechazo = _respuesta([], stop_reason='refusal', stop_details=MagicMock(category='cyber'))
    mock_client.messages.create.side_effect = [rechazo, _make_text_response("No me consta nada, señor.")]

    from core.orchestrator import Orchestrator
    result = Orchestrator(db, '99999').handle("ZZ-MENSAJE-SECRETO")

    assert result["text"] == "No me consta nada, señor."
    mock_execute.assert_not_called()
    avisos = [str(c) for c in mock_logger.warning.call_args_list]
    assert any("cyber" in a for a in avisos)
    assert not any("ZZ-MENSAJE-SECRETO" in a for a in avisos)


def test_pending_plan_conserva_thinking():
    """T0.6: el ida y vuelta de pending_plans conserva `thinking` (aunque esté vacío) y su `signature`."""
    from anthropic.types import ThinkingBlock
    bloque_sdk = ThinkingBlock(thinking="", signature="firma-abc", type="thinking")
    bloque_dict = {"type": "thinking", "thinking": "", "signature": "firma-def"}
    messages = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": [bloque_sdk, bloque_dict]},
    ]

    ida_y_vuelta = _messages_from_json(_messages_to_json(messages))

    a, b = ida_y_vuelta[1]["content"]
    assert a == {"type": "thinking", "thinking": "", "signature": "firma-abc"}
    assert b == bloque_dict


@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
def test_planner_cortado_por_max_tokens_deja_warning(mock_anthropic_cls, mock_logger, db):
    """El razonamiento cuenta para max_tokens: un planner cortado antes de decidir no debe ser silencioso."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    cortado = _respuesta([_bloque('thinking', thinking="", signature="f")], stop_reason='max_tokens')
    mock_client.messages.create.side_effect = [cortado, _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("hola")

    assert any("max_tokens" in str(c) for c in mock_logger.warning.call_args_list)


# ── Fase 2 H3: índice de la memoria en el planner (D36) ───────────────────────────────────────

_INDICE = "Lo que me consta de ti (nombres, sin valores; usa search_memory para los valores):\n- Paco (persona): alergia"


def test_planner_system_lleva_el_indice_despues_de_las_capacidades():
    texto = _planner_system(_INDICE)
    assert build_capabilities_digest() in texto
    assert texto.index(build_capabilities_digest()) < texto.index(_INDICE)
    assert _INDICE not in _planner_system()                      # sin indice, el prompt no cambia
    assert _INDICE not in _ALFRED_SYSTEM                         # D36: no va en la sintesis


@patch('core.orchestrator.indice_memoria', return_value=_INDICE)
@patch('core.orchestrator.Anthropic')
def test_el_planner_recibe_el_indice_y_alfred_no(mock_anthropic_cls, mock_indice, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("¿qué alergias tiene Paco?")

    planner, sintesis = mock_client.messages.create.call_args_list
    assert _INDICE in planner.kwargs['system']
    assert _INDICE not in sintesis.kwargs['system']


@patch('core.orchestrator.indice_memoria', return_value=_INDICE)
@patch('core.orchestrator.Anthropic')
def test_el_indice_se_calcula_una_vez_por_turno(mock_anthropic_cls, mock_indice, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [
        _make_tool_use_response("search_memory", "t1", {"query": "paco"}),
        _make_text_response("ya"), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    orch._executor.execute = MagicMock(return_value={"hechos": []})
    orch.handle("¿qué alergias tiene Paco?")

    assert mock_indice.call_count == 1
    planner_1, planner_2, _ = mock_client.messages.create.call_args_list
    assert _INDICE in planner_1.kwargs['system'] and _INDICE in planner_2.kwargs['system']


@patch('core.orchestrator.logger')
@patch('core.orchestrator.indice_memoria', side_effect=RuntimeError("bd caída"))
@patch('core.orchestrator.Anthropic')
def test_indice_falla_y_turno_sigue(mock_anthropic_cls, mock_indice, mock_logger, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok, señor")]

    from core.orchestrator import Orchestrator
    result = Orchestrator(db, '99999').handle("hola")

    assert result["text"] == "ok, señor"
    planner = mock_client.messages.create.call_args_list[0]
    assert "Lo que me consta de ti" not in planner.kwargs['system']
    avisos = " ".join(str(c) for c in mock_logger.warning.mock_calls)
    assert "índice" in avisos and "RuntimeError" in avisos       # el aviso lleva el tipo del error, no su texto
    assert "bd caída" not in avisos


@patch('core.orchestrator.logger')
@patch('core.orchestrator.indice_memoria', return_value="Lo que me consta de ti:\n- Persona-secreta-123 (persona): alergia")
@patch('core.orchestrator.Anthropic')
def test_el_log_no_lleva_el_indice(mock_anthropic_cls, mock_indice, mock_logger, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("hola")

    volcado = " ".join(str(c) for log in (mock_logger.info, mock_logger.debug, mock_logger.warning)
                       for c in log.mock_calls)
    assert "Persona-secreta-123" not in volcado


@patch('core.orchestrator.leer_proyectos', return_value={"proyecto-prueba": {"estado": "stable"}})
@patch('core.orchestrator.indice_memoria', return_value="")
@patch('core.orchestrator.Anthropic')
def test_el_vault_solo_se_pasa_al_indice_del_propietario(mock_anthropic_cls, mock_indice, mock_leer, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")] * 2
    config = {'anthropic_apikey': 'k', 'vault_docs_path': '/vault/30-projects', 'cuaderno_chat_id': 99999}

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999', config=config).handle("hola")           # el propietario
    assert mock_indice.call_args.args[2] == {"proyecto-prueba": {"estado": "stable"}}
    Orchestrator(db, '12345', config=config).handle("hola")           # otro usuario autorizado
    assert mock_indice.call_args.args[2] is None


# ── Fase 2 H3 (R7, D41): el literal del usuario llega a la fuente ─────────────────────────────

@patch('core.orchestrator.Anthropic')
def test_el_ejecutor_recibe_el_mensaje_literal_del_turno(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    assert orch._executor.mensaje_del_turno is None
    orch.handle("apunta lo de Paco, que es alérgico a los frutos secos")
    assert orch._executor.mensaje_del_turno == "apunta lo de Paco, que es alérgico a los frutos secos"


@patch('core.orchestrator.Anthropic')
def test_el_mensaje_del_turno_se_renueva_en_cada_turno(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")] * 2

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    orch.handle("primero")
    orch.handle("segundo")
    assert orch._executor.mensaje_del_turno == "segundo"


# ── Fase 2 H3 (R12, D42): el log de inicio de turno no guarda el texto del mensaje ────────────

@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
def test_el_log_de_inicio_de_turno_no_lleva_el_mensaje(mock_anthropic_cls, mock_logger, db):
    """D42: «olvida lo de…» borra el texto. El log de inicio de turno guardaba los primeros 200 caracteres de cada
    mensaje, y ahí seguía el texto olvidado. Ahora solo la longitud y el usuario."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("x"), _make_text_response("ok")]
    mensaje = "Olvida lo de la colonoscopia-secreta-4242"

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle(mensaje)

    # `logger.bind(...).info(...)` es una llamada encadenada: se mira todo lo que registró el mock.
    volcado = " ".join(str(c) for c in mock_logger.mock_calls)
    assert "colonoscopia-secreta-4242" not in volcado and "Olvida lo de" not in volcado
    inicio = [c for c in mock_logger.mock_calls if "Turn start" in str(c)]
    assert inicio, "tiene que seguir habiendo traza de inicio de turno"
    assert f"chars={len(mensaje)}" in str(inicio[0]) and "user=99999" in str(inicio[0])


# ── Fase 2 H3 (R14, D42): los logs de error de handle() tampoco guardan el texto del mensaje ───

def _errores_de_api():
    from anthropic import APIConnectionError, APIError, RateLimitError
    return [
        APIConnectionError(request=MagicMock()),
        RateLimitError("limite", response=MagicMock(status_code=429, headers={}), body=None),
        APIError("fallo del servicio", request=MagicMock(), body=None),
    ]


@pytest.mark.parametrize("error", _errores_de_api(), ids=["conexion", "limite", "api"])
@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
def test_los_logs_de_error_no_llevan_el_mensaje(mock_anthropic_cls, mock_logger, error, db):
    """Mismo caso que R12: «olvida lo de…» borra el texto, y los logs de error de handle() guardaban 200 caracteres."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = error
    mensaje = "Olvida lo de la colonoscopia-secreta-8181"

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle(mensaje)

    volcado = " ".join(str(c) for c in mock_logger.mock_calls)
    assert "colonoscopia-secreta-8181" not in volcado and "Olvida lo de" not in volcado
    errores = [c for c in mock_logger.mock_calls if "exception" in str(c)[:60] or "Anthropic API" in str(c)]
    assert errores, "tiene que seguir quedando la traza del error"
    assert any(f"chars={len(mensaje)}" in str(c) and "user=99999" in str(c) for c in errores)


# ── Fase 2 H4 (R15, D44): un turno sin herramientas, Alfred lo sabe ───────────────────────────

_AVISO = ("[En este turno no se ha ejecutado ninguna herramienta: no has guardado, cambiado, borrado, apuntado ni creado "
          "nada. Si el usuario lo pidió, dile en llano que no lo has hecho y ofrécete a intentarlo.]")


def _orquestador_con_sintesis(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_text_response("ok")
    from core.orchestrator import Orchestrator
    return Orchestrator(db, '99999'), mock_client


def test_la_constante_es_la_de_la_revision():
    from core.orchestrator import _TURNO_SIN_HERRAMIENTAS
    assert _TURNO_SIN_HERRAMIENTAS == _AVISO


@patch('core.orchestrator.Anthropic')
def test_sintesis_sin_herramientas_lleva_aviso(mock_anthropic_cls, db):
    """D44: sin tool_results, Alfred solo veía el mensaje y el historial («Anotado… al marisco») y contestaba «He retirado…».
    Ese dato (en este turno no se hizo nada) lo tiene el código y ahora se le pasa, DESPUÉS del mensaje del usuario."""
    orch, cliente = _orquestador_con_sintesis(mock_anthropic_cls, db)
    historial = [{"role": "user", "content": "Paco también es alérgico al marisco"},
                 {"role": "assistant", "content": "Anotado, señor."}]

    orch._synthesize("Olvida lo del marisco de Paco", [], historial)

    mensajes = cliente.messages.create.call_args.kwargs["messages"]
    assert mensajes[:-1] == historial                                  # el historial viaja igual que antes
    ultimo = mensajes[-1]["content"]
    assert ultimo.index("Olvida lo del marisco de Paco") < ultimo.index(_AVISO)       # después del mensaje
    assert ultimo.rstrip().endswith(_AVISO)


@patch('core.orchestrator.Anthropic')
def test_sintesis_con_herramientas_no_lleva_aviso(mock_anthropic_cls, db):
    orch, cliente = _orquestador_con_sintesis(mock_anthropic_cls, db)
    resultados = [{"tool": "mark_as_memorable", "input": {"texto": "x"}, "result": {"success": True}}]

    orch._synthesize("Olvida lo del marisco de Paco", resultados, [])

    assert "no se ha ejecutado ninguna herramienta" not in cliente.messages.create.call_args.kwargs["messages"][-1]["content"]


@patch('core.orchestrator.Anthropic')
def test_un_turno_en_el_que_el_planner_no_llama_a_ninguna_tool_le_pasa_el_aviso_a_alfred(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("Listo, he retirado el marisco."), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("Olvida lo del marisco de Paco")

    sintesis = mock_client.messages.create.call_args_list[1]
    assert _AVISO in sintesis.kwargs["messages"][-1]["content"]


@patch('core.orchestrator.Anthropic')
def test_un_turno_con_tool_no_pasa_el_aviso(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [
        _make_tool_use_response("search_memory", "t1", {"query": "paco"}), _make_text_response("ya"), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    orch._executor.execute = MagicMock(return_value={"hechos": []})
    orch.handle("¿Qué alergias tiene Paco?")

    assert _AVISO not in mock_client.messages.create.call_args_list[2].kwargs["messages"][-1]["content"]


# ── Fase 3 H7 (R17, D57): el texto del planner que cierra SIN tool llega a Alfred, y no al log ────────────────────────

_PREGUNTA = "¿Lo quieres esta noche o mañana por la noche?"


@patch('core.orchestrator.Anthropic')
def test_r17_el_texto_del_planner_sin_tool_llega_a_alfred_despues_del_aviso(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response(_PREGUNTA), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("Recuérdame a la una que me duerma ya")

    ultimo = mock_client.messages.create.call_args_list[1].kwargs["messages"][-1]["content"]
    assert _PREGUNTA in ultimo and _AVISO in ultimo                       # el aviso sigue ahí: la nota no lo sustituye
    assert ultimo.index(_AVISO) < ultimo.index(_PREGUNTA)                 # y va después
    assert "no es un dato ni algo hecho" in ultimo


@patch('core.orchestrator.Anthropic')
def test_r17_si_el_turno_ejecuto_una_tool_el_cierre_normal_no_llega_a_alfred(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [
        _make_tool_use_response("search_memory", "t1", {"query": "paco"}),
        _make_text_response("Hecho, te recordaré mañana a la una."), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    orch = Orchestrator(db, '99999')
    orch._executor.execute = MagicMock(return_value={"hechos": []})
    orch.handle("¿Qué alergias tiene Paco?")

    sintesis = mock_client.messages.create.call_args_list[2].kwargs["messages"][-1]["content"]
    assert "Hecho, te recordaré" not in sintesis and "Nota de quien planifica" not in sintesis


@patch('core.orchestrator.Anthropic')
def test_r17_sin_tool_y_sin_texto_el_prompt_queda_como_hoy(mock_anthropic_cls, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("   "), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("Olvida lo del marisco de Paco")

    ultimo = mock_client.messages.create.call_args_list[1].kwargs["messages"][-1]["content"]
    assert ultimo.rstrip().endswith(_AVISO) and "Nota de quien planifica" not in ultimo


@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
def test_r17_el_texto_no_va_al_log_solo_que_hubo_nota_y_su_longitud(mock_anthropic_cls, mock_logger, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response(_PREGUNTA), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("Recuérdame a la una que me duerma ya")

    volcado = " ".join(str(c) for c in mock_logger.mock_calls)
    assert "esta noche o mañana" not in volcado and _PREGUNTA not in volcado
    assert f"planner_nota=1 chars={len(_PREGUNTA)}" in volcado


@patch('core.orchestrator.logger')
@patch('core.orchestrator.Anthropic')
def test_r17_sin_nota_no_hay_linea_de_nota(mock_anthropic_cls, mock_logger, db):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response(""), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    Orchestrator(db, '99999').handle("Olvida lo del marisco de Paco")

    assert "planner_nota" not in " ".join(str(c) for c in mock_logger.mock_calls)


@patch('core.orchestrator.Anthropic')
def test_r17_al_reanudar_un_plan_tambien_llega_la_nota(mock_anthropic_cls, db):
    """`_resume_plan` comparte el camino de síntesis: lo que el planner escribe al cerrar sin tool tampoco se pierde."""
    import time
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_make_text_response("¿A qué hora, exactamente?"), _make_text_response("ok")]

    from core.orchestrator import Orchestrator
    plan = {
        "messages_json": _messages_to_json([
            {"role": "user", "content": "Recuérdame lo del martes"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "rc1", "name": "request_clarification",
                                               "input": {"question": "¿Qué día?"}}]}]),
        "original_message": "Recuérdame lo del martes",
    }
    Orchestrator(db, '99999')._resume_plan(plan, "el 17", time.perf_counter())

    ultimo = mock_client.messages.create.call_args_list[1].kwargs["messages"][-1]["content"]
    assert "¿A qué hora, exactamente?" in ultimo and _AVISO in ultimo


# ── Fase 3 H7 (R18, D58): regla de madrugada y fecha completa en la confirmación ─────────────────────────────────────

def test_r18_la_regla_de_madrugada_esta_en_el_planner():
    from core.orchestrator import _REGLA_COMPROMISOS
    for trozo in ("00:00", "05:59", "esta noche", "fecha de mañana", "fecha explícita", "más próxima", "ya ha pasado"):
        assert trozo in _REGLA_COMPROMISOS, trozo
    assert _REGLA_COMPROMISOS in _planner_system()


def test_r18_alfred_confirma_con_dia_de_la_semana_dia_y_mes():
    assert "cuando_texto" in _ALFRED_SYSTEM and "día de la semana" in _ALFRED_SYSTEM
