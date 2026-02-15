"""Response formatter with sprite selection."""

import random
from typing import Dict, Optional

from loguru import logger
from sprites.sprite_system import SpriteSystem


class ResponseFormatter:
    """Formats router results into Telegram responses with sprites."""

    def __init__(self):
        """Initialize with SpriteSystem."""
        self.sprite_system = SpriteSystem()
        logger.info("ResponseFormatter initialized")

    def format_response(
        self, router_result: dict, context: Optional[dict] = None
    ) -> dict:
        """
        Format router result into Telegram response with sprite.

        Args:
            router_result: {"success": bool, "result": str, "data": dict}
            context: Optional context for expression selection
                     {"module": str, "action": str, "low_stock": bool, "empty": bool}

        Returns:
            {
                "sprite_path": str,  # Absolute path to sprite image
                "caption": str        # Text response
            }
        """
        if context is None:
            context = {}

        # Select appropriate expression
        expression = self._select_expression(router_result, context)

        # Get sprite path
        sprite_path = self.sprite_system.get_sprite(expression)

        # Extract caption from router result
        caption = router_result.get("result", "")

        logger.debug(
            f"Formatted response: expression={expression}, "
            f"caption_preview={caption[:50]}..."
        )

        return {"sprite_path": sprite_path, "caption": caption}

    def _select_expression(self, router_result: dict, context: dict) -> str:
        """
        Select sprite expression based on result and context.

        Logic:
        - Error (success=False) → confused or apologetic
        - Low stock (context["low_stock"]=True) → concerned
        - Empty list (context["empty"]=True) → apologetic or deadpan
        - Add/update action → confident or triumphant
        - List/query action → neutral
        - Default → neutral

        Args:
            router_result: Result from router
            context: Context dict with module, action, flags

        Returns:
            Expression name (e.g., "confident", "neutral")
        """
        success = router_result.get("success", True)
        action = context.get("action", "")
        low_stock = context.get("low_stock", False)
        empty = context.get("empty", False)

        # Error cases
        if not success:
            return random.choice(["confused", "apologetic"])

        # Special context flags
        if low_stock:
            return "concerned"

        if empty:
            return random.choice(["apologetic", "deadpan"])

        # Action-based selection
        if action in ["add", "update"]:
            return random.choice(["confident", "triumphant"])

        if action in ["list", "query", "get"]:
            return "neutral"

        # Default to neutral
        return "neutral"
