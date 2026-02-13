"""Base configuration classes for providers"""
from abc import ABC, abstractmethod
from typing import Any


class ProviderConfig(ABC):
    """Base configuration class for all providers"""

    @abstractmethod
    def validate(self) -> bool:
        """
        Validate configuration values.

        Returns:
            True if valid (never False - raises instead)

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    def __repr__(self):
        """Safe repr without exposing secrets"""
        class_name = self.__class__.__name__
        attrs = {k: '***' if 'key' in k.lower() or 'token' in k.lower() or 'secret' in k.lower() else v
                 for k, v in self.__dict__.items()}
        return f"{class_name}({attrs})"
