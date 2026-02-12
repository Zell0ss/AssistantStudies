# Provider Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor Sebastian bot into modular provider architecture with retry logic, structured logging, and clear separation of production vs experimental code.

**Architecture:** Create base provider class with retry/logging, abstract providers for swappable services (weather, calendar), concrete providers for stable ones (storage, transcription), and central registry for initialization.

**Tech Stack:** Python 3.11+, loguru (logging), tenacity (retry), LangChain (agent framework), existing APIs (OpenMeteo, Google Calendar, Dropbox, OpenAI)

---

## Phase 1: Foundation (No Breaking Changes)

### Task 1: Project Structure Setup

**Files:**
- Create: `providers/__init__.py`
- Create: `providers/base.py`
- Create: `providers/config.py`
- Create: `utils/logging_config.py`
- Create: `experiments/.gitkeep`

**Step 1: Create providers package structure**

```bash
mkdir -p providers
touch providers/__init__.py
touch providers/base.py
touch providers/config.py
```

**Step 2: Create logging config**

Create `utils/logging_config.py`:

```python
"""Loguru logging configuration for Sebastian bot"""
from loguru import logger
import sys


def setup_logging(log_folder: str = "logs", level: str = "INFO"):
    """
    Configure loguru for the application.

    Args:
        log_folder: Directory for log files
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove default handler
    logger.remove()

    # Console output (colorized, user-friendly)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True
    )

    # File output (detailed for debugging)
    logger.add(
        f"{log_folder}/app.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="1 month",
        compression="zip",
        enqueue=True  # Thread-safe
    )

    # Error-only file (critical issues)
    logger.add(
        f"{log_folder}/errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
        level="ERROR",
        rotation="10 MB",
        retention="3 months",
        compression="zip",
        enqueue=True
    )

    logger.info("Logging system initialized")
    return logger
```

**Step 3: Create experiments directory and move test files**

```bash
mkdir -p experiments/legacytests
mv tester.py experiments/
mv test_oauth.py experiments/
mv tester.ipynb experiments/
mv agent_creation.ipynb experiments/
mv legacytests/* experiments/legacytests/
touch experiments/.gitkeep
```

**Step 4: Update requirements.txt**

Add to `requirements.txt`:

```
loguru
tenacity
```

**Step 5: Install new dependencies**

```bash
pip install loguru tenacity
```

**Step 6: Commit foundation**

```bash
git add providers/ utils/logging_config.py experiments/ requirements.txt
git add -u  # Track moved/deleted files
git commit -m "feat: create provider foundation structure

- Create providers package with base/config modules
- Add loguru logging configuration
- Move experimental code to experiments/ directory
- Add loguru and tenacity dependencies

Phase 1/5 of provider refactoring"
```

---

### Task 2: Base Provider Class

**Files:**
- Modify: `providers/base.py`
- Modify: `providers/config.py`

**Step 1: Implement ProviderConfig base class**

In `providers/config.py`:

```python
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
            True if valid

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
```

**Step 2: Implement BaseProvider with retry logic**

In `providers/base.py`:

```python
"""Base provider class with retry logic and logging"""
from abc import ABC, abstractmethod
from typing import Any, Callable, TypeVar
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)
import requests.exceptions

# Type for retry wrapper
T = TypeVar('T')

# Transient errors that should be retried
TRANSIENT_ERRORS = (
    requests.exceptions.RequestException,
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    ConnectionResetError,
    TimeoutError,
)


class BaseProvider(ABC):
    """
    Base class for all providers with retry logic and structured logging.

    Providers should inherit from this and implement:
    - __init__: Initialize provider with config
    - health_check: Verify provider is working
    """

    def __init__(self, config):
        """Initialize provider with configuration"""
        self.config = config
        self.config.validate()
        logger.info(f"Initialized {self.__class__.__name__}")

    def _call_with_retry(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with automatic retry for transient errors.

        Retries 3 times with exponential backoff (2s → 4s → 8s) for:
        - Network errors
        - Connection timeouts
        - Temporary API failures

        Fails immediately for:
        - Authentication errors
        - Validation errors
        - Configuration errors

        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            Original exception if retries exhausted or non-transient error
        """
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(TRANSIENT_ERRORS),
            reraise=True
        )
        def _retry_wrapper():
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{self.__class__.__name__}.{func.__name__}: Call successful")
                return result
            except TRANSIENT_ERRORS as e:
                logger.warning(
                    f"{self.__class__.__name__}.{func.__name__}: "
                    f"Transient error (will retry): {type(e).__name__}: {e}"
                )
                raise  # Let tenacity handle retry
            except Exception as e:
                logger.error(
                    f"{self.__class__.__name__}.{func.__name__}: "
                    f"Non-transient error (failing fast): {type(e).__name__}: {e}"
                )
                raise  # Don't retry, fail immediately

        try:
            return _retry_wrapper()
        except RetryError as e:
            logger.error(
                f"{self.__class__.__name__}.{func.__name__}: "
                f"Failed after 3 retries: {e.last_attempt.exception()}"
            )
            raise e.last_attempt.exception()

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if provider is healthy and properly configured.

        Returns:
            True if provider is working

        Raises:
            Exception if provider is unhealthy
        """
        pass
```

**Step 3: Test base provider (manual verification)**

Create temporary test script `test_base_provider.py` (will delete):

```python
from providers.base import BaseProvider
from providers.config import ProviderConfig

class TestConfig(ProviderConfig):
    def __init__(self):
        self.test_value = "test"

    def validate(self):
        return True

class TestProvider(BaseProvider):
    def health_check(self):
        return True

# Should initialize without error
config = TestConfig()
provider = TestProvider(config)
print(f"✓ Provider initialized: {provider}")
print(f"✓ Config repr safe: {config}")
```

Run:
```bash
python test_base_provider.py
```

Expected output:
```
✓ Provider initialized: <TestProvider object>
✓ Config repr safe: TestConfig({'test_value': 'test'})
```

**Step 4: Clean up test and commit**

```bash
rm test_base_provider.py
git add providers/base.py providers/config.py
git commit -m "feat: implement BaseProvider with retry logic

- Add ProviderConfig ABC for configuration validation
- Add BaseProvider with _call_with_retry method
- Retry transient errors (network, timeout) 3 times
- Fail fast on auth/config errors
- Safe repr for configs (hide secrets)

Phase 1/5 of provider refactoring"
```

---

## Phase 2: Weather Provider (Pilot Migration)

### Task 3: Weather Provider Configuration

**Files:**
- Modify: `providers/config.py`
- Reference: `weather/openmeteo.py` (for current config structure)

**Step 1: Add WeatherConfig class**

Add to `providers/config.py`:

