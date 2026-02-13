# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sebastian is a Telegram bot powered by OpenAI's GPT models and LangChain, providing conversational AI, image generation, weather forecasts, wine expertise, and productivity features. The bot uses a LangChain agent system to orchestrate specialized tools/chains for different types of queries.

## Commands

### Running the Bot
```bash
# Direct execution
python sebastian_bot.py

# Using systemd service (production)
make start    # or: sudo systemctl start sebastian.service
make stop     # or: sudo systemctl stop sebastian.service
make restart  # or: sudo systemctl restart sebastian.service
make status   # or: sudo systemctl status sebastian.service
```

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configuration setup
# 1. Copy config.example.yaml to config.yaml and fill in API keys
# 2. Copy .env.example to .env and configure OpenAI model settings
# 3. For Google Calendar: place credentials in mycalendar/ folder
```

### Environment Variables (.env)
Key environment variables control which OpenAI models are used:
- `OPENAI_CHAT_MODEL`: Model for specialized chains (weather, wine, etc.)
- `OPENAI_AGENT_MODEL`: Model for the LangChain agent executor
- `OPENAI_LZP_MODEL`: Model for prompt enhancement
- `OPENAI_APIKEY`: OpenAI API key

## Architecture

### Core Components Flow

```
Telegram Message → sebastian_bot.py → ProviderRegistry → providers/* → External APIs
                    (handlers)        (provider access)   (retry logic)

                 ↓ (no command)

               sebastian_agent.py → tools.py + provider tools → OpenAI/APIs
               (LangChain agent)    (specialized chains)
```

**Provider Flow**:
- Bot startup: config.yaml → ProviderRegistry → Initialize providers → Health checks
- Message handling: Command → Provider method → _call_with_retry() → External API
- Agent routing: Plain text → Agent → Tool selection → Provider tool → Provider method

### Key Files

**sebastian_bot.py** - Main entry point
- Telegram bot command handlers (`/start`, `/imagen`, `/calendario`, etc.)
- Initializes ProviderRegistry on startup
- Authorization checking via `utils.utils.authorized()`
- Routes default messages (no command) to the LangChain agent
- Direct GPT calls for `/3` (GPT-3.5) and `/4` (GPT-4) commands
- Accesses providers via `provider_registry.get('provider_name')`

**sebastian_agent.py** - LangChain orchestration
- Creates the main agent using `create_openai_functions_agent()`
- Uses `AgentExecutor` with tools from `tools.py` + provider tools
- Aggregates provider tools via `provider_registry.get_all_tools()`
- Pulls agent prompt from LangChain Hub: `"hwchase17/openai-functions-agent"`
- Exposes `get_sebastian_answer(question)` function that returns agent response

**tools.py** - Specialized chains
- Defines LangChain chains for different domains:
  - `BasicQuestions`: General Q&A (excludes weather/prompt tasks)
  - `WeatherSummary`: Current weather queries
  - `WeatherReport`: Full newspaper-style weather reports
  - `WineTasteNote`: Wine tasting note generation
  - `InvestigateWine`: Wine research and details
  - `WineArticleBanner`: Social media content for wine blog
  - `LazyPrompt`: Prompt enhancement using structured tool with parameters
- Each chain combines a specialized system prompt + ChatOpenAI model
- Returns list of tools via `get_tools()` for agent consumption

**utils/utils.py** - Configuration and utilities
- Loads `config.yaml` using PyYAML
- Authorization checking against `authorized_users` and `authorized_ids`
- Service management (restart/stop via systemctl)
- Dropbox file upload integration
- Telegram file retrieval and MIME type classification

### Specialized Modules

**providers/** - Modular provider system
- All providers inherit from `BaseProvider` with automatic retry logic
- ProviderRegistry manages initialization, health checks, and tool aggregation
- See [docs/HOW-TO-ADD-PROVIDER.md](docs/HOW-TO-ADD-PROVIDER.md) for details

**providers/weather.py** - OpenMeteoWeatherProvider
- OpenMeteo API integration with caching (1-hour cache via requests_cache)
- Supports multiple cities via config (Madrid, Gijón, Oviedo, Magán)
- Fetches current temp, precipitation, daily min/max, sunrise/sunset
- Returns weather report + random Spanish wine saying from `data/refranes.txt`
- Exposes WeatherSummary and WeatherReport tools for LangChain agent

**providers/calendar.py** - GoogleCalendarProvider
- Google Calendar API integration via service account
- Retrieves events for upcoming days via `get_events(days_ahead)`
- Called directly from `/calendario` bot command

**providers/storage.py** - StorageProvider (Dropbox)
- Dropbox API file upload functionality via OAuth2 refresh token
- Called from bot when documents are sent to chat
- Uploads to "Espacio familiar/intercambio" folder by default

**providers/transcription.py** - TranscriptionProvider (Whisper)
- OpenAI Whisper API integration for audio transcription
- Called from bot when voice messages are sent to chat

## LangChain Agent System

### How Tool Selection Works

1. User sends message without command → routed to `echo_all()` handler
2. Handler calls `get_sebastian_answer(message.text)` from sebastian_agent
3. Agent executor uses OpenAI function calling to select appropriate tool
4. Tool descriptions guide selection:
   - Weather queries → `WeatherSummary` or `WeatherReport`
   - Wine tasks → `WineTasteNote`, `InvestigateWine`, or `WineArticleBanner`
   - Prompt enhancement → `LazyPrompt` (StructuredTool with parameters)
   - Everything else → `BasicQuestions`

### Adding New Tools

1. Create a chain function in `tools.py` that returns `template | chat_model`
2. Define tool in `get_tools()` list with clear description
3. For tools needing parameters, use `StructuredTool` with Pydantic schema (see `LazyPrompt` example)
4. Tool descriptions are critical - the agent uses them for selection

### Agent Prompt Customization

The agent currently uses the standard `"hwchase17/openai-functions-agent"` prompt from LangChain Hub. To customize:
- Uncomment the `ChatPromptTemplate.from_messages()` example in sebastian_agent.py
- Important: Tool outputs should be returned as-is to user, not interpreted as instructions

## Configuration Structure

**config.yaml** (gitignored)
```yaml
authorized_ids: [telegram_user_id_1, ...]
authorized_users: [username_1, ...]
telegram_apikey: xxx
openai_apikey: xxx
openai_org_id: xxx
logfolder: /path/to/logs
dropbox: {...}
google_installed: {...}
```

## Authorization System

All bot commands check authorization via:
```python
if authorized(message.chat.username, message.chat.id):
    # command logic
```

Users can be authorized by username or Telegram user ID. New users can be added via `/adduser <user_id>` command (requires existing authorization).

## Telegram Bot Commands

- `/start`, `/hola` - Welcome message
- `/ayuda`, `/help` - Show available commands
- `/restart`, `/stop` - Service management (authorized only)
- `/id_me`, `/whoami` - Get Telegram user info
- `/adduser <user_id>` - Add authorized user
- `/imagen <prompt>` - DALL-E 3 image generation
- `/calendario` - Tomorrow's calendar events
- `/consumo` - Link to OpenAI usage dashboard
- `/plantilla` - Wine tasting note template
- `/nota_cata <wine_data>` - Generate wine tasting notes
- `/resumen <article_topic>` - Social media content for wine blog
- `/3 <question>` - Direct GPT-3.5 query (bypasses agent)
- `/4 <question>` - Direct GPT-4 query (bypasses agent)
- No command (plain text) - Routed to LangChain agent

## Provider System

### Adding New Provider

See [docs/HOW-TO-ADD-PROVIDER.md](docs/HOW-TO-ADD-PROVIDER.md) for comprehensive guide.

**Quick 5-step overview**:

1. **Create config class** in `providers/config.py`:
   ```python
   class NewProviderConfig(ProviderConfig):
       def validate(self) -> bool:
           # Check required fields
           pass
   ```

2. **Create provider class** in `providers/new_provider.py`:
   ```python
   class NewProvider(BaseProvider):
       def health_check(self) -> bool:
           # Verify connectivity
           pass
   ```

3. **Register in ProviderRegistry** (`providers/__init__.py`):
   ```python
   if 'new_provider' in self.config:
       config = NewProviderConfig(self.config['new_provider'])
       self.providers['new_provider'] = NewProvider(config)
   ```

4. **Add to config.yaml**:
   ```yaml
   new_provider:
     api_key: xxx
   ```

5. **Test initialization** and use in bot handlers or expose as LangChain tools

### Provider Retry Logic

All providers inherit from `BaseProvider` which provides automatic retry logic via `_call_with_retry()`:

- **Retries transient errors** (network failures, timeouts, connection resets) **3 times**
- **Exponential backoff**: 2 seconds → 4 seconds → 8 seconds between retries
- **Fails fast** on non-transient errors (authentication failures, configuration errors, validation errors)
- **All retries logged** via loguru with full context (provider name, method name, error type)

**When to use**: Wrap all external API calls with `self._call_with_retry(api_function)` to get automatic retry behavior.

**Example**:
```python
def fetch_weather(self, city: str):
    def _api_call():
        response = requests.get(f"https://api.weather.com/forecast?city={city}")
        response.raise_for_status()
        return response.json()

    return self._call_with_retry(_api_call)  # Automatic retries on network errors
```

### Current Providers

**WeatherProvider** (abstract → OpenMeteoWeatherProvider):
- Fetches weather forecasts from OpenMeteo API
- Provides LangChain tools: WeatherSummary, WeatherReport
- Includes 1-hour HTTP cache to reduce API calls
- Returns Spanish weather report + random refran (wine saying)

**CalendarProvider** (abstract → GoogleCalendarProvider):
- Retrieves events from Google Calendar API
- Uses service account authentication
- Called directly from bot commands (not exposed as agent tools)

**StorageProvider** (concrete, Dropbox):
- Uploads files to Dropbox via OAuth2
- Handles document uploads from Telegram
- Called directly from bot handlers (not exposed as agent tools)

**TranscriptionProvider** (concrete, Whisper):
- Transcribes audio files using OpenAI Whisper API
- Handles voice messages from Telegram
- Called directly from bot handlers (not exposed as agent tools)

## Logging

- Log file location: `{config["logfolder"]}/app.log`
- Uses **loguru** for structured logging across all modules
- All providers log initialization, health checks, API calls, retries, and errors
- Configured in both sebastian_bot.py and utils/logging_config.py

## Important Notes

- The bot uses `bot.infinity_polling()` for continuous operation
- GPT models are configurable: `GPT4 = "gpt-4o"`, `GPT3 = "gpt-3.5-turbo"`
- DALL-E model: `DALLE3 = "dall-e-3"` (1024x1024, standard quality)
- Agent system runs with `verbose=True` and `return_intermediate_steps=True`
- Weather reports include random Spanish wine sayings for cultural flavor
- All sensitive data (API keys, tokens) must be in config.yaml or .env, never in code
- **Provider health checks** run on bot startup - critical failures will prevent bot from starting
