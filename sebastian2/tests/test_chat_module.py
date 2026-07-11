# tests/test_chat_module.py
"""Tests for ChatModule — history persistence."""
import pytest
from unittest.mock import patch, MagicMock
from db.connection import get_connection, close_connection
from modules.chat import ChatModule


@pytest.fixture
def setup():
    user_id = "test_user_chat"
    conn = get_connection()
    chat = ChatModule(conn, user_id)

    # Clean up any existing test data
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE user_id = %s", (user_id,))
    conn.commit()

    yield chat, conn, user_id

    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE user_id = %s", (user_id,))
    conn.commit()
    close_connection()


class TestChatHistory:
    def test_save_and_retrieve(self, setup):
        """Test that saved exchanges are retrieved today."""
        chat, conn, user_id = setup
        chat.save("hola", "Buenas tardes, señor.")
        chat.save("qué tal?", "Todo en orden, gracias por preguntar.")

        history = chat.get_history_today()
        assert len(history) == 2
        assert history[0]['user_msg'] == "hola"
        assert history[0]['bot_reply'] == "Buenas tardes, señor."
        assert history[1]['user_msg'] == "qué tal?"

    def test_history_chronological_order(self, setup):
        """History should be returned oldest-first."""
        chat, conn, user_id = setup
        chat.save("primero", "respuesta 1")
        chat.save("segundo", "respuesta 2")
        chat.save("tercero", "respuesta 3")

        history = chat.get_history_today()
        assert history[0]['user_msg'] == "primero"
        assert history[2]['user_msg'] == "tercero"

    def test_history_limit(self, setup):
        """get_history_today respects the limit parameter."""
        chat, conn, user_id = setup
        for i in range(8):
            chat.save(f"msg {i}", f"reply {i}")

        history = chat.get_history_today(limit=3)
        assert len(history) == 3
        # Should return the 3 most recent (reversed to chronological)
        assert history[-1]['user_msg'] == "msg 7"

    def test_empty_history(self, setup):
        """No history today returns empty list."""
        chat, conn, user_id = setup
        history = chat.get_history_today()
        assert history == []


class TestChatRespond:
    def test_respond_calls_sonnet_and_saves(self, setup):
        """respond() calls Anthropic and saves the exchange."""
        chat, conn, user_id = setup

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="De nada, señor.")]

        with patch.object(chat._client.messages, 'create', return_value=mock_response) as mock_create:
            reply = chat.respond("gracias")

        assert reply == "De nada, señor."

        # Verify it was saved
        history = chat.get_history_today()
        assert len(history) == 1
        assert history[0]['user_msg'] == "gracias"
        assert history[0]['bot_reply'] == "De nada, señor."

    def test_respond_includes_history_as_context(self, setup):
        """respond() passes existing history as message context."""
        chat, conn, user_id = setup
        chat.save("hola", "Buenas tardes.")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Con mucho gusto.")]

        with patch.object(chat._client.messages, 'create', return_value=mock_response) as mock_create:
            chat.respond("gracias")

        call_args = mock_create.call_args
        messages = call_args[1]['messages']

        # Should have: history user, history assistant, new user
        assert len(messages) == 3
        assert messages[0] == {"role": "user", "content": "hola"}
        assert messages[1] == {"role": "assistant", "content": "Buenas tardes."}
        assert messages[2] == {"role": "user", "content": "gracias"}

    def test_respond_uses_sonnet_model(self, setup):
        """respond() uses claude-sonnet-4-6."""
        chat, conn, user_id = setup

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Efectivamente.")]

        with patch.object(chat._client.messages, 'create', return_value=mock_response) as mock_create:
            chat.respond("ok")

        assert mock_create.call_args[1]['model'] == "claude-sonnet-4-6"