```python
import os


class WeatherConfig(ProviderConfig):
    """Configuration for weather provider"""

    def __init__(self, config_dict: dict = None):
        """
        Initialize weather configuration.

        Args:
            config_dict: Dict from config.yaml['weather'], optional
        """
        if config_dict is None:
            config_dict = {}

        self.cities = config_dict.get('cities', {
            "madrid": [40.4165, -3.7026],
            "gijón": [43.5357, -5.6615],
            "gijon": [43.5357, -5.6615],
            "oviedo": [43.3603, -5.8448],
            "magán": [39.9614, -3.9316],
            "magan": [39.9614, -3.9316]
        })

        self.cache_hours = config_dict.get('cache_hours', 1)

        # Find refranes.txt file
        refranes_file = config_dict.get('refranes_file', 'weather/refranes.txt')
        if os.path.exists(refranes_file):
            self.refranes_file = refranes_file
        else:
            # Fallback: try relative to this file
            self.refranes_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'weather',
                'refranes.txt'
            )

    def validate(self) -> bool:
        """Validate weather configuration"""
        if not self.cities:
            raise ValueError("WeatherConfig: No cities configured")

        if not isinstance(self.cities, dict):
            raise ValueError("WeatherConfig: cities must be a dict")

        for city, coords in self.cities.items():
            if not isinstance(coords, list) or len(coords) != 2:
                raise ValueError(
                    f"WeatherConfig: City '{city}' has invalid coordinates: {coords}"
                )

        if not os.path.exists(self.refranes_file):
            raise FileNotFoundError(
                f"WeatherConfig: refranes.txt not found at {self.refranes_file}"
            )

        return True
```

**Step 2: Test configuration**

Create `test_weather_config.py`:

```python
from providers.config import WeatherConfig

# Test default config
config = WeatherConfig()
assert config.validate()
print(f"✓ Default config valid")
print(f"  Cities: {list(config.cities.keys())}")
print(f"  Cache hours: {config.cache_hours}")

# Test custom config
custom = WeatherConfig({
    'cities': {'test_city': [1.23, 4.56]},
    'cache_hours': 2
})
assert custom.validate()
print(f"✓ Custom config valid")

# Test validation error
try:
    bad = WeatherConfig({'cities': {}})
    bad.validate()
    print("✗ Should have raised ValueError")
except ValueError as e:
    print(f"✓ Validation correctly failed: {e}")

print("\n✓ All weather config tests passed")
```

Run:
```bash
python test_weather_config.py
```

Expected: All tests pass

**Step 3: Commit weather config**

```bash
rm test_weather_config.py
git add providers/config.py
git commit -m "feat: add WeatherConfig with validation

- Load cities from config.yaml or use defaults
- Validate cities structure and coordinates
- Locate refranes.txt file
- Validate file exists

Phase 2/5 of provider refactoring"
```

---

### Task 4: Weather Provider Implementation

**Files:**
- Create: `providers/weather.py`
- Reference: `weather/openmeteo.py` (migrate logic from here)
- Reference: `tools.py` (migrate weather chains from here)

**Step 1: Create abstract WeatherProvider**

Create `providers/weather.py`:

```python
"""Weather provider with OpenMeteo implementation"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from loguru import logger
import requests_cache
from retry_requests import retry as retry_requests
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
```

**Step 2: Implement OpenMeteoWeatherProvider**

Add to `providers/weather.py`:

```python
class OpenMeteoWeatherProvider(WeatherProvider):
    """OpenMeteo weather API implementation"""

    def __init__(self, config: WeatherConfig, chat_model: str = None):
        """
        Initialize OpenMeteo weather provider.

        Args:
            config: WeatherConfig instance
            chat_model: OpenAI model for chains (from env if None)
        """
        super().__init__(config)

        self.cities = config.cities
        self.cache_hours = config.cache_hours

        # Load Spanish weather sayings
        with open(config.refranes_file, 'r', encoding='utf-8') as f:
            self.refranes = [line.rstrip() for line in f if line.strip()]

        logger.info(f"Loaded {len(self.refranes)} refranes from {config.refranes_file}")

        # Set up caching session
        self.cache_session = requests_cache.CachedSession(
            '.cache',
            expire_after=config.cache_hours * 3600
        )
        self.retry_session = retry_requests(
            self.cache_session,
            retries=5,
            backoff_factor=0.2
        )

        # Set up LangChain chat model for chains
        self.chat_model_name = chat_model or os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
        self.chat_model = ChatOpenAI(model=self.chat_model_name, temperature=0)

        logger.info(f"Initialized OpenMeteo provider with model {self.chat_model_name}")

    def health_check(self) -> bool:
        """Verify provider can access OpenMeteo API"""
        try:
            # Try to fetch weather for first configured city
            test_city = list(self.cities.keys())[0]
            result = self.get_current_weather(test_city)
            logger.info(f"Weather provider health check passed: {test_city}")
            return True
        except Exception as e:
            logger.error(f"Weather provider health check failed: {e}")
            raise

    def _get_random_refran(self) -> str:
        """Get random Spanish weather saying"""
        return np.random.choice(self.refranes)

    def _fetch_weather_data(self, city: str) -> str:
        """
        Fetch weather data from OpenMeteo API.

        Returns formatted weather report string.
        """
        city_lower = city.lower()
        if city_lower not in self.cities:
            raise ValueError(f"City '{city}' not configured. Available: {list(self.cities.keys())}")

        lat, lon = self.cities[city_lower]

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ["temperature_2m", "precipitation"],
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "sunrise",
                "sunset",
                "precipitation_probability_max"
            ],
            "forecast_days": 1
        }

        # Use retry wrapper for API call
        def _api_call():
            response = self.retry_session.get(url, params=params)
            response.raise_for_status()
            return response.json()

        data = self._call_with_retry(_api_call)

        # Format response
        report = f"Este es el resumen meteorológico para hoy en {city}. \n"

        current = data["current"]
        report += f"Hora {current['time'][-5:]}. \n"
        report += f"Temperatura actual {current['temperature_2m']}°C. \n"
        report += f"Precipitación actual {current['precipitation']}mm. \n"

        daily = data["daily"]
        daily_temp_max = daily['temperature_2m_max'][0]
        daily_temp_min = daily['temperature_2m_min'][0]
        daily_sunrise = daily['sunrise'][0][-5:]
        daily_sunset = daily['sunset'][0][-5:]
        daily_max_prob_precipitation = daily['precipitation_probability_max'][0]

        report += f"- temperatura máxima {daily_temp_max}°C \n"
        report += f"- temperatura mínima {daily_temp_min}°C.\n"
        report += f"- El amanecer será a las {daily_sunrise} \n"
        report += f"- El anochecer será a las {daily_sunset}.\n"
        report += f"- La máxima probabilidad de precipitación será del {daily_max_prob_precipitation}%. \n"
        report += "El refrán para hoy es: " + self._get_random_refran()

        logger.debug(f"Fetched weather for {city}: {daily_temp_min}°C - {daily_temp_max}°C")

        return report

    def get_current_weather(self, city: str = "madrid") -> str:
        """Get current weather summary for city"""
        try:
            return self._fetch_weather_data(city)
        except Exception as e:
            logger.error(f"Failed to fetch weather for {city}: {e}")
            return (
                f"No se pudo obtener el reporte meteorológico para {city}. "
                f"El refrán para hoy es: {self._get_random_refran()}"
            )

    def get_weather_report(self, city: str = "madrid") -> str:
        """Get full weather report (same as current for OpenMeteo)"""
        return self.get_current_weather(city)

    def _create_weather_summary_chain(self):
        """Create LangChain chain for weather summaries"""
        system_template_str = (
            f"You are a meteorologist. Your job is to answer what will be today's weather. "
            f"You know that today's weather forecast is provided in the context."
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

    def _create_weather_report_chain(self):
        """Create LangChain chain for full weather reports"""
        system_template_str = (
            "Como experto en redactar columnas meteorológicas atractivas para periódicos, "
            "tu tarea es crear una pieza cautivadora con el pronóstico del tiempo de hoy "
            "junto con un refrán relacionado. Combina el extracto meteorológico con el refrán "
            "para formar una columna concisa y entretenida que cautive a tus lectores."
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
        """Return LangChain tools for weather operations"""
        weather_summary_chain = self._create_weather_summary_chain()
        weather_report_chain = self._create_weather_report_chain()

        def weather_summary_func(question: str) -> str:
            """Answer weather questions with current data"""
            weather_data = self.get_current_weather()
            context_question = f"Weather data: {weather_data}\n\nQuestion: {question}"
            return weather_summary_chain.invoke({"question": context_question}).content

        def weather_report_func(question: str) -> str:
            """Generate full weather report"""
            weather_data = self.get_weather_report()
            context_question = f"Weather data: {weather_data}\n\nQuestion: {question}"
            return weather_report_chain.invoke({"question": context_question}).content

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
```

