# bot/handlers.py
"""
Telegram bot handlers for Sebastian 2.0.

Integrates parser, router, formatter, and sprite system.
"""
from core.haiku_parser import HaikuParser
from core.router import ModuleRouter
from bot.formatter import ResponseFormatter
from loguru import logger


def setup_handlers(bot, config):
    """
    Setup all Telegram message handlers.

    Args:
        bot: TeleBot instance
        config: Configuration dict with authorized_users, authorized_ids
    """
    # Initialize components
    parser = HaikuParser()
    formatter = ResponseFormatter()

    logger.info("Setting up Telegram bot handlers")

    def authorized(username, userid):
        """
        Check if user is authorized.

        Args:
            username: Telegram username
            userid: Telegram user ID

        Returns:
            bool: True if authorized
        """
        return (
            username in config.get("authorized_users", [])
            or userid in config.get("authorized_ids", [])
        )

    @bot.message_handler(commands=['start', 'hola'])
    def send_welcome(message):
        """Welcome message"""
        if not authorized(message.chat.username, message.chat.id):
            bot.reply_to(message, "No estás autorizado para usar este bot.")
            logger.warning(
                f"Unauthorized access attempt: {message.chat.username} ({message.chat.id})"
            )
            return

        logger.info(f"Welcome message sent to {message.chat.username}")
        bot.reply_to(
            message,
            "¡Hola! Soy Sebastian 2.0, tu asistente personal. "
            "Puedo ayudarte con inventario, listas de compra, equipaje y notas. "
            "Usa /ayuda para ver qué puedo hacer."
        )

    @bot.message_handler(commands=['help', 'ayuda'])
    def send_help(message):
        """Help message"""
        if not authorized(message.chat.username, message.chat.id):
            bot.reply_to(message, "No estás autorizado para usar este bot.")
            return

        help_text = """
🤖 **Sebastian 2.0 - Comandos Disponibles**

**Comandos Básicos:**
• /start, /hola - Saludo inicial
• /help, /ayuda - Muestra esta ayuda
• /id_me, /whoami - Muestra tu ID de Telegram

**Qué puedo hacer:**

📦 **Inventario:**
• "compré 6 aguacates"
• "me quedan 2 limones"
• "cuántos huevos tengo?"
• "lista el inventario"

🛒 **Lista de Compra:**
• "añade leche a la compra"
• "quita pan de la compra"
• "lista de la compra"

🎒 **Listas de Equipaje:**
• "añade toalla a Gijón"
• "añade cepillo dental a Gijón, siempre" (item recurrente)
• "marca cargador en lista Gijón"
• "lista equipaje Gijón"

📝 **Notas:**
• "apunta que Rebe prefiere manzanas verdes"
• "busca notas sobre Rebe"

💬 Simplemente escribe o envía un mensaje de voz describiendo lo que necesitas.
"""
        bot.reply_to(message, help_text, parse_mode='Markdown')
        logger.info(f"Help message sent to {message.chat.username}")

    @bot.message_handler(commands=['id_me', 'whoami'])
    def send_id(message):
        """Show user's Telegram ID"""
        response = (
            f"📋 **Tu información:**\n"
            f"• ID: `{message.chat.id}`\n"
            f"• Username: @{message.chat.username or 'sin username'}"
        )
        bot.reply_to(message, response, parse_mode='Markdown')
        logger.info(f"ID request from {message.chat.username} ({message.chat.id})")

    @bot.message_handler(func=lambda message: True, content_types=['text'])
    def handle_text(message):
        """
        Handle all text messages.

        Flow: parse → route → format → send photo with caption
        """
        if not authorized(message.chat.username, message.chat.id):
            bot.reply_to(message, "No estás autorizado para usar este bot.")
            return

        try:
            logger.info(
                f"Processing text from {message.chat.username}: {message.text[:50]}..."
            )

            # Parse intent
            parsed = parser.parse(message.text)
            logger.debug(f"Parsed intent: {parsed}")

            # Route to module
            router = ModuleRouter(str(message.chat.id))
            result = router.route(parsed)
            logger.debug(f"Router result: {result}")

            # Build context for formatter
            context = {
                "module": parsed.get("module"),
                "action": parsed.get("action"),
                "low_stock": result.get("low_stock", False),
                "empty": result.get("data", {}) == [] or result.get("data") is None
            }

            # Format response with sprite
            response = formatter.format_response(result, context)
            logger.debug(f"Formatted response: {response}")

            # Send sprite photo with caption
            try:
                with open(response["sprite_path"], 'rb') as photo:
                    bot.send_photo(
                        chat_id=message.chat.id,
                        photo=photo,
                        caption=response["caption"]
                    )
                logger.info(f"Response sent successfully to {message.chat.username}")
            except FileNotFoundError:
                logger.error(f"Sprite file not found: {response['sprite_path']}")
                bot.reply_to(message, response["caption"])

            # Cleanup router connection
            router.cleanup()

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

            # Send error response with confused sprite
            error_result = {
                "success": False,
                "result": "Ups, algo salió mal. ¿Puedes intentarlo de nuevo?",
                "data": {}
            }
            error_context = {"module": "unknown", "action": "unknown"}
            error_response = formatter.format_response(error_result, error_context)

            try:
                with open(error_response["sprite_path"], 'rb') as photo:
                    bot.send_photo(
                        chat_id=message.chat.id,
                        photo=photo,
                        caption=error_response["caption"]
                    )
            except FileNotFoundError:
                # Fallback to text-only if sprite not found
                bot.reply_to(message, error_response["caption"])

    @bot.message_handler(content_types=['voice'])
    def handle_voice(message):
        """
        Handle voice messages.

        Note: Basic Telegram API doesn't provide transcription.
        Users need Telegram Premium (auto-transcription) or we need Whisper API.
        """
        if not authorized(message.chat.username, message.chat.id):
            return

        logger.info(f"Voice message received from {message.chat.username}")

        bot.reply_to(
            message,
            "📱 **Mensajes de voz:**\n\n"
            "Los mensajes de voz requieren Telegram Premium (conversión automática) "
            "o integración con Whisper API.\n\n"
            "Por ahora, por favor escribe el mensaje en texto. "
            "¡Gracias por tu comprensión! 🙏"
        )

    logger.info("All handlers registered successfully")
