"""Tests for Orchestrator — tool use loop."""
import json
import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from tests.test_item_list_module import MySQLCompatibleConnection
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
    msg.content = [content_block]
    return msg


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

    assert isinstance(result, str)
    assert len(result) > 0


@patch('core.orchestrator.Anthropic')
@patch('core.tool_executor.ToolExecutor.execute')
@patch('core.orchestrator.logger')
def test_tool_steps_are_logged(mock_logger, mock_execute, mock_anthropic_cls, db):
    """Calling a tool logs 'Calling tool X' before and 'Tool X →' after."""
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
    all_info_calls = [str(c) for c in mock_logger.info.call_args_list]
    assert any("calendar_search_events" in c and "Calling" in c for c in all_debug_calls)
    assert any("calendar_search_events" in c and "→" in c for c in all_info_calls)


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
    assert isinstance(result, str)
    assert len(result) > 0


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

    assert isinstance(result, str)


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

    assert isinstance(result, str)


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

        # Final response is a string (Alfred synthesized it)
        assert isinstance(result, str)
        assert len(result) > 10
