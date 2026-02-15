"""Sprite system for managing character expressions with multi-skin support."""

import os
from pathlib import Path
from typing import Dict, List

import yaml
from loguru import logger


class SpriteSystem:
    """Manages sprite expressions and maps them to image files with skin support."""

    def __init__(self):
        """Load sprite mapping from sprites/mapping.yaml."""
        self.sprites_dir = Path(__file__).parent
        self.mapping_file = self.sprites_dir / 'mapping.yaml'

        if not self.mapping_file.exists():
            raise FileNotFoundError(
                f"Sprite mapping file not found: {self.mapping_file}"
            )

        # Load mapping from YAML
        with open(self.mapping_file, 'r', encoding='utf-8') as f:
            mapping = yaml.safe_load(f)

        self.expressions: Dict[str, str] = mapping.get('expressions', {})
        self.default_expression: str = mapping.get('default', 'neutral')
        self.default_skin: str = mapping.get('default_skin', 'sebastian')
        self.available_skins: List[str] = mapping.get('available_skins', ['sebastian'])

        logger.info(
            f"Loaded {len(self.expressions)} sprite expressions "
            f"(default: {self.default_expression}, default skin: {self.default_skin})"
        )

    def get_sprite(self, expression: str, skin: str = None) -> str:
        """
        Get sprite image path for expression with specified skin.

        Args:
            expression: Expression name (e.g., "confident")
            skin: Skin name (e.g., "sebastian", "cute"). Uses default if None.

        Returns:
            Absolute path to sprite image.
            Falls back to default expression/skin if not found.
        """
        # Use default skin if not specified
        if skin is None:
            skin = self.default_skin

        # Validate skin exists
        if skin not in self.available_skins:
            logger.warning(f"Skin '{skin}' not available, using default '{self.default_skin}'")
            skin = self.default_skin

        # Get expression filename (or use default)
        if expression not in self.expressions:
            logger.debug(
                f"Expression '{expression}' not found, using default '{self.default_expression}'"
            )
            expression = self.default_expression

        filename = self.expressions[expression]

        # Build path: sprites/images/{skin}/{filename}
        sprite_path = self.sprites_dir / 'images' / skin / filename

        # Verify file exists
        if not sprite_path.exists():
            logger.error(f"Sprite file not found: {sprite_path}")
            # Fallback to default skin + neutral expression
            sprite_path = self.sprites_dir / 'images' / self.default_skin / self.expressions[self.default_expression]

        return str(sprite_path.resolve())

    def get_available_skins(self) -> List[str]:
        """
        Get list of available sprite skins.

        Returns:
            List of skin names
        """
        return self.available_skins.copy()

    def skin_exists(self, skin: str) -> bool:
        """
        Check if a skin exists.

        Args:
            skin: Skin name to check

        Returns:
            True if skin exists, False otherwise
        """
        skin_dir = self.sprites_dir / 'images' / skin
        return skin_dir.exists() and skin_dir.is_dir()
