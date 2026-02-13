# How to Add a New Provider

## Goal

By the end of this guide you will have created a new provider for the Sebastian bot that integrates with an external service, includes automatic retry logic, health checks, and is fully registered in the ProviderRegistry.

## Context

Providers in the Sebastian bot are self-contained modules that integrate with external services (APIs, databases, third-party libraries). They inherit from `BaseProvider` to get automatic retry logic, structured logging, and health check capabilities. The ProviderRegistry manages all providers and aggregates their tools for the LangChain agent.

## Steps

### 1. Decide: Abstract or Concrete?

**Choose Abstract Provider if**:
- Multiple implementations are likely (e.g., weather from OpenMeteo, WeatherAPI, Tomorrow.io)
- Service has industry standards (e.g., calendar via CalDAV, Google, Outlook)
- You want swappable implementations for testing or migration

**Choose Concrete Provider if**:
- Service is unique/proprietary (e.g., Dropbox API, Slack API)
- Only one implementation will ever exist
- Abstraction adds no value

**Examples from Sebastian**:
- **Abstract**: `WeatherProvider` (can swap between OpenMeteo, WeatherAPI)
- **Abstract**: `CalendarProvider` (can swap between Google, Outlook)
- **Concrete**: `StorageProvider` (Dropbox-specific, no alternative implementation)
- **Concrete**: `TranscriptionProvider` (Whisper-specific, no alternative implementation)

### 2. Create Configuration Class

Add your config class to `providers/config.py`:

```python
from abc import ABC, abstractmethod
import os


class NewProviderConfig(ProviderConfig):
    """Configuration for new provider"""

    def __init__(self, config_dict: dict):
        """
        Initialize configuration.

        Args:
            config_dict: Dict from config.yaml['new_provider']
        """
        # Extract required fields
        self.api_key = config_dict.get('api_key')
        self.api_endpoint = config_dict.get('api_endpoint', 'https://api.example.com')

        # Extract optional fields with defaults
        self.timeout = config_dict.get('timeout', 30)
        self.retry_count = config_dict.get('retry_count', 3)

    def validate(self) -> bool:
        """
        Validate configuration.

        Returns:
            True if valid

        Raises:
            ValueError: If required fields missing
            FileNotFoundError: If required files don't exist
        """
        # Check required fields
        if not self.api_key:
            raise ValueError("NewProviderConfig: api_key not specified")

        # Validate field formats
        if not isinstance(self.timeout, int) or self.timeout <= 0:
            raise ValueError("NewProviderConfig: timeout must be positive integer")

        # Check file existence if needed
        # if not os.path.exists(self.credentials_file):
        #     raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")

        return True
```

**Key points**:
- Inherit from `ProviderConfig`
- Extract all config values in `__init__`
- Provide sensible defaults for optional fields
- Implement `validate()` to check required fields
- Raise descriptive exceptions (ValueError, FileNotFoundError)

### 3. Create Provider Class

#### Option A: Abstract Provider (Swappable)

Create `providers/new_provider.py`:

```python
"""New provider with abstract interface"""
from abc import ABC, abstractmethod
from loguru import logger

from .base import BaseProvider
from .config import NewProviderConfig


class NewProvider(BaseProvider, ABC):
    """Abstract new provider interface"""

    @abstractmethod
    def fetch_data(self, query: str) -> dict:
        """Fetch data from provider"""
        pass

    @abstractmethod
    def get_tools(self) -> list:
        """Return LangChain tools for this provider"""
        pass


class ExampleNewProvider(NewProvider):
    """Example implementation of new provider"""

    def __init__(self, config: NewProviderConfig):
        """Initialize provider"""
        super().__init__(config)

        # Initialize API client
        self.api_key = config.api_key
        self.endpoint = config.api_endpoint
        self.timeout = config.timeout

        logger.info(f"Initialized ExampleNewProvider with endpoint: {self.endpoint}")

    def health_check(self) -> bool:
        """
        Check if provider is healthy.

        Returns:
            True if successful

        Raises:
            Exception if health check fails
        """
        try:
            # Simple API call to verify connectivity
            result = self.fetch_data("health_check")
            logger.info("Health check passed for ExampleNewProvider")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise

    def fetch_data(self, query: str) -> dict:
        """
        Fetch data from external API.

        Args:
            query: Query string

        Returns:
            Data dict from API
        """
        import requests

        def _api_call():
            response = requests.get(
                f"{self.endpoint}/data",
                params={'q': query},
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        # Use retry wrapper from BaseProvider
        return self._call_with_retry(_api_call)

    def get_tools(self) -> list:
        """
        Return LangChain tools.

        Returns:
            List of Tool objects
        """
        from langchain.tools import Tool

        def fetch_tool_func(query: str) -> str:
            """Fetch data based on query"""
            result = self.fetch_data(query)
            return str(result)

        tools = [
            Tool(
                name="NewProviderFetch",
                func=fetch_tool_func,
                description="Use when asked to fetch data from new provider."
            )
        ]

        logger.debug(f"Created {len(tools)} tools for ExampleNewProvider")
        return tools
```