**Step 3: Test weather provider (manual)**

Create `test_weather_provider.py`:

```python
import os
from dotenv import load_dotenv
from providers.config import WeatherConfig
from providers.weather import OpenMeteoWeatherProvider

load_dotenv()

# Test initialization
config = WeatherConfig()
provider = OpenMeteoWeatherProvider(config)
print(f"✓ Provider initialized")

# Test weather fetch
weather = provider.get_current_weather("madrid")
print(f"✓ Weather fetched for Madrid")
print(f"  Preview: {weather[:100]}...")

# Test tools
tools = provider.get_tools()
print(f"✓ Created {len(tools)} tools")
for tool in tools:
    print(f"  - {tool.name}: {tool.description}")

# Test health check
assert provider.health_check()
print(f"✓ Health check passed")

print("\n✓ All weather provider tests passed")
```

Run:
```bash
python test_weather_provider.py
```

Expected: All tests pass, weather data retrieved

**Step 4: Commit weather provider**

```bash
rm test_weather_provider.py
git add providers/weather.py
git commit -m "feat: implement OpenMeteo weather provider

- Abstract WeatherProvider interface
- OpenMeteoWeatherProvider with retry logic
- Migrated logic from weather/openmeteo.py
- LangChain tools for WeatherSummary and WeatherReport
- Health check implementation

Phase 2/5 of provider refactoring"
```

---

### Task 5: Integrate Weather Provider with Agent

**Files:**
- Modify: `sebastian_agent.py`
- Modify: `config.yaml` (add weather section)
- Keep: `weather/openmeteo.py` (for now, as backup)

**Step 1: Add weather section to config.yaml**

Add to `config.yaml`:

```yaml
# Weather provider configuration
weather:
  cache_hours: 1
  cities:
    madrid: [40.4165, -3.7026]
    gijón: [43.5357, -5.6615]
    gijon: [43.5357, -5.6615]
    oviedo: [43.3603, -5.8448]
    magán: [39.9614, -3.9316]
    magan: [39.9614, -3.9316]
  refranes_file: weather/refranes.txt
```

**Step 2: Update sebastian_agent.py to use weather provider**

Modify `sebastian_agent.py`:

```python
import dotenv
import os
from langchain import hub
from langchain_openai import ChatOpenAI
from langchain.agents import (
    create_openai_functions_agent,
    AgentExecutor,
)
from loguru import logger

# Import provider system
from providers.config import WeatherConfig
from providers.weather import OpenMeteoWeatherProvider
from utils.logging_config import setup_logging
from utils.utils import config

# Import tools (will be updated later to exclude weather)
from tools import get_tools

"""
Creates a LangChain-based AI agent called "Sebastian" that can use tools to answer questions.
Now using modular provider system for weather functionality.
"""

# Initialize logging
setup_logging(log_folder=config.get("logfolder", "logs"))

dotenv.load_dotenv()
AGENT_MODEL = os.getenv("OPENAI_AGENT_MODEL")
chat_model = ChatOpenAI(model=AGENT_MODEL, temperature=0)

agent_prompt = hub.pull("hwchase17/openai-functions-agent")

# Initialize weather provider if configured
weather_provider = None
weather_tools = []
if 'weather' in config:
    try:
        weather_config = WeatherConfig(config['weather'])
        weather_provider = OpenMeteoWeatherProvider(weather_config)
        weather_tools = weather_provider.get_tools()
        logger.info(f"Weather provider initialized with {len(weather_tools)} tools")
    except Exception as e:
        logger.error(f"Failed to initialize weather provider: {e}")
        weather_provider = None
        weather_tools = []

# Get legacy tools (includes weather for now - will be removed later)
legacy_tools = get_tools()

# Combine all tools (during migration, weather tools from both sources)
all_tools = legacy_tools + weather_tools

logger.info(f"Total tools available: {len(all_tools)}")

"""
An agent needs both the agent and the agent executor
"""
sebastian_agent = create_openai_functions_agent(
    llm=chat_model,
    prompt=agent_prompt,
    tools=all_tools,
)

sebastian_agent_executor = AgentExecutor(
    agent=sebastian_agent,
    tools=all_tools,
    return_intermediate_steps=True,
    verbose=True,
)

def get_sebastian_answer(question):
    """Get answer from Sebastian agent"""
    logger.info(f"Processing question: {question[:50]}...")
    response = sebastian_agent_executor.invoke({"input": question})
    logger.info("Response generated")
    return response["output"]
```

**Step 3: Test agent with weather provider**

```bash
python sebastian_bot.py
```

In another terminal, send test message to bot:
- "¿Qué tiempo hace hoy en Madrid?"

Expected: Bot responds with weather, logs show "Weather provider initialized"

**Step 4: Verify logs**

Check `logs/app.log`:
```bash
tail -20 logs/app.log
```

Expected to see:
- "Logging system initialized"
- "Initialized OpenMeteoWeatherProvider"
- "Weather provider initialized with 2 tools"

**Step 5: Commit weather integration**

```bash
git add sebastian_agent.py config.yaml
git commit -m "feat: integrate weather provider with agent

- Add weather section to config.yaml
- Initialize WeatherProvider in sebastian_agent.py
- Set up loguru logging
- Combine provider tools with legacy tools
- Log provider initialization

Phase 2/5 of provider refactoring (pilot complete)"
```

---

## Phase 3: Migrate Remaining Providers

### Task 6: Calendar Provider

**Files:**
- Create: `providers/calendar.py`
- Modify: `providers/config.py`
- Reference: `mycalendar/googlecal.py`

**Step 1: Add CalendarConfig**

Add to `providers/config.py`:

```python
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
```

**Step 2: Create calendar provider**

Create `providers/calendar.py`:

