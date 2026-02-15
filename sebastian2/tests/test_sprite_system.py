"""Tests for sprite system."""

import os
import pytest
from pathlib import Path
from sprites.sprite_system import SpriteSystem


class TestSpriteSystem:
    """Test sprite expression mapping system."""

    @pytest.fixture
    def sprite_system(self):
        """Create SpriteSystem instance."""
        return SpriteSystem()

    def test_load_sprite_mapping(self, sprite_system):
        """Test that sprite mapping loads correctly from YAML."""
        # Should have loaded expressions and default
        assert hasattr(sprite_system, 'expressions')
        assert hasattr(sprite_system, 'default_expression')
        assert len(sprite_system.expressions) >= 10
        assert sprite_system.default_expression == 'neutral'

    def test_get_sprite_returns_path(self, sprite_system):
        """Test that valid expression returns correct path."""
        path = sprite_system.get_sprite('confident')

        # Should return a string path
        assert isinstance(path, str)

        # Should end with the expected filename
        assert path.endswith('images/confident.png')

        # Should be an absolute path
        assert os.path.isabs(path)

    def test_get_sprite_fallback(self, sprite_system):
        """Test that unknown expression returns default sprite."""
        default_path = sprite_system.get_sprite('neutral')
        unknown_path = sprite_system.get_sprite('nonexistent_expression')

        # Both should return the same default sprite
        assert unknown_path == default_path
        assert unknown_path.endswith('images/neutral.png')

    def test_sprite_paths_are_absolute(self, sprite_system):
        """Test that all sprite paths are absolute."""
        test_expressions = ['neutral', 'thinking', 'confident', 'surprised']

        for expression in test_expressions:
            path = sprite_system.get_sprite(expression)
            assert os.path.isabs(path), f"Path for {expression} is not absolute: {path}"

            # Should contain the project directory
            assert '/sebastian2/sprites/' in path

    def test_all_defined_expressions(self, sprite_system):
        """Test that all required expressions are defined."""
        required_expressions = [
            'neutral', 'thinking', 'confident', 'surprised',
            'concerned', 'triumphant', 'confused', 'serious',
            'apologetic', 'deadpan'
        ]

        for expression in required_expressions:
            path = sprite_system.get_sprite(expression)
            assert path is not None
            assert isinstance(path, str)
            assert len(path) > 0