#### Option B: Concrete Provider (Single Implementation)

Create `providers/new_provider.py`:

```python
"""New provider implementation"""
from loguru import logger
import some_api_library

from .base import BaseProvider
from .config import NewProviderConfig


class NewProvider(BaseProvider):
    """Concrete new provider (not abstract)"""

    def __init__(self, config: NewProviderConfig):
        """Initialize provider"""
        super().__init__(config)

        # Initialize API client
        self.client = some_api_library.Client(
            api_key=config.api_key,
            endpoint=config.api_endpoint
        )

        logger.info("Initialized NewProvider")

    def health_check(self) -> bool:
        """
        Verify provider is working.

        Returns:
            True if successful

        Raises:
            Exception if health check fails
        """
        try:
            # Simple API call
            self.client.ping()
            logger.info("Health check passed for NewProvider")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise

    def do_something(self, input_data: str) -> str:
        """
        Provider's main functionality.

        Args:
            input_data: Input for processing

        Returns:
            Processed result
        """
        def _api_call():
            return self.client.process(input_data)

        try:
            # Use retry wrapper for API calls
            result = self._call_with_retry(_api_call)
            logger.info(f"Processed data: {len(result)} chars")
            return result
        except Exception as e:
            logger.error(f"Failed to process data: {e}")
            raise
```

**Key points**:
- Inherit from `BaseProvider` (and optionally `ABC` for abstract)
- Call `super().__init__(config)` to trigger validation
- Initialize API clients in `__init__`
- Implement `health_check()` with a simple API call
- Use `self._call_with_retry()` for all external API calls
- Log all operations with context

### 4. Add to config.yaml

Add provider configuration to your `config.yaml`:

```yaml
# Existing config...
telegram_apikey: xxx
openai_apikey: xxx

# New provider configuration
new_provider:
  api_key: your_api_key_here
  api_endpoint: https://api.example.com
  timeout: 30
  retry_count: 3
```

**Important**: Add corresponding section to `config.example.yaml` (without real API keys):

```yaml
# New provider (optional)
new_provider:
  api_key: xxx_your_api_key_here
  api_endpoint: https://api.example.com  # API endpoint URL
  timeout: 30  # Request timeout in seconds
  retry_count: 3  # Number of retries for transient errors
```

### 5. Register in ProviderRegistry

Edit `providers/__init__.py` to register your provider:

```python
# Add import at top
from .new_provider import NewProvider  # or ExampleNewProvider
from .config import NewProviderConfig

# In ProviderRegistry._initialize_providers(), add:
def _initialize_providers(self):
    # ... existing provider initialization ...

    # Initialize new provider if configured
    if 'new_provider' in self.config:
        try:
            new_config = NewProviderConfig(self.config['new_provider'])
            self.providers['new_provider'] = ExampleNewProvider(new_config)
            logger.debug("New provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize new provider: {e}")

    # ... rest of initialization ...
```

**Also update `__all__` export**:

```python
__all__ = [
    'BaseProvider',
    'ProviderConfig',
    'WeatherConfig',
    'CalendarConfig',
    'StorageConfig',
    'TranscriptionConfig',
    'NewProviderConfig',  # Add this
    'OpenMeteoWeatherProvider',
    'GoogleCalendarProvider',
    'StorageProvider',
    'TranscriptionProvider',
    'NewProvider',  # Add this (or ExampleNewProvider)
    'ProviderRegistry',
]
```

### 6. Test

Test your provider initialization:

