"""Provider registry and base classes"""
from typing import Optional, Any, Dict
from loguru import logger

from .base import BaseProvider
from .config import (
    ProviderConfig,
    WeatherConfig,
    CalendarConfig,
    StorageConfig,
    TranscriptionConfig,
)
from .weather import OpenMeteoWeatherProvider
from .calendar import GoogleCalendarProvider
from .storage import StorageProvider
from .transcription import TranscriptionProvider


class ProviderRegistry:
    """
    Centralized registry for all providers.

    Handles:
    - Provider initialization from config
    - Health checks
    - Tool aggregation
    - Provider access by name
    """

    def __init__(self, config: dict):
        """
        Initialize provider registry.

        Args:
            config: Full application config dict
        """
        self.config = config
        self.providers: Dict[str, BaseProvider] = {}

        # Initialize and health check all providers
        self._initialize_providers()
        self._run_health_checks()

    def _initialize_providers(self):
        """
        Initialize all configured providers.

        Checks config for each provider type and initializes if present.
        Logs success/failure for each provider.
        """
        # Initialize weather provider if configured
        if 'weather' in self.config:
            try:
                weather_config = WeatherConfig(self.config['weather'])
                self.providers['weather'] = OpenMeteoWeatherProvider(weather_config)
                logger.debug("Weather provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize weather provider: {e}")

        # Initialize calendar provider if configured
        if 'google_calendar' in self.config:
            try:
                calendar_config = CalendarConfig(self.config['google_calendar'])
                self.providers['calendar'] = GoogleCalendarProvider(calendar_config)
                logger.debug("Calendar provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize calendar provider: {e}")

        # Initialize storage provider if configured
        if 'dropbox' in self.config:
            try:
                storage_config = StorageConfig(self.config['dropbox'])
                self.providers['storage'] = StorageProvider(storage_config)
                logger.debug("Storage provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize storage provider: {e}")

        # Initialize transcription provider if configured
        if 'openai_apikey' in self.config:
            try:
                transcription_config = TranscriptionConfig(self.config)
                self.providers['transcription'] = TranscriptionProvider(transcription_config)
                logger.debug("Transcription provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize transcription provider: {e}")

        # Log summary
        provider_names = list(self.providers.keys())
        logger.info(f"Initialized {len(provider_names)} providers: {provider_names}")

    def _run_health_checks(self):
        """
        Run health checks on all initialized providers.

        Logs success/failure for each provider.
        Non-fatal - warnings only, doesn't crash on failure.
        """
        for name, provider in self.providers.items():
            try:
                provider.health_check()
                logger.info(f"✓ {name} provider healthy")
            except Exception as e:
                logger.warning(f"✗ {name} provider health check failed: {e}")

    def get(self, name: str) -> Optional[Any]:
        """
        Get provider by name.

        Args:
            name: Provider name ('weather', 'calendar', 'storage', 'transcription')

        Returns:
            Provider instance or None if not initialized
        """
        return self.providers.get(name)

    def get_all_tools(self) -> list:
        """
        Aggregate tools from all providers.

        Returns:
            Combined list of all tools from all providers
        """
        all_tools = []

        for name, provider in self.providers.items():
            # Check if provider has get_tools method
            if hasattr(provider, 'get_tools') and callable(getattr(provider, 'get_tools')):
                try:
                    tools = provider.get_tools()
                    all_tools.extend(tools)
                    logger.debug(f"Loaded {len(tools)} tools from {name} provider")
                except Exception as e:
                    logger.error(f"Failed to get tools from {name} provider: {e}")

        logger.info(f"Total provider tools aggregated: {len(all_tools)}")
        return all_tools

    def list_providers(self) -> list[str]:
        """
        List all initialized provider names.

        Returns:
            List of provider names
        """
        return list(self.providers.keys())


__all__ = [
    'BaseProvider',
    'ProviderConfig',
    'WeatherConfig',
    'CalendarConfig',
    'StorageConfig',
    'TranscriptionConfig',
    'OpenMeteoWeatherProvider',
    'GoogleCalendarProvider',
    'StorageProvider',
    'TranscriptionProvider',
    'ProviderRegistry',
]
