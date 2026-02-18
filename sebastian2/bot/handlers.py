# bot/handlers.py
"""
Telegram bot handlers for Sebastian 2.0.

Integrates parser, router, formatter, and sprite system.
"""
import io
import telebot
from telegram_markdown import parse_markdown_to_entities
from core.haiku_parser import HaikuParser
from core.router import ModuleRouter
from bot.formatter import ResponseFormatter
from modules.user_settings import UserSettingsModule
from sprites.sprite_system import SpriteSystem
from db.connection import get_connection
from bot.ticket_handler import handle_media, try_resolve_pending
from modules.ticket_generator import generate_image
from loguru import logger


def _send_markdown(bot, chat_id, text):
    """Send a message with **bold** markdown using Telegram entities (no parse_mode needed)."""
    plain_text, entity_dicts = parse_markdown_to_entities(text)
    entities = [telebot.types.MessageEntity(**e) for e in entity_dicts]
    bot.send_message(chat_id, plain_text, entities=entities or None)


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
    sprite_system = SpriteSystem()

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

    @bot.message_handler(commands=['skins'])
    def list_skins(message):
        """List available sprite skins"""
        if not authorized(message.chat.username, message.chat.id):
            return

        conn = get_connection()
        settings = UserSettingsModule(conn, str(message.chat.id))
        current_skin = settings.get_sprite_skin()
        available_skins = sprite_system.get_available_skins()

        skins_list = "\n".join([
            f"{'✅' if skin == current_skin else '  '} {skin}"
            for skin in available_skins
        ])

        response = (
            f"🎨 **Skins disponibles:**\n\n"
            f"{skins_list}\n\n"
            f"Usa `/skin nombre` para cambiar\n"
            f"Ejemplo: `/skin cute`"
        )
        bot.reply_to(message, response, parse_mode='Markdown')
        logger.info(f"Skins list requested by {message.chat.username}")

    @bot.message_handler(commands=['skin'])
    def change_skin(message):
        """Change sprite skin"""
        if not authorized(message.chat.username, message.chat.id):
            return

        # Parse command: /skin <skin_name>
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message,
                "Uso: `/skin nombre`\n"
                "Ejemplo: `/skin cute`\n\n"
                "Usa `/skins` para ver las opciones",
                parse_mode='Markdown'
            )
            return

        skin_name = parts[1].strip()

        # Validate skin exists
        if not sprite_system.skin_exists(skin_name):
            available = ", ".join(sprite_system.get_available_skins())
            bot.reply_to(message,
                f"❌ Skin '{skin_name}' no encontrado.\n\n"
                f"Skins disponibles: {available}",
                parse_mode='Markdown'
            )
            return

        # Save skin preference
        conn = get_connection()
        settings = UserSettingsModule(conn, str(message.chat.id))
        result = settings.set_sprite_skin(skin_name)

        bot.reply_to(message,
            f"✅ {result['message']}\n\n"
            f"Ahora verás los sprites de '{skin_name}'! 🎨",
            parse_mode='Markdown'
        )
        logger.info(f"{message.chat.username} changed skin to: {skin_name}")

    @bot.message_handler(func=lambda message: True, content_types=['text'])
    def handle_text(message):
        """
        Handle all text messages.

        Flow: parse → route → format → send photo with caption
        """
        if not authorized(message.chat.username, message.chat.id):
            bot.reply_to(message, "No estás autorizado para usar este bot.")
            return

        # Check if user is responding to a pending ticket association
        if try_resolve_pending(message, bot):
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

            # Get user's sprite skin preference
            conn = get_connection()
            settings = UserSettingsModule(conn, str(message.chat.id))
            user_skin = settings.get_sprite_skin()

            # Build context for formatter
            data = result.get("data", {})
            context = {
                "module": parsed.get("module"),
                "action": parsed.get("action"),
                "low_stock": result.get("low_stock", False),
                "empty": (
                    data == [] or
                    data is None or
                    (isinstance(data, dict) and data.get("empty", False))
                )
            }

            # Format response with sprite (using user's skin)
            response = formatter.format_response(result, context, user_skin=user_skin)
            logger.debug(f"Formatted response with skin '{user_skin}': {response}")

            # Send text message first
            _send_markdown(bot, message.chat.id, response["caption"])

            # If show_tickets returned ticket data, send images
            if (parsed.get("module") == "calendar" and
                    parsed.get("action") == "show_tickets" and
                    isinstance(result.get("data"), dict) and
                    result["data"].get("tickets")):
                for ticket in result["data"]["tickets"]:
                    try:
                        img_bytes = generate_image(ticket)
                        if img_bytes:
                            bot.send_photo(
                                message.chat.id,
                                io.BytesIO(img_bytes),
                                caption=ticket['type']
                            )
                        else:
                            bot.send_message(
                                message.chat.id,
                                f"📋 {ticket['type']}: {ticket['value']}"
                            )
                    except Exception as e:
                        logger.error(f"Failed to send ticket image: {e}")

            # Then send sprite as document to preserve transparency
            try:
                with open(response["sprite_path"], 'rb') as sprite:
                    bot.send_document(
                        chat_id=message.chat.id,
                        document=sprite,
                        disable_notification=True  # Silent notification
                    )
                logger.info(f"Response sent successfully to {message.chat.username}")
            except FileNotFoundError:
                logger.error(f"Sprite file not found: {response['sprite_path']}")
                # Text already sent, so just log the error

            # Cleanup router connection
            router.cleanup()

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

            # Get user's skin (or use default if error)
            try:
                conn = get_connection()
                settings = UserSettingsModule(conn, str(message.chat.id))
                user_skin = settings.get_sprite_skin()
            except:
                user_skin = None  # Will use default

            # Send error response with confused sprite
            error_result = {
                "success": False,
                "result": "Ups, algo salió mal. ¿Puedes intentarlo de nuevo?",
                "data": {}
            }
            error_context = {"module": "unknown", "action": "unknown"}
            error_response = formatter.format_response(error_result, error_context, user_skin=user_skin)

            # Send error message
            bot.send_message(
                chat_id=message.chat.id,
                text=error_response["caption"]
            )

            # Send error sprite
            try:
                with open(error_response["sprite_path"], 'rb') as sprite:
                    bot.send_document(
                        chat_id=message.chat.id,
                        document=sprite,
                        disable_notification=True
                    )
            except FileNotFoundError:
                # Text already sent, just log the error
                logger.error(f"Error sprite not found: {error_response['sprite_path']}")

    @bot.message_handler(content_types=['photo'])
    def handle_photo(message):
        """Handle photo messages — try to decode QR/barcode."""
        if not authorized(message.chat.username, message.chat.id):
            return
        handle_media(message, bot)

    @bot.message_handler(content_types=['document'])
    def handle_document(message):
        """Handle document messages — try to decode QR/barcode from image files."""
        if not authorized(message.chat.username, message.chat.id):
            return
        mime = getattr(message.document, 'mime_type', '') or ''
        if mime.startswith('image/'):
            handle_media(message, bot)

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
