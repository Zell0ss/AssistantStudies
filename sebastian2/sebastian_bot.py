#!/usr/bin/env python3
# sebastian_bot.py
"""
Sebastian 2.0 - Personal Assistant Telegram Bot

Main entry point for the bot. Initializes all components and starts polling.
"""
import telebot
from utils.config import get_config
from utils.logging_config import setup_logging
from bot.handlers import setup_handlers
from loguru import logger


def main():
    """
    Main entry point.

    Loads configuration, sets up logging, initializes bot, and starts polling.
    """
    # Setup logging first
    setup_logging(log_level='INFO')

    logger.info("=" * 60)
    logger.info("Sebastian 2.0 Starting...")
    logger.info("=" * 60)

    try:
        # Load configuration
        config = get_config()
        logger.info("Configuration loaded successfully")

        # Validate required config fields
        required_fields = ['telegram_apikey', 'authorized_users', 'authorized_ids']
        missing_fields = [f for f in required_fields if f not in config]
        if missing_fields:
            logger.error(f"Missing required config fields: {missing_fields}")
            raise ValueError(f"Missing config fields: {missing_fields}")

        # Initialize Telegram bot
        bot = telebot.TeleBot(config['telegram_apikey'])
        logger.info("Telegram bot initialized")

        # Setup all message handlers
        setup_handlers(bot, config)
        logger.info("Message handlers configured")

        # Start polling
        logger.info("Starting bot polling...")
        logger.info(
            f"Authorized users: {len(config['authorized_users'])} usernames, "
            f"{len(config['authorized_ids'])} IDs"
        )
        logger.info("Bot is ready to receive messages!")
        logger.info("=" * 60)

        # Start infinite polling
        bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error starting bot: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
