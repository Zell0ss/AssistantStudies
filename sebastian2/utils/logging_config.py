# utils/logging_config.py
"""
Centralized logging configuration using loguru.
"""
from loguru import logger
import sys
import os

def setup_logging(log_folder='logs', log_level='INFO'):
    """
    Configure loguru for Sebastian 2.0.

    Args:
        log_folder: Directory to store log files
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove default handler
    logger.remove()

    # Console handler (colorized)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=log_level
    )

    # Create log folder if not exists
    os.makedirs(log_folder, exist_ok=True)

    # File handler (rotating)
    logger.add(
        f"{log_folder}/sebastian2.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level=log_level,
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )

    logger.info(f"Logging initialized: level={log_level}, folder={log_folder}")
