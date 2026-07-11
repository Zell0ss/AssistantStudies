# utils/logging_config.py
"""One-time loguru bootstrap.

Removes loguru's built-in default stderr handler so LogCentral's own handlers
(added by every module's `get_logger("sebastian")` call) are the single
source of truth for all logging in this app — no duplicate console/file output.
"""
from loguru import logger

try:
    logger.remove(0)
except ValueError:
    pass  # already removed (re-import, or another module got here first)
