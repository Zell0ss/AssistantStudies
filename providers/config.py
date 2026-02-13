"""Base configuration classes for providers"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import os


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


class WeatherConfig(ProviderConfig):
    """Configuration for weather provider"""

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """
        Initialize weather configuration.

        Args:
            config_dict: Optional configuration from config.yaml['weather']
        """
        config_dict = config_dict or {}

        # Default cities with coordinates
        default_cities = {
            "madrid": [40.4165, -3.7026],
            "gijón": [43.5357, -5.6615],
            "gijon": [43.5357, -5.6615],
            "oviedo": [43.3603, -5.8448],
            "magán": [39.9614, -3.9316],
            "magan": [39.9614, -3.9316]
        }

        # Load cities from config or use defaults
        self.cities: Dict[str, List[float]] = config_dict.get('cities', default_cities)

        # Cache hours (default 1 hour)
        self.cache_hours: int = config_dict.get('cache_hours', 1)

        # Refranes file path
        self.refranes_file: str = self._resolve_refranes_path(config_dict.get('refranes_file'))

    def _resolve_refranes_path(self, config_path: Optional[str]) -> str:
        """
        Resolve the path to refranes.txt file.

        Args:
            config_path: Optional path from config

        Returns:
            Resolved absolute path to refranes.txt
        """
        if config_path and os.path.exists(config_path):
            return os.path.abspath(config_path)

        # Fallback: resolve relative to module location
        # Assumes weather/refranes.txt exists relative to project root
        module_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(module_dir)
        fallback_path = os.path.join(project_root, 'weather', 'refranes.txt')

        return os.path.abspath(fallback_path)

    def validate(self) -> bool:
        """
        Validate weather configuration.

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid
            FileNotFoundError: If refranes.txt doesn't exist
        """
        # Check cities is not empty
        if not self.cities:
            raise ValueError("No cities configured")

        # Check cities is a dict
        if not isinstance(self.cities, dict):
            raise ValueError("Cities must be a dictionary")

        # Validate each city has valid coordinates
        for city_name, coords in self.cities.items():
            if not isinstance(coords, list):
                raise ValueError(f"City '{city_name}' coordinates must be a list")

            if len(coords) != 2:
                raise ValueError(f"City '{city_name}' must have exactly 2 coordinates (lat, lon)")

            if not all(isinstance(c, (int, float)) for c in coords):
                raise ValueError(f"City '{city_name}' coordinates must be numbers")

        # Check refranes file exists
        if not os.path.exists(self.refranes_file):
            raise FileNotFoundError(f"Refranes file not found: {self.refranes_file}")

        return True


class CalendarConfig(ProviderConfig):
    """Configuration for calendar provider"""

    def __init__(self, config_dict: dict):
        """
        Initialize calendar configuration.

        Args:
            config_dict: Dict from config.yaml['google_calendar']
        """
        self.service_account_file = config_dict.get('service_account_file')
        self.calendar_id = config_dict.get('calendar_id')
        self.scopes = config_dict.get('scopes', ['https://www.googleapis.com/auth/calendar'])

    def validate(self) -> bool:
        """Validate calendar configuration"""
        if not self.service_account_file:
            raise ValueError("CalendarConfig: service_account_file not specified")

        if not os.path.exists(self.service_account_file):
            raise FileNotFoundError(
                f"CalendarConfig: service account file not found: {self.service_account_file}"
            )

        if not self.calendar_id:
            raise ValueError("CalendarConfig: calendar_id not specified")

        return True
