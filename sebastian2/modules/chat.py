# modules/chat.py
"""
Chat module - Alfred-style conversational responses with daily history.

Handles casual conversation when Haiku classifies intent_type as 'conversation'.
Uses Sonnet for responses, persists today's exchanges in MariaDB.
"""
from anthropic import Anthropic
from loguru import logger
from modules.base import BaseModule
from utils.config import get_config

_ALFRED_SYSTEM = """Eres Sebastian, el asistente personal de tu señor.
Tu estilo es el de Alfred Pennyworth: servicial, eficiente, con flema británica.
Eres discreto — no te extiendes innecesariamente, mides cada palabra.
Nunca preguntas más de lo estrictamente necesario.
Respondes siempre en español.
Si el contexto conversacional previo es relevante, lo usas con naturalidad."""

_HISTORY_LIMIT = 6  # últimas 6 interacciones del día (3 pares)


class ChatModule(BaseModule):
    """
    Handles casual conversation with Alfred personality using Sonnet.

    Operations:
    - respond(user_msg) - Generate Alfred-style reply, save to history
    - get_history_today(limit) - Fetch today's chat history for context
    - save(user_msg, bot_reply) - Persist an exchange
    """

    def __init__(self, db, user_id):
        super().__init__(db, user_id)
        config = get_config()
        self._client = Anthropic(api_key=config['anthropic_apikey'])
        self._model = "claude-sonnet-4-6"

    def get_history_today(self, limit=_HISTORY_LIMIT):
        """
        Fetch today's chat exchanges for this user (most recent first, then reversed).

        Args:
            limit: Max number of exchanges to retrieve

        Returns:
            List of dicts with 'user_msg' and 'bot_reply', chronological order
        """
        query = """
            SELECT user_msg, bot_reply
            FROM conversations
            WHERE user_id = %s AND DATE(created_at) = CURDATE()
            ORDER BY id DESC
            LIMIT %s
        """
        cursor = self.execute_query(query, (self.user_id, limit))
        rows = cursor.fetchall()
        # Reverse to get chronological order (oldest first)
        return list(reversed(rows))

    def save(self, user_msg, bot_reply):
        """
        Persist a chat exchange to the conversations table.

        Args:
            user_msg: User's message
            bot_reply: Bot's response
        """
        query = """
            INSERT INTO conversations (user_id, user_msg, bot_reply)
            VALUES (%s, %s, %s)
        """
        self.execute_query(query, (self.user_id, user_msg, bot_reply))
        self.commit()
        logger.debug(f"Saved conversation for user {self.user_id}")

    def respond(self, user_msg):
        """
        Generate an Alfred-style response to a casual message.

        Loads today's history as context, calls Sonnet, saves the exchange.

        Args:
            user_msg: User's casual message

        Returns:
            Bot reply string
        """
        history = self.get_history_today()

        # Build messages from history (alternating user/assistant)
        messages = []
        for exchange in history:
            messages.append({"role": "user", "content": exchange['user_msg']})
            messages.append({"role": "assistant", "content": exchange['bot_reply']})

        # Add current message
        messages.append({"role": "user", "content": user_msg})

        response = self._client.messages.create(
            model=self._model,
            max_tokens=300,
            system=_ALFRED_SYSTEM,
            messages=messages
        )

        reply = response.content[0].text.strip()
        logger.info(f"Chat response for user {self.user_id}: {reply[:80]}")

        self.save(user_msg, reply)
        return reply

    @staticmethod
    def cleanup_old_conversations(db):
        """
        Delete conversations from previous days (called by scheduler at midnight).

        Args:
            db: Database connection
        """
        cursor = db.cursor()
        cursor.execute("DELETE FROM conversations WHERE DATE(created_at) < CURDATE()")
        deleted = cursor.rowcount
        db.commit()
        logger.info(f"Cleaned up {deleted} old conversation records")
