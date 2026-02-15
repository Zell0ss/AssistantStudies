"""Sprite system for managing character expressions."""

import os
from pathlib import Path
from typing import Dict

import yaml
from loguru import logger


class SpriteSystem:
    """Manages sprite expressions and maps them to image files."""

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

        logger.info(
            f"Loaded {len(self.expressions)} sprite expressions "
            f"(default: {self.default_expression})"
        )

    def get_sprite(self, expression: str) -> str:
        """
        Get sprite image path for expression.

        Args:
            expression: Expression name (e.g., "confident")

        Returns:
            Absolute path to sprite image.
            Falls back to default if expression not found.
        """
        # Get relative path from mapping (or use default)
        if expression not in self.expressions:
            logger.debug(
                f"Expression '{expression}' not found, using default '{self.default_expression}'"
            )
            expression = self.default_expression

        relative_path = self.expressions[expression]

        # Convert to absolute path
        absolute_path = self.sprites_dir / relative_path
        return str(absolute_path.resolve())