```python
"""Calendar provider with Google Calendar implementation"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from loguru import logger
from google.oauth2 import service_account
from googleapiclient.discovery import build

from .base import BaseProvider
from .config import CalendarConfig


class CalendarProvider(BaseProvider, ABC):
    """Abstract calendar provider interface"""

    @abstractmethod
    def get_events(self, days_ahead: int = 1) -> str:
        """Get events for next N days"""
        pass


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar API implementation"""

    def __init__(self, config: CalendarConfig):
        """Initialize Google Calendar provider"""
        super().__init__(config)

        # Initialize service account credentials
        self.credentials = service_account.Credentials.from_service_account_file(
            config.service_account_file,
            scopes=config.scopes
        )

        # Build calendar service
        self.service = build('calendar', 'v3', credentials=self.credentials)
        self.calendar_id = config.calendar_id

        logger.info(f"Initialized Google Calendar provider for {config.calendar_id}")

    def health_check(self) -> bool:
        """Verify can access calendar"""
        try:
            # Try to get calendar info
            calendar = self.service.calendars().get(calendarId=self.calendar_id).execute()
            logger.info(f"Calendar provider health check passed: {calendar.get('summary', self.calendar_id)}")
            return True
        except Exception as e:
            logger.error(f"Calendar provider health check failed: {e}")
            raise

    def get_events(self, days_ahead: int = 1) -> str:
        """
        Get events for the next N days.

        Args:
            days_ahead: Number of days to look ahead (default 1 = tomorrow)

        Returns:
            Formatted string with events
        """
        try:
            target_date = datetime.now() + timedelta(days=days_ahead)
            fecha_hoy = datetime.now().date().isoformat()
            fecha_target = target_date.date().isoformat()

            def _fetch_events():
                return self.service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=fecha_hoy + 'T00:00:00Z',
                    timeMax=fecha_target + 'T23:59:59Z'
                ).execute()

            # Use retry wrapper for API call
            eventos = self._call_with_retry(_fetch_events)

            # Format events
            eventos_str = ""
            if eventos.get('items'):
                for evento in eventos['items']:
                    eventos_str += f'Título: {evento.get("summary", "Sin título")} \n'
                    if evento['start'].get('date'):
                        eventos_str += f'Fecha: {evento["start"].get("date")} \n'
                    else:
                        eventos_str += f'Fecha: {evento["start"].get("dateTime", "")[:16]} \n'

                logger.info(f"Found {len(eventos['items'])} events")
                return eventos_str
            else:
                logger.info("No events found")
                return 'No hay eventos programados entre hoy y mañana.'

        except Exception as e:
            logger.error(f"Failed to fetch calendar events: {e}")
            return f"Error obteniendo eventos del calendario: {str(e)}"
```

**Step 3: Add to config.yaml**

Add to `config.yaml`:

```yaml
# Google Calendar provider configuration
google_calendar:
  service_account_file: mycalendar/Zell0ss_api-access.json
  calendar_id: zelloss@gmail.com
```

**Step 4: Update sebastian_agent.py**

Add to `sebastian_agent.py` after weather provider initialization:

```python
from providers.config import CalendarConfig
from providers.calendar import GoogleCalendarProvider

# Initialize calendar provider if configured
calendar_provider = None
if 'google_calendar' in config:
    try:
        calendar_config = CalendarConfig(config['google_calendar'])
        calendar_provider = GoogleCalendarProvider(calendar_config)
        logger.info("Calendar provider initialized")
    except Exception as e:
        logger.error(f"Failed to initialize calendar provider: {e}")
        calendar_provider = None
```

**Step 5: Update sebastian_bot.py calendar command**

Modify the `/calendario` handler in `sebastian_bot.py`:

```python
from sebastian_agent import calendar_provider  # Import provider

@bot.message_handler(commands=['calendario'])
def send_calendar(message):
    if authorized(message.chat.username, message.chat.id):
        try:
            if calendar_provider:
                events = calendar_provider.get_events()
            else:
                # Fallback to old implementation
                from mycalendar.googlecal import get_events
                events = get_events()
            bot.reply_to(message, events)
        except Exception as e:
            logger.error(f"Calendar command failed: {e}")
            bot.reply_to(message, f"❌ Error obteniendo calendario: {str(e)}")
```

**Step 6: Test calendar**

```bash
python sebastian_bot.py
```

Send `/calendario` command to bot.

Expected: Events listed, logs show "Calendar provider initialized"

**Step 7: Commit calendar provider**

```bash
git add providers/calendar.py providers/config.py sebastian_agent.py sebastian_bot.py config.yaml
git commit -m "feat: add Google Calendar provider

- Abstract CalendarProvider interface
- GoogleCalendarProvider with retry logic
- Migrated from mycalendar/googlecal.py
- Integrated with sebastian_agent.py
- Updated /calendario command to use provider
- Added google_calendar config section

Phase 3/5 of provider refactoring"
```

---

### Task 7: Storage Provider (Dropbox)

**Files:**
- Create: `providers/storage.py`
- Modify: `providers/config.py`
- Reference: `mydropbox/upload_dropbox.py`

**Step 1: Add StorageConfig**

Add to `providers/config.py`:

```python
class StorageConfig(ProviderConfig):
    """Configuration for storage provider (Dropbox)"""

    def __init__(self, config_dict: dict):
        """
        Initialize storage configuration.

        Args:
            config_dict: Dict from config.yaml['dropbox']
        """
        self.refresh_token = config_dict.get('refresh_token')
        self.app_key = config_dict.get('app_key')
        self.app_secret = config_dict.get('app_secret')
        self.app_name = config_dict.get('app_name', 'SebastianAssistant')

    def validate(self) -> bool:
        """Validate storage configuration"""
        if not self.refresh_token:
            raise ValueError("StorageConfig: refresh_token not specified")

        if not self.app_key:
            raise ValueError("StorageConfig: app_key not specified")

        if not self.app_secret:
            raise ValueError("StorageConfig: app_secret not specified")

        return True
```

**Step 2: Create storage provider**

Create `providers/storage.py`:

```python
"""Storage provider with Dropbox implementation"""
from loguru import logger
import dropbox
from dropbox.files import WriteMode

from .base import BaseProvider
from .config import StorageConfig


class StorageProvider(BaseProvider):
    """Dropbox storage provider (concrete, not abstract)"""

    def __init__(self, config: StorageConfig):
        """Initialize Dropbox storage provider"""
        super().__init__(config)

        # Initialize Dropbox client with refresh token
        self.dbx = dropbox.Dropbox(
            oauth2_refresh_token=config.refresh_token,
            app_key=config.app_key,
            app_secret=config.app_secret
        )

        self.app_name = config.app_name

        logger.info(f"Initialized Dropbox storage provider ({config.app_name})")

    def health_check(self) -> bool:
        """Verify can access Dropbox account"""
        try:
            account = self.dbx.users_get_current_account()
            logger.info(f"Storage provider health check passed: {account.name.display_name}")
            return True
        except Exception as e:
            logger.error(f"Storage provider health check failed: {e}")
            raise

    def upload_file(self, file_blob: bytes, file_name: str, folder: str = "intercambio") -> dict:
        """
        Upload file to Dropbox.

        Args:
            file_blob: File content as bytes
            file_name: Name for the file
            folder: Subfolder in "Espacio familiar" (default: intercambio)

        Returns:
            Upload metadata dict
        """
        target_path = f"/Espacio familiar/{folder}/{file_name}"

        def _upload():
            return self.dbx.files_upload(
                file_blob,
                target_path,
                mode=WriteMode("overwrite")
            )

        try:
            # Use retry wrapper for upload
            metadata = self._call_with_retry(_upload)
            logger.info(f"Uploaded file to Dropbox: {target_path}")
            return {
                'path': metadata.path_display,
                'size': metadata.size,
                'modified': metadata.client_modified.isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to upload file to Dropbox: {e}")
            raise
```

