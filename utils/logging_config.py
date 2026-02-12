"""Loguru logging configuration for Sebastian bot"""
from loguru import logger
import sys


def setup_logging(log_folder: str = "logs", level: str = "INFO"):
    """
    Configure loguru for the application.

    Args:
        log_folder: Directory for log files
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove default handler
    logger.remove()

    # Console output (colorized, user-friendly)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True
    )

    # File output (detailed for debugging)
    logger.add(
        f"{log_folder}/app.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="1 month",
        compression="zip",
        enqueue=True  # Thread-safe
    )

    # Error-only file (critical issues)
    logger.add(
        f"{log_folder}/errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
        level="ERROR",
        rotation="10 MB",
        retention="3 months",
        compression="zip",
        enqueue=True
    )

    logger.info("Logging system initialized")
    return logger
