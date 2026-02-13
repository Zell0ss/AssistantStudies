"""Weather provider implementation with OpenMeteo API integration"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from loguru import logger
import requests_cache
import numpy as np
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.prompts import (
    PromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    ChatPromptTemplate,
)
import os

from .base import BaseProvider
from .config import WeatherConfig


class WeatherProvider(BaseProvider, ABC):
    """Abstract weather provider interface"""

    @abstractmethod
    def get_current_weather(self, city: str) -> str:
        """Get current weather summary for city"""
        pass

    @abstractmethod
    def get_weather_report(self, city: str) -> str:
        """Get full weather report for city"""
        pass

    @abstractmethod
    def get_tools(self) -> list:
        """Return LangChain tools for this provider"""
        pass


class OpenMeteoWeatherProvider(WeatherProvider):
    """OpenMeteo weather provider implementation"""

    def __init__(self, config: WeatherConfig, chat_model: str = None):
        """
        Initialize OpenMeteo weather provider.

        Args:
            config: WeatherConfig with cities, cache_hours, refranes_file
            chat_model: Optional chat model name (defaults to env var OPENAI_CHAT_MODEL or gpt-4o)
        """
        # Call parent to trigger validation
        super().__init__(config)

        # Extract config values
        self.cities = config.cities
        self.cache_hours = config.cache_hours

        # Load refranes from file (UTF-8 encoded)
        with open(config.refranes_file, 'r', encoding='utf-8') as f:
            self.refranes = [line.rstrip() for line in f]

        # Set up cached session (retries handled by BaseProvider's _call_with_retry)
        self.cache_session = requests_cache.CachedSession('.cache', expire_after=self.cache_hours * 3600)
        self.session = self.cache_session  # No retry wrapping

        # Initialize chat model
        model_name = chat_model or os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
        self.chat_model = ChatOpenAI(model=model_name, temperature=0)

        logger.info(f"OpenMeteoWeatherProvider initialized with model: {model_name}")

    def health_check(self) -> bool:
        """
        Check if provider is healthy by fetching weather for first city.

        Returns:
            True if successful

        Raises:
            Exception if health check fails
        """
        try:
            first_city = list(self.cities.keys())[0]
            weather_data = self.get_current_weather(first_city)
            logger.info(f"Health check passed: Successfully fetched weather for {first_city}")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise

    def _get_random_refran(self) -> str:
        """Return random refran from loaded list"""
        return np.random.choice(self.refranes)

    def _fetch_weather_data(self, city: str) -> str:
        """
        Fetch weather data from OpenMeteo API.

        Args:
            city: City name (must be in configured cities)

        Returns:
            Formatted weather report in Spanish

        Raises:
            ValueError: If city not configured
        """
        # Validate city (case-insensitive)
        city_lower = city.lower()
        if city_lower not in self.cities:
            raise ValueError(f"City '{city}' not configured. Available cities: {list(self.cities.keys())}")

        # Get coordinates
        lat, lon = self.cities[city_lower]

        # Define API call function for retry wrapper
        def _api_call():
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": ["temperature_2m", "precipitation"],
                "daily": ["temperature_2m_max", "temperature_2m_min", "sunrise", "sunset", "precipitation_probability_max"],
                "forecast_days": 1
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()  # Raise exception for bad status codes
            return response.json()

        # Call API with retry logic from BaseProvider
        response = self._call_with_retry(_api_call)

        # Format response in Spanish (exact format from original implementation)
        report = f"Este es el resumen meteorológico para hoy en {city_lower}. \n"

        current = response["current"]
        report = report + f"Hora {current['time'][-5:]}. \n"
        report = report + f"Temperatura actual {current['temperature_2m']}. \n"
        report = report + f"Precipitacion actual {current['precipitation']}. \n"

        daily = response["daily"]
        daily_temp_max = daily['temperature_2m_max'][0]
        daily_temp_min = daily['temperature_2m_min'][0]
        daily_sunrise = daily['sunrise'][0][-5:]
        daily_sunset = daily['sunset'][0][-5:]
        daily_max_prob_precipitation = daily['precipitation_probability_max'][0]

        report = report + f"- temperatura máxima {daily_temp_max} \n- temperatura mínima {daily_temp_min}.\n- El amanecer sera a las {daily_sunrise} \n- El anochecer sera a las {daily_sunset}.\n"
        report = report + f"- La máxima probabilidad de precipitacion será del {daily_max_prob_precipitation}%. \n"
        report = report + "El refran para hoy es: " + self._get_random_refran()

        logger.debug(f"Fetched weather for {city_lower}: {daily_temp_min}°-{daily_temp_max}°")

        return report

    def get_current_weather(self, city: str = "madrid") -> str:
        """
        Get current weather summary for city.

        Args:
            city: City name (defaults to madrid)

        Returns:
            Weather report in Spanish
        """
        try:
            return self._fetch_weather_data(city)
        except Exception as e:
            logger.error(f"Failed to fetch weather for {city}: {e}")
            # Fallback message with just a refran (matches original behavior)
            return "No se ha podido obtener el reporte meteorológico. El refran para hoy es: " + self._get_random_refran()

    def get_weather_report(self, city: str = "madrid") -> str:
        """
        Get full weather report for city.
        For OpenMeteo, this is the same as get_current_weather.

        Args:
            city: City name (defaults to madrid)

        Returns:
            Weather report in Spanish
        """
        return self.get_current_weather(city)

    def _create_weather_summary_chain(self):
        """
        Create LangChain chain for weather summary.

        Returns:
            Chain that answers weather questions
        """
        system_template_str = "You are a meteorologist. Your job is to answer what will be today's weather. You know that today's weather forecast is provided in the context."

        system_prompt = SystemMessagePromptTemplate(
            prompt=PromptTemplate.from_template(system_template_str)
        )

        human_prompt = HumanMessagePromptTemplate(
            prompt=PromptTemplate.from_template("{question}")
        )

        messages = [system_prompt, human_prompt]
        template = ChatPromptTemplate.from_messages(messages)

        return template | self.chat_model

    def _create_weather_report_chain(self):
        """
        Create LangChain chain for weather report.

        Returns:
            Chain that creates newspaper-style weather columns
        """
        system_template_str = (
            "Como experto en redactar columnas meteorológicas atractivas para periódicos, "
            "tu tarea es crear una pieza cautivadora con el pronóstico del tiempo de hoy "
            "junto con un refrán relacionado. Combina el extracto meteorológico con el refrán "
            "para formar una columna concisa y entretenida que cautive a tus lectores. "
            "Considera incluir detalles como la vestimenta recomendada para el día, "
            "si la temperatura se ajusta a la estación actual y cualquier fenómeno "
            "meteorológico único que valga la pena mencionar. Tu columna no solo debe "
            "informar a los lectores sobre el clima del día, sino también engancharlos "
            "con un toque de creatividad y estilo. "
            "Redacta una narrativa que entrelace sin esfuerzo el pronóstico del tiempo, "
            "el refrán y observaciones adicionales para que tu columna sea tanto informativa "
            "como agradable de leer. Apunta a una extensión adecuada para una columna de periódico, "
            "brindando una visión general breve pero completa del clima del día mientras le imprimes "
            "personalidad y encanto. Deja que tu experiencia brille mientras entregas una columna "
            "meteorológica que no solo informe, sino que también entretenga e intrigue a tu audiencia. "
            "Prepárate para inspirar a tus lectores con una deliciosa combinación de información "
            "meteorológica y sabiduría literaria en la columna del clima de hoy."
        )

        system_prompt = SystemMessagePromptTemplate(
            prompt=PromptTemplate.from_template(system_template_str)
        )

        human_prompt = HumanMessagePromptTemplate(
            prompt=PromptTemplate.from_template("{question}")
        )

        messages = [system_prompt, human_prompt]
        template = ChatPromptTemplate.from_messages(messages)

        return template | self.chat_model

    def get_tools(self) -> list:
        """
        Return LangChain tools for this provider.

        Returns:
            List of Tool objects for weather summary and report
        """
        # Create chains
        summary_chain = self._create_weather_summary_chain()
        report_chain = self._create_weather_report_chain()

        # Define wrapper functions that fetch weather and invoke chains
        def weather_summary_func(question: str) -> str:
            """Answer weather questions with current data.

            Note: Currently hardcoded to Madrid for MVP. Future enhancement will
            extract city names from user questions.
            """
            weather_data = self.get_current_weather("madrid")
            # Combine weather data with question for context
            full_question = f"{question}\n\nContext: {weather_data}"
            result = summary_chain.invoke({"question": full_question})
            return result.content if hasattr(result, 'content') else str(result)

        def weather_report_func(question: str) -> str:
            """Generate full weather report.

            Note: Currently hardcoded to Madrid for MVP. Future enhancement will
            extract city names from user questions.
            """
            weather_data = self.get_weather_report("madrid")
            # Combine weather data with question for context
            full_question = f"{question}\n\nContext: {weather_data}"
            result = report_chain.invoke({"question": full_question})
            return result.content if hasattr(result, 'content') else str(result)

        # Create tools
        tools = [
            Tool(
                name="WeatherSummary",
                func=weather_summary_func,
                description="Use when asked about current weather today."
            ),
            Tool(
                name="WeatherReport",
                func=weather_report_func,
                description="Use when asked to make a complete report or an inspired piece, newspaper-like, about current weather today."
            )
        ]

        logger.debug(f"Created {len(tools)} weather tools")

        return tools
