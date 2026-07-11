#!/usr/bin/env python3
# sebastian_bot.py
"""
Sebastian 2.0 - Personal Assistant Telegram Bot

Main entry point for the bot. Initializes all components and starts polling.
"""
import telebot
import utils.logging_config  # noqa: F401 — removes loguru's default handler once
from utils.config import get_config
from bot.handlers import setup_handlers
from bot.scheduler import start_daily_reminder
from logcentral_client import get_logger

logger = get_logger("sebastian")


def main():
    """
    Main entry point.

    Loads configuration, initializes bot, and starts polling.
    """
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

        # Start daily calendar reminder
        scheduler = start_daily_reminder(bot, config)
        logger.info("Daily calendar reminder scheduler started")

        # Start polling
        logger.info("Starting bot polling...")
        logger.info(
            f"Authorized users: {len(config['authorized_users'])} usernames, "
            f"{len(config['authorized_ids'])} IDs"
        )
        logger.info("Bot is ready to receive messages!")
        logger.info("=" * 60)

        # Clear all pending plans on startup (plans are session-scoped)
        try:
            from db.connection import get_connection
            from db.pending_plan_repo import PendingPlanRepository
            PendingPlanRepository(get_connection()).delete_all()
        except Exception as e:
            logger.warning(f"Could not clear pending plans on startup: {e}")

        # Start infinite polling
        bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
        if 'scheduler' in locals():
            scheduler.shutdown()
    except Exception as e:
        logger.error(f"Fatal error starting bot: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
