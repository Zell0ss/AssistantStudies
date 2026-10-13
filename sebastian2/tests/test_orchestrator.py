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
    Orchestrator(db, '99999', config=fake_config)
    mock_tool_executor_cls.assert_called_once_with(db, '99999', config=fake_config)


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