**Step 3: Update sebastian_agent.py**

Add to `sebastian_agent.py` after calendar provider:

```python
from providers.config import StorageConfig
from providers.storage import StorageProvider

# Initialize storage provider if configured
storage_provider = None
if 'dropbox' in config:
    try:
        storage_config = StorageConfig(config['dropbox'])
        storage_provider = StorageProvider(storage_config)
        logger.info("Storage provider initialized")
    except Exception as e:
        logger.error(f"Failed to initialize storage provider: {e}")
        storage_provider = None
```

**Step 4: Update sebastian_bot.py document handler**

Modify document upload handler in `sebastian_bot.py`:

```python
from sebastian_agent import storage_provider  # Import provider

@bot.message_handler(
    func=lambda message: classify_text_mimetype(message.document.mime_type) != 'unk',
    content_types=['document']
)
def command_handle_document(message):
    if authorized(message.chat.username, message.chat.id):
        try:
            # Get folder from caption or default
            if hasattr(message, "caption") and message.caption:
                folder = message.caption
            elif hasattr(message, "html_caption") and message.html_caption:
                folder = message.html_caption
            else:
                folder = "intercambio"

            name = message.document.file_name

            # Retrieve file from Telegram
            remote_name = retrieve_telegram_file_address(message.document.file_id)
            das_file = retrieve_telegram_file(remote_name)

            # Upload using provider if available
            if storage_provider:
                metadata = storage_provider.upload_file(
                    file_blob=das_file,
                    file_name=name,
                    folder=folder
                )
                response = f'✓ Documento subido a Dropbox: Espacio familiar/{folder}/{name}'
            else:
                # Fallback to old implementation
                from mydropbox.upload_dropbox import upload_file_dbx
                upload_file_dbx(file_blob=das_file, file_name=name, folder=folder)
                response = f'Documento subido a {remote_name} depositado en dropbox Espacio familiar/{folder}/{name}'

            bot.send_message(message.chat.id, response)

        except Exception as e:
            logger.error(f"Document upload failed: {e}")
            bot.send_message(message.chat.id, f"❌ Error subiendo documento: {str(e)}")
```

**Step 5: Test file upload**

Start bot and send a test document with caption "test".

Expected: File uploaded to Dropbox, logs show "Uploaded file to Dropbox"

**Step 6: Commit storage provider**

```bash
git add providers/storage.py providers/config.py sebastian_agent.py sebastian_bot.py
git commit -m "feat: add Dropbox storage provider

- Concrete StorageProvider (no abstraction needed)
- Migrated from mydropbox/upload_dropbox.py
- Integrated with sebastian_agent.py
- Updated document handler to use provider
- Retry logic for uploads

Phase 3/5 of provider refactoring"
```

---

### Task 8: Transcription Provider (Whisper)

**Files:**
- Create: `providers/transcription.py`
- Modify: `providers/config.py`
- Reference: `mp3totext/whisper_openai.py`

**Step 1: Add TranscriptionConfig**

Add to `providers/config.py`:

```python
class TranscriptionConfig(ProviderConfig):
    """Configuration for transcription provider (Whisper)"""

    def __init__(self, config_dict: dict):
        """
        Initialize transcription configuration.

        Args:
            config_dict: Dict from config.yaml (needs openai_apikey)
        """
        self.api_key = config_dict.get('openai_apikey')

    def validate(self) -> bool:
        """Validate transcription configuration"""
        if not self.api_key:
            raise ValueError("TranscriptionConfig: openai_apikey not specified")

        return True
```

**Step 2: Create transcription provider**

Create `providers/transcription.py`:

```python
"""Transcription provider with OpenAI Whisper implementation"""
from loguru import logger
from openai import OpenAI

from .base import BaseProvider
from .config import TranscriptionConfig


class TranscriptionProvider(BaseProvider):
    """OpenAI Whisper transcription provider (concrete, not abstract)"""

    def __init__(self, config: TranscriptionConfig):
        """Initialize Whisper transcription provider"""
        super().__init__(config)

        # Initialize OpenAI client
        self.client = OpenAI(api_key=config.api_key)

        logger.info("Initialized Whisper transcription provider")

    def health_check(self) -> bool:
        """Verify OpenAI API key is valid"""
        try:
            # Simple API check
            models = self.client.models.list()
            logger.info("Transcription provider health check passed")
            return True
        except Exception as e:
            logger.error(f"Transcription provider health check failed: {e}")
            raise

    def transcribe_audio(self, audio_file_path: str, language: str = None) -> str:
        """
        Transcribe audio file using Whisper.

        Args:
            audio_file_path: Path to audio file
            language: Language code (e.g., 'es', 'en'), auto-detect if None

        Returns:
            Transcribed text
        """
        def _transcribe():
            with open(audio_file_path, 'rb') as audio_file:
                kwargs = {'file': audio_file, 'model': 'whisper-1'}
                if language:
                    kwargs['language'] = language

                transcript = self.client.audio.transcriptions.create(**kwargs)
                return transcript.text

        try:
            # Use retry wrapper for API call
            text = self._call_with_retry(_transcribe)
            logger.info(f"Transcribed audio: {audio_file_path} ({len(text)} chars)")
            return text
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            raise
```

**Step 3: Update sebastian_agent.py**

Add to `sebastian_agent.py` after storage provider:

```python
from providers.config import TranscriptionConfig
from providers.transcription import TranscriptionProvider

# Initialize transcription provider if configured
transcription_provider = None
if 'openai_apikey' in config:
    try:
        transcription_config = TranscriptionConfig(config)
        transcription_provider = TranscriptionProvider(transcription_config)
        logger.info("Transcription provider initialized")
    except Exception as e:
        logger.error(f"Failed to initialize transcription provider: {e}")
        transcription_provider = None
```

**Step 4: Commit transcription provider**

```bash
git add providers/transcription.py providers/config.py sebastian_agent.py
git commit -m "feat: add Whisper transcription provider

- Concrete TranscriptionProvider (no abstraction needed)
- Migrated from mp3totext/whisper_openai.py
- Integrated with sebastian_agent.py
- Retry logic for API calls

Phase 3/5 of provider refactoring"
```

---

## Phase 4: Provider Registry & Cleanup

### Task 9: Provider Registry

**Files:**
- Modify: `providers/__init__.py`
- Modify: `sebastian_agent.py`

**Step 1: Implement ProviderRegistry**

Update `providers/__init__.py`:

```python
"""Provider registry for centralized initialization"""
from loguru import logger
from typing import Optional, Dict, Any

from .config import (
    WeatherConfig,
    CalendarConfig,
    StorageConfig,
    TranscriptionConfig
)
from .weather import OpenMeteoWeatherProvider
from .calendar import GoogleCalendarProvider
from .storage import StorageProvider
from .transcription import TranscriptionProvider


class ProviderRegistry:
    """
    Centralized registry for all providers.

    Handles initialization, health checks, and tool aggregation.
    """

    def __init__(self, config: dict):
        """
        Initialize all configured providers.

        Args:
            config: Global config dict from config.yaml
        """
        self.config = config
        self.providers: Dict[str, Any] = {}
        self._initialize_providers()
        self._run_health_checks()

    def _initialize_providers(self):
        """Initialize all providers from config"""
        logger.info("Initializing providers...")

        # Weather provider
        if 'weather' in self.config:
            try:
                weather_config = WeatherConfig(self.config['weather'])
                self.providers['weather'] = OpenMeteoWeatherProvider(weather_config)
            except Exception as e:
                logger.error(f"Failed to initialize weather provider: {e}")

        # Calendar provider
        if 'google_calendar' in self.config:
            try:
                cal_config = CalendarConfig(self.config['google_calendar'])
                self.providers['calendar'] = GoogleCalendarProvider(cal_config)
            except Exception as e:
                logger.error(f"Failed to initialize calendar provider: {e}")

        # Storage provider
        if 'dropbox' in self.config:
            try:
                storage_config = StorageConfig(self.config['dropbox'])
                self.providers['storage'] = StorageProvider(storage_config)
            except Exception as e:
                logger.error(f"Failed to initialize storage provider: {e}")

        # Transcription provider
        if 'openai_apikey' in self.config:
            try:
                transcription_config = TranscriptionConfig(self.config)
                self.providers['transcription'] = TranscriptionProvider(transcription_config)
            except Exception as e:
                logger.error(f"Failed to initialize transcription provider: {e}")

        logger.info(f"Initialized {len(self.providers)} providers: {list(self.providers.keys())}")

    def _run_health_checks(self):
        """Run health checks on all providers"""
        logger.info("Running provider health checks...")

        for name, provider in self.providers.items():
            try:
                provider.health_check()
                logger.info(f"✓ {name} provider healthy")
            except Exception as e:
                logger.warning(f"✗ {name} provider health check failed: {e}")

    def get(self, name: str) -> Optional[Any]:
        """
        Get specific provider by name.

        Args:
            name: Provider name ('weather', 'calendar', 'storage', 'transcription')

        Returns:
            Provider instance or None if not initialized
        """
        return self.providers.get(name)

    def get_all_tools(self) -> list:
        """
        Collect all LangChain tools from all providers.

        Returns:
            Combined list of tools from all providers
        """
        tools = []

        for name, provider in self.providers.items():
            if hasattr(provider, 'get_tools'):
                try:
                    provider_tools = provider.get_tools()
                    tools.extend(provider_tools)
                    logger.debug(f"Registered {len(provider_tools)} tools from {name}")
                except Exception as e:
                    logger.error(f"Failed to get tools from {name}: {e}")

        logger.info(f"Total provider tools: {len(tools)}")
        return tools

    def list_providers(self) -> list[str]:
        """Get list of initialized provider names"""
        return list(self.providers.keys())


# Export main classes
__all__ = [
    'ProviderRegistry',
    'WeatherConfig',
    'CalendarConfig',
    'StorageConfig',
    'TranscriptionConfig',
    'OpenMeteoWeatherProvider',
    'GoogleCalendarProvider',
    'StorageProvider',
    'TranscriptionProvider',
]
```

**Step 2: Simplify sebastian_agent.py using registry**

Replace all provider initialization in `sebastian_agent.py` with:

```python
import dotenv
import os
from langchain import hub
from langchain_openai import ChatOpenAI
from langchain.agents import (
    create_openai_functions_agent,
    AgentExecutor,
)
from loguru import logger

from providers import ProviderRegistry
from utils.logging_config import setup_logging
from utils.utils import config
from tools import get_tools

"""
Creates a LangChain-based AI agent called "Sebastian" using modular provider system.
"""

# Initialize logging
setup_logging(log_folder=config.get("logfolder", "logs"))

dotenv.load_dotenv()
AGENT_MODEL = os.getenv("OPENAI_AGENT_MODEL")
chat_model = ChatOpenAI(model=AGENT_MODEL, temperature=0)

agent_prompt = hub.pull("hwchase17/openai-functions-agent")

# Initialize provider registry
logger.info("Initializing provider registry...")
registry = ProviderRegistry(config)

# Get all tools (core + provider tools)
core_tools = get_tools()
provider_tools = registry.get_all_tools()
all_tools = core_tools + provider_tools

logger.info(f"Core tools: {len(core_tools)}, Provider tools: {len(provider_tools)}, Total: {len(all_tools)}")

# Create agent with all tools
sebastian_agent = create_openai_functions_agent(
    llm=chat_model,
    prompt=agent_prompt,
    tools=all_tools,
)

sebastian_agent_executor = AgentExecutor(
    agent=sebastian_agent,
    tools=all_tools,
    return_intermediate_steps=True,
    verbose=True,
)


def get_sebastian_answer(question):
    """Get answer from Sebastian agent"""
    logger.info(f"Processing question: {question[:50]}...")
    response = sebastian_agent_executor.invoke({"input": question})
    logger.info("Response generated")
    return response["output"]


# Export providers for bot commands
weather_provider = registry.get('weather')
calendar_provider = registry.get('calendar')
storage_provider = registry.get('storage')
transcription_provider = registry.get('transcription')
```

**Step 3: Test registry**

```bash
python sebastian_bot.py
```

Check logs for:
- "Initializing providers..."
- "Initialized N providers: [...]"
- "Running provider health checks..."
- "✓ weather provider healthy"
- etc.

Test commands:
- Weather query
- `/calendario`
- Send document

**Step 4: Commit provider registry**

```bash
git add providers/__init__.py sebastian_agent.py
git commit -m "feat: implement ProviderRegistry for centralized initialization

- ProviderRegistry class handles all provider init
- Automatic health checks on startup
- Tool aggregation from all providers
- Simplified sebastian_agent.py significantly
- Export providers for bot command access

Phase 4/5 of provider refactoring"
```

---

### Task 10: Remove Legacy Provider Directories

**Files:**
- Delete: `weather/` directory
- Delete: `mycalendar/` directory (keep credentials)
- Delete: `mydropbox/` directory
- Delete: `mp3totext/` directory
- Move: `weather/refranes.txt` to `data/`
- Modify: `providers/config.py` (update refranes path)

**Step 1: Create data directory and move refranes**

```bash
mkdir -p data
cp weather/refranes.txt data/refranes.txt
```

**Step 2: Update WeatherConfig default path**

In `providers/config.py`, update `WeatherConfig`:

```python
class WeatherConfig(ProviderConfig):
    def __init__(self, config_dict: dict = None):
        # ...
        # Update refranes default path
        refranes_file = config_dict.get('refranes_file', 'data/refranes.txt')
        # ...
```