```python
# test_new_provider.py
import yaml
from providers import ProviderRegistry

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize registry (will initialize all providers including new one)
registry = ProviderRegistry(config)

# Check provider is initialized
provider = registry.get('new_provider')
if provider:
    print("✓ Provider initialized successfully")

    # Test provider method
    result = provider.do_something("test input")
    print(f"✓ Provider method works: {result}")
else:
    print("✗ Provider not initialized")
```

Run test:

```bash
python test_new_provider.py
```

**Expected output**:
```
[INFO] Initialized ExampleNewProvider with endpoint: https://api.example.com
[INFO] Health check passed for ExampleNewProvider
[INFO] Initialized 5 providers: ['weather', 'calendar', 'storage', 'transcription', 'new_provider']
✓ Provider initialized successfully
[INFO] Processed data: 42 chars
✓ Provider method works: ...
```

### 7. Use in Bot

Use your provider in sebastian_bot.py:

```python
# In sebastian_bot.py

@bot.message_handler(commands=['newcommand'])
def new_command_handler(message):
    """Handle /newcommand"""
    if not authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, "Not authorized")
        return

    try:
        # Get provider
        provider = provider_registry.get('new_provider')
        if not provider:
            bot.reply_to(message, "New provider not configured")
            return

        # Extract arguments
        args = message.text.split(' ', 1)
        if len(args) < 2:
            bot.reply_to(message, "Usage: /newcommand <input>")
            return

        input_data = args[1]

        # Call provider
        result = provider.do_something(input_data)

        # Send response
        bot.reply_to(message, result)

    except Exception as e:
        logger.error(f"Error in new command: {e}")
        bot.reply_to(message, f"Error: {str(e)}")
```

**Or integrate with LangChain agent** (if provider has `get_tools()`):

The provider's tools are automatically aggregated by `ProviderRegistry.get_all_tools()` and passed to the LangChain agent in sebastian_agent.py. No additional code needed - the agent will select your provider's tools based on their descriptions.

## Troubleshooting

### Problem: "Failed to initialize provider"

**Cause**: Configuration validation failed or provider initialization raised exception

**Solution**:
1. Check config.yaml has all required fields:
   ```bash
   cat config.yaml | grep -A 5 "new_provider:"
   ```

2. Verify `validate()` method requirements:
   - All required fields present?
   - File paths exist?
   - Values have correct types?

3. Check logs for specific error:
   ```bash
   tail -f logs/app.log | grep "new_provider"
   ```

4. Test config class independently:
   ```python
   from providers.config import NewProviderConfig
   config = NewProviderConfig({'api_key': 'test'})
   config.validate()  # Should raise descriptive error
   ```

---

### Problem: "Health check failed"

**Cause**: Provider can't connect to external service

**Solution**:
1. Verify API credentials are correct:
   - API key valid?
   - Endpoint URL correct?
   - Network connectivity to service?

2. Test API manually:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" https://api.example.com/health
   ```

3. Check if service is down:
   - Visit service status page
   - Check for maintenance windows

4. Simplify health check temporarily:
   ```python
   def health_check(self) -> bool:
       logger.info("Skipping health check for testing")
       return True  # Temporary bypass
   ```

5. Enable verbose logging:
   ```python
   logger.add("provider_debug.log", level="DEBUG")
   ```

---

### Problem: "Provider tools not registered"

**Cause**: Provider doesn't implement `get_tools()` or tools not aggregated

**Solution**:
1. Verify provider implements `get_tools()`:
   ```python
   def get_tools(self) -> list:
       """Must return list of Tool objects"""
       return [Tool(...)]
   ```

2. Check ProviderRegistry.get_all_tools() includes your provider:
   ```python
   registry = ProviderRegistry(config)
   all_tools = registry.get_all_tools()
   print([tool.name for tool in all_tools])  # Should include your tool names
   ```

3. Verify tools have descriptive names and descriptions:
   ```python
   Tool(
       name="NewProviderFetch",  # Clear, unique name
       func=fetch_tool_func,
       description="Use when asked to fetch data from new provider."  # Agent uses this
   )
   ```

4. Check sebastian_agent.py includes provider tools:
   ```python
   # In sebastian_agent.py
   provider_tools = provider_registry.get_all_tools()
   all_tools = get_tools() + provider_tools  # Should combine core + provider tools
   ```

---

### Problem: "API calls failing without retries"

**Cause**: Not using `BaseProvider._call_with_retry()`

**Solution**:
Always wrap API calls with retry logic:

```python
# ✗ Bad - no retries
def fetch_data(self):
    response = requests.get(self.endpoint)
    return response.json()

