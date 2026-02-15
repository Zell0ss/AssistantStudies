# tests/test_handlers.py
"""
Tests for Telegram bot handlers.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from bot.handlers import setup_handlers


class TestAuthorization:
    """Test authorization logic"""

    def test_authorized_with_valid_username(self):
        """Test authorization with valid username"""
        # Create mock bot and config
        bot = MagicMock()
        config = {
            "authorized_users": ["testuser", "anotheruser"],
            "authorized_ids": [123, 456],
            "telegram_apikey": "fake_key"
        }

        # Setup handlers
        setup_handlers(bot, config)

        # Extract the authorization function from the message handler
        # We'll test by calling a command handler with authorized user
        message = Mock()
        message.chat.username = "testuser"
        message.chat.id = 999  # Not in authorized_ids, but username matches

        # Get the start command handler (first registered handler)
        start_handler = None
        for call in bot.message_handler.call_args_list:
            if 'commands' in call[1] and 'start' in call[1]['commands']:
                # Get the function that was registered
                start_handler = call[0][0]  # First positional arg is the handler function
                break

        # Call the handler
        if start_handler:
            start_handler(message)
            # Should call reply_to with welcome message, not unauthorized
            bot.reply_to.assert_called()
            call_args = bot.reply_to.call_args[0]
            assert "autorizado" not in call_args[1].lower()  # Should not say "not authorized"

    def test_authorized_with_valid_userid(self):
        """Test authorization with valid user ID"""
        bot = MagicMock()
        config = {
            "authorized_users": ["testuser"],
            "authorized_ids": [123, 456],
            "telegram_apikey": "fake_key"
        }

        setup_handlers(bot, config)

        message = Mock()
        message.chat.username = "unknown_user"  # Not in authorized_users
        message.chat.id = 123  # But ID matches

        # Get the start command handler
        start_handler = None
        for call in bot.message_handler.call_args_list:
            if 'commands' in call[1] and 'start' in call[1]['commands']:
                start_handler = call[0][0]
                break

        if start_handler:
            start_handler(message)
            bot.reply_to.assert_called()
            call_args = bot.reply_to.call_args[0]
            assert "autorizado" not in call_args[1].lower()

    def test_authorized_rejects_invalid_user(self):
        """Test authorization rejects invalid users"""
        bot = MagicMock()
        config = {
            "authorized_users": ["testuser"],
            "authorized_ids": [123],
            "telegram_apikey": "fake_key"
        }

        setup_handlers(bot, config)

        message = Mock()
        message.chat.username = "hacker"  # Not authorized
        message.chat.id = 999  # Not authorized

        # Get the start command handler
        start_handler = None
        for call in bot.message_handler.call_args_list:
            if 'commands' in call[1] and 'start' in call[1]['commands']:
                start_handler = call[0][0]
                break

        if start_handler:
            start_handler(message)
            bot.reply_to.assert_called()
            call_args = bot.reply_to.call_args[0]
            # Should say not authorized
            assert "no estás autorizado" in call_args[1].lower()


class TestCommandHandlers:
    """Test command handlers"""

    def test_help_command(self):
        """Test help command returns help text"""
        bot = MagicMock()
        config = {
            "authorized_users": ["testuser"],
            "authorized_ids": [],
            "telegram_apikey": "fake_key"
        }

        setup_handlers(bot, config)

        message = Mock()
        message.chat.username = "testuser"
        message.chat.id = 123

        # Get help handler
        help_handler = None
        for call in bot.message_handler.call_args_list:
            if 'commands' in call[1] and 'help' in call[1]['commands']:
                help_handler = call[0][0]
                break

        if help_handler:
            help_handler(message)
            bot.reply_to.assert_called()
            call_args = bot.reply_to.call_args[0]
            # Should contain help text
            assert "comandos" in call_args[1].lower()

    def test_id_me_command(self):
        """Test id_me command returns user ID"""
        bot = MagicMock()
        config = {
            "authorized_users": [],
            "authorized_ids": [123],
            "telegram_apikey": "fake_key"
        }

        setup_handlers(bot, config)

        message = Mock()
        message.chat.username = "testuser"
        message.chat.id = 123

        # Get id_me handler
        id_handler = None
        for call in bot.message_handler.call_args_list:
            if 'commands' in call[1] and 'id_me' in call[1]['commands']:
                id_handler = call[0][0]
                break

        if id_handler:
            id_handler(message)
            bot.reply_to.assert_called()
            call_args = bot.reply_to.call_args[0]
            # Should contain user ID
            assert "123" in call_args[1]