**Step 3: Update config.yaml weather section**

In `config.yaml`:

```yaml
weather:
  cache_hours: 1
  cities:
    # ... cities unchanged
  refranes_file: data/refranes.txt  # Updated path
```

**Step 4: Create backup of credentials**

```bash
# Backup calendar credentials (keep these!)
cp mycalendar/Zell0ss_api-access.json .
# Will restore after directory removal
```

**Step 5: Remove legacy directories**

```bash
rm -rf weather/
rm -rf mydropbox/
rm -rf mp3totext/
# Keep mycalendar for now, just the credentials
```

**Step 6: Restore credentials and update config**

```bash
mkdir -p credentials
mv Zell0ss_api-access.json credentials/
rm -rf mycalendar/
```

Update `config.yaml`:

```yaml
google_calendar:
  service_account_file: credentials/Zell0ss_api-access.json  # Updated path
  calendar_id: zelloss@gmail.com
```

**Step 7: Test everything still works**

```bash
python sebastian_bot.py
```

Test all commands:
- Weather query
- `/calendario`
- Send document

All should work with new paths.

**Step 8: Commit cleanup**

```bash
git add -A
git commit -m "refactor: remove legacy provider directories

- Moved weather/refranes.txt to data/refranes.txt
- Moved credentials to credentials/ directory
- Removed weather/, mycalendar/, mydropbox/, mp3totext/
- Updated config paths in config.yaml
- All functionality now in providers/ package

Phase 4/5 of provider refactoring (cleanup complete)"
```

---

## Phase 5: Documentation & Final Cleanup

### Task 11: Remove Weather Tools from tools.py

**Files:**
- Modify: `tools.py` (remove weather chains)

**Step 1: Remove weather chains from tools.py**

In `tools.py`, remove:
- `get_current_weather_chain()` function
- `get_weather_report_chain()` function
- Weather tools from `get_tools()` return list

Keep:
- `get_basic_question_chain()`
- `get_wine_taste_note_chain()`
- `investigate_wine_chain()`
- `get_social_media_banner()`
- `get_lazy_prompt()`
- All wine and core tools

**Step 2: Test that weather still works via provider**

```bash
python sebastian_bot.py
```

Ask bot weather question - should use provider tools.

**Step 3: Commit tools cleanup**

```bash
git add tools.py
git commit -m "refactor: remove weather chains from tools.py

- Removed get_current_weather_chain
- Removed get_weather_report_chain
- Weather functionality now exclusively in WeatherProvider
- Core tools remain (wine, basic questions, lazy prompt)

Phase 5/5 of provider refactoring"
```

---

### Task 12: Update Documentation

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `BRIEFING.md`
- Create: `docs/HOW-TO-ADD-PROVIDER.md`
- Modify: `CLAUDE.md`

**Step 1: Update ARCHITECTURE.md**

Update `ARCHITECTURE.md` with provider architecture section:

```markdown
## Provider Architecture

Sebastian uses a modular provider system for external integrations.

### Provider Hierarchy

\```mermaid
graph TD
    A[ProviderRegistry] --> B[WeatherProvider]
    A --> C[CalendarProvider]
    A --> D[StorageProvider]
    A --> E[TranscriptionProvider]

    B --> F[OpenMeteoWeatherProvider]
    C --> G[GoogleCalendarProvider]

    style A fill:#90EE90
    style B fill:#FFE4B5
    style C fill:#FFE4B5
    style D fill:#87CEEB
    style E fill:#87CEEB
\```

**Abstract Providers** (swappable):
- WeatherProvider: OpenMeteo implementation (can swap for WeatherAPI)
- CalendarProvider: Google Calendar implementation (can swap for Outlook)

**Concrete Providers** (specific):
- StorageProvider: Dropbox integration
- TranscriptionProvider: OpenAI Whisper

### Key Design Decisions

#### Why Provider Pattern?

**Context**: Bot integrates with multiple external services (weather, calendar, storage, AI).

**Decision**: Create base provider class with retry logic, abstract providers for swappable services.

**Reasons**:
- Easy to add new providers (Instagram, Blogger, n8n coming)
- Consistent error handling and retry logic
- Each provider self-contained (config, chains, logic)
- Clear separation from bot logic

**Trade-off**: Slightly more complex than direct integration, but much easier to extend.

[... rest of ARCHITECTURE.md ...]
\```

**Step 2: Update BRIEFING.md**

Update `BRIEFING.md` with new structure:

```markdown
## Project structure

\```
sebastian/
├── providers/              # Modular provider system
│   ├── __init__.py        # ProviderRegistry
│   ├── base.py            # BaseProvider with retry logic
│   ├── config.py          # Provider configurations
│   ├── weather.py         # Weather provider
│   ├── calendar.py        # Calendar provider
│   ├── storage.py         # Storage provider (Dropbox)
│   └── transcription.py   # Transcription provider (Whisper)
├── sebastian_bot.py       # Telegram bot handlers
├── sebastian_agent.py     # LangChain agent with providers
├── tools.py               # Core LangChain tools
├── utils/
│   ├── utils.py           # Utilities
│   └── logging_config.py  # Loguru setup
├── experiments/           # Test/experimental code
├── credentials/           # API credentials (gitignored)
├── data/                  # Static data (refranes.txt)
└── config.yaml            # Configuration

\```

**Key modules**:
- **providers/**: Self-contained provider implementations with retry logic and logging
- **sebastian_bot.py**: Telegram command handlers, uses providers via registry
- **sebastian_agent.py**: LangChain agent, combines core tools + provider tools
- **tools.py**: Core chains (wine, basic Q&A, prompt enhancement)

[... rest of BRIEFING.md ...]
\```

**Step 3: Create HOW-TO-ADD-PROVIDER.md**

Create `docs/HOW-TO-ADD-PROVIDER.md`:

```markdown
# How to Add a New Provider

## Goal

By the end of this guide, you will have added a new provider to Sebastian bot following the established pattern.

## Context

Providers in Sebastian bot are self-contained modules that integrate external services (APIs, databases, etc.). Examples: weather, calendar, social media publishers.

## Steps

### 1. Decide: Abstract or Concrete?

**Abstract provider** - When multiple implementations possible:
- Social media (Blogger, Instagram, Twitter)
- Calendar (Google, Outlook, Apple)
- Weather (OpenMeteo, WeatherAPI, OpenWeather)

**Concrete provider** - When single implementation:
- Dropbox storage (unlikely to swap)
- Whisper transcription (specific to OpenAI)

### 2. Create Configuration Class

In `providers/config.py`:

\```python
class YourProviderConfig(ProviderConfig):
    """Configuration for your provider"""

    def __init__(self, config_dict: dict):
        self.api_key = config_dict.get('api_key')
        self.base_url = config_dict.get('base_url', 'https://api.example.com')
        # ... other config

    def validate(self) -> bool:
        if not self.api_key:
            raise ValueError("YourProviderConfig: api_key required")
        return True
\```

### 3. Create Provider Class

Create `providers/your_provider.py`:

\```python
from abc import ABC, abstractmethod
from loguru import logger
from .base import BaseProvider
from .config import YourProviderConfig

# If abstract:
class YourProvider(BaseProvider, ABC):
    @abstractmethod
    def main_method(self):
        pass

# Implementation:
class YourProviderImpl(YourProvider):
    def __init__(self, config: YourProviderConfig):
        super().__init__(config)
        # Initialize API client, etc.

    def health_check(self) -> bool:
        # Test connection
        pass

    def main_method(self):
        def _api_call():
            # Actual API call
            pass

        # Use retry wrapper
        return self._call_with_retry(_api_call)

    def get_tools(self) -> list:
        # If provider has LangChain tools
        return [...]
\```

### 4. Add to config.yaml

\```yaml
your_provider:
  api_key: xxx
  base_url: https://api.example.com
\```

### 5. Register in ProviderRegistry

In `providers/__init__.py`:

\```python
from .your_provider import YourProviderImpl
from .config import YourProviderConfig

class ProviderRegistry:
    def _initialize_providers(self):
        # ... existing providers ...

        # Your provider
        if 'your_provider' in self.config:
            try:
                config = YourProviderConfig(self.config['your_provider'])
                self.providers['your_provider'] = YourProviderImpl(config)
            except Exception as e:
                logger.error(f"Failed to init your_provider: {e}")
\```

### 6. Test

\```bash
python sebastian_bot.py
\```

Check logs for:
- "Initialized YourProviderImpl"
- "✓ your_provider provider healthy"

### 7. Use in Bot

In `sebastian_bot.py`:

\```python
from sebastian_agent import registry

your_provider = registry.get('your_provider')

@bot.message_handler(commands=['your_command'])
def your_command_handler(message):
    if authorized(message.chat.username, message.chat.id):
        result = your_provider.main_method()
        bot.reply_to(message, result)
\```

## Troubleshooting

### Problem: "Failed to initialize provider"

**Cause**: Config validation failed or API credentials invalid

**Solution**: Check `logs/errors.log` for specific error, verify config.yaml values

### Problem: "Health check failed"

**Cause**: Cannot connect to external API

**Solution**: Verify API credentials, check network connectivity, test API endpoint manually

### Problem: "Provider tools not registered"

**Cause**: `get_tools()` not implemented or returning empty list

**Solution**: Implement `get_tools()` in provider, check logs for tool registration count
\```

**Step 4: Update CLAUDE.md**

Update `CLAUDE.md` with provider information:

```markdown
## Provider System

Sebastian uses a modular provider architecture for external integrations.

### Adding New Provider

See [docs/HOW-TO-ADD-PROVIDER.md](docs/HOW-TO-ADD-PROVIDER.md) for complete guide.

Quick overview:
1. Create config class in `providers/config.py`
2. Create provider in `providers/your_provider.py`
3. Add config section to `config.yaml`
4. Register in `ProviderRegistry` (`providers/__init__.py`)
5. Test and use in bot commands

### Provider Retry Logic

All providers inherit retry logic from `BaseProvider`:
- Retries transient errors (network, timeout) 3 times
- Exponential backoff: 2s → 4s → 8s
- Fails fast on auth/config errors
- All retries logged via loguru

### Current Providers

- **Weather**: OpenMeteo API (abstract, swappable)
- **Calendar**: Google Calendar (abstract, swappable)
- **Storage**: Dropbox (concrete)
- **Transcription**: OpenAI Whisper (concrete)

[... rest of CLAUDE.md ...]
\```

**Step 5: Commit documentation**

```bash
git add ARCHITECTURE.md BRIEFING.md CLAUDE.md docs/HOW-TO-ADD-PROVIDER.md
git commit -m "docs: update documentation for provider architecture

- Updated ARCHITECTURE.md with provider pattern and decisions
- Updated BRIEFING.md with new project structure
- Created HOW-TO-ADD-PROVIDER.md guide
- Updated CLAUDE.md with provider system info

Phase 5/5 of provider refactoring (COMPLETE)"
```

---

### Task 13: Final Verification & Git Tag

**Files:**
- All files (final verification)

**Step 1: Run full test suite (manual)**

Test all bot functionality:
- [ ] Bot starts without errors
- [ ] Weather queries work
- [ ] `/calendario` returns events
- [ ] Document upload to Dropbox works
- [ ] All providers show healthy in logs
- [ ] LangChain agent can use all tools
- [ ] Experimental code in `experiments/` folder
- [ ] Old provider directories removed
- [ ] Documentation updated

**Step 2: Check logs**

```bash
tail -50 logs/app.log
```

Verify:
- No errors during startup
- All providers initialized
- Health checks passed
- Tool counts correct

**Step 3: Verify experiments folder**

```bash
ls experiments/
```

Should contain:
- tester.py
- test_oauth.py
- *.ipynb files
- legacytests/ subdirectory

**Step 4: Verify provider directory**

```bash
ls providers/
```

Should contain:
- __init__.py (ProviderRegistry)
- base.py
- config.py
- weather.py
- calendar.py
- storage.py
- transcription.py

**Step 5: Create git tag**

```bash
git tag -a v2.0.0-provider-refactoring -m "Major refactoring: Modular provider architecture

- Implemented provider system with BaseProvider and retry logic
- Migrated all integrations to providers/ package
- Added loguru structured logging
- Separated experimental code to experiments/
- Updated all documentation

Breaking changes:
- weather/, mycalendar/, mydropbox/, mp3totext/ directories removed
- config.yaml structure changed (added provider sections)
- Direct imports from old modules will fail

Migration guide: See docs/plans/2026-02-13-provider-refactoring-design.md"

git push origin v2.0.0-provider-refactoring
```

**Step 6: Final commit**

```bash
git add -A
git commit -m "chore: provider refactoring complete

All 5 phases completed:
✓ Phase 1: Foundation (structure, logging, base classes)
✓ Phase 2: Weather provider migration (pilot)
✓ Phase 3: Remaining providers (calendar, storage, transcription)
✓ Phase 4: Provider registry and cleanup
✓ Phase 5: Documentation and final verification

Bot is now fully modularized with provider architecture.
Ready for future extensions (Blogger, Instagram, n8n)."
```

---

## Success Criteria Checklist

Verify all criteria met:

- [x] All existing bot commands work identically
- [x] Adding new provider follows clear pattern (documented in HOW-TO)
- [x] Provider failures retry transient errors automatically
- [x] Logs clearly show provider initialization and errors (loguru)
- [x] Experimental code completely separated (experiments/ folder)
- [x] Documentation updated (ARCHITECTURE, BRIEFING, CLAUDE, HOW-TO)
- [x] Future developer can understand architecture in <10 minutes (see design doc)
- [x] Old provider directories removed, code consolidated
- [x] Registry provides centralized provider management
- [x] Health checks run on startup for all providers

---

## Execution Options

Plan complete and saved to `docs/plans/2026-02-13-provider-refactoring.md`.

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration. REQUIRED SUB-SKILL: superpowers:subagent-driven-development

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints. REQUIRED SUB-SKILL: superpowers:executing-plans (in new session)

**Which approach do you prefer?**