# ✓ Good - automatic retries
def fetch_data(self):
    def _api_call():
        response = requests.get(self.endpoint)
        response.raise_for_status()  # Important: raise on HTTP errors
        return response.json()

    return self._call_with_retry(_api_call)
```

**Key points**:
- Define inner function with API call
- Call `raise_for_status()` to trigger retries on HTTP errors
- Return result from `_call_with_retry()`
- Transient errors (network, timeout) automatically retried
- Non-transient errors (auth, config) fail immediately

---

### Problem: "Secrets exposed in logs"

**Cause**: Provider config `__repr__` showing API keys

**Solution**:
Config classes inherit `__repr__` from `ProviderConfig` that automatically masks secrets. But verify:

```python
# Test repr safety
config = NewProviderConfig({'api_key': 'secret123'})
print(config)  # Should show: NewProviderConfig({'api_key': '***', ...})
```

If secrets still exposed, ensure you're inheriting from `ProviderConfig` and not overriding `__repr__`.

---

## Advanced Topics

### Adding LangChain Chains

If your provider needs to process data with GPT before returning to user:

```python
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

class NewProvider(BaseProvider):
    def __init__(self, config: NewProviderConfig):
        super().__init__(config)
        # Initialize chat model
        self.chat_model = ChatOpenAI(model="gpt-4o", temperature=0)

    def _create_analysis_chain(self):
        """Create chain for data analysis"""
        template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert analyst. Analyze the data and provide insights."),
            ("human", "{data}")
        ])
        return template | self.chat_model

    def get_tools(self) -> list:
        chain = self._create_analysis_chain()

        def analyze_func(query: str) -> str:
            data = self.fetch_data(query)
            result = chain.invoke({"data": data})
            return result.content

        return [Tool(name="NewProviderAnalysis", func=analyze_func, description="...")]
```

### Custom Retry Logic

Override `_call_with_retry()` for custom retry behavior:

```python
class NewProvider(BaseProvider):
    def _custom_retry(self, func, *args, **kwargs):
        """Custom retry with different backoff strategy"""
        from tenacity import retry, stop_after_attempt, wait_fixed

        @retry(stop=stop_after_attempt(5), wait=wait_fixed(5))
        def _wrapper():
            return func(*args, **kwargs)

        return _wrapper()
```

### Provider Dependencies

If your provider depends on another provider:

```python
class DependentProvider(BaseProvider):
    def __init__(self, config: DependentConfig, storage_provider: StorageProvider):
        super().__init__(config)
        self.storage = storage_provider  # Use another provider

    def process_and_store(self, data: str):
        processed = self._process(data)
        # Use storage provider
        self.storage.upload_file(processed.encode(), "result.txt")
```

Then in `ProviderRegistry._initialize_providers()`:

```python
storage = self.providers.get('storage')
if 'dependent' in self.config and storage:
    config = DependentConfig(self.config['dependent'])
    self.providers['dependent'] = DependentProvider(config, storage)
```

---

## Checklist

Before considering your provider complete:

- [ ] Config class created in `providers/config.py`
- [ ] Config class has `validate()` method checking all required fields
- [ ] Provider class created in `providers/new_provider.py`
- [ ] Provider inherits from `BaseProvider`
- [ ] Provider implements `health_check()` method
- [ ] All API calls use `self._call_with_retry()`
- [ ] Provider registered in `ProviderRegistry._initialize_providers()`
- [ ] Provider added to `__all__` in `providers/__init__.py`
- [ ] Configuration added to `config.yaml`
- [ ] Example config added to `config.example.yaml`
- [ ] Provider tested independently (initialization + health check)
- [ ] Provider integrated with bot (command handler or agent tools)
- [ ] Logging uses loguru with descriptive messages
- [ ] No secrets hardcoded (all from config.yaml)

---

## Next Steps

- Read [ARCHITECTURE.md](../ARCHITECTURE.md) to understand provider pattern design decisions
- Read [BRIEFING.md](../BRIEFING.md) for project context and conventions
- Explore existing providers (weather.py, storage.py) as reference implementations
- Consider adding unit tests for your provider in `tests/` directory

---

*Need help? Check logs in `logs/app.log` or enable DEBUG logging.*
