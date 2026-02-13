# Sebastian Bot - Briefing for Claude

> **Purpose**: Knowledge transfer between Claude Code and Claude Web.
> **Audience**: Claude AI and developer

---

## What is this project

Sebastian is a Telegram bot powered by OpenAI's GPT models and LangChain that provides conversational AI, image generation, weather forecasts, wine expertise, and productivity features. The bot uses a modular provider system to integrate with external services (weather APIs, Google Calendar, Dropbox, Whisper) and a LangChain agent to orchestrate specialized tools for different types of queries.

---

## How it works (data flow)

```
1. INGESTION: Telegram message → sebastian_bot.py (authorization check)
2. ROUTING: Command detection → Direct handler OR agent routing
3. PROCESSING: Provider calls OR LangChain agent tool selection
4. EXTERNAL APIS: Weather/Calendar/Storage/Transcription providers (with retries)
5. OUTPUT: Formatted response → Telegram user
```

Detailed explanation:

When a user sends a message to the Telegram bot, sebastian_bot.py receives it and checks if the user is authorized. Commands like `/imagen`, `/calendario`, or `/nota_cata` route directly to specific handlers that may call provider methods (e.g., calendar provider for events, storage provider for file uploads). Plain text messages without commands route to sebastian_agent.py, which uses a LangChain agent with OpenAI function calling to select the appropriate tool (weather summary, wine expertise, prompt enhancement, etc.). The agent combines core tools from tools.py with provider-exposed tools from the ProviderRegistry. All external API calls go through provider classes that inherit from BaseProvider, which provides automatic retry logic (3 retries with exponential backoff), structured logging, and health checks.

---

## Tech stack

- **Language**: Python 3.8+
- **Main Frameworks/Libs**:
  - **pyTelegramBotAPI**: Telegram bot API wrapper with polling
  - **LangChain**: Agent orchestration and tool calling framework
  - **OpenAI**: GPT-4/GPT-3.5 for chat, DALL-E 3 for images, Whisper for transcription
  - **tenacity**: Automatic retry logic with exponential backoff
  - **loguru**: Structured logging across all modules
  - **requests-cache**: HTTP caching for weather API calls
  - **dropbox**: Dropbox API v2 SDK
  - **google-api-python-client**: Google Calendar API integration
- **External APIs**:
  - **OpenMeteo**: Free weather forecast API (no auth required)
  - **Google Calendar API**: Event retrieval via service account
  - **Dropbox API**: File uploads via OAuth2 refresh token
  - **OpenAI API**: GPT models, DALL-E, Whisper
- **Infrastructure**: Local/server deployment with systemd service

---

## Main CLI commands

The bot doesn't have a traditional CLI. Interaction is via Telegram commands:

| Command | What it does | Usage example |
|---------|--------------|---------------|
| `/start`, `/hola` | Welcome message | `/start` |
| `/ayuda`, `/help` | Show available commands | `/ayuda` |
| `/imagen <prompt>` | Generate DALL-E 3 image | `/imagen sunset over mountains` |
| `/calendario` | Get tomorrow's events | `/calendario` |
| `/nota_cata <wine>` | Generate wine tasting notes | `/nota_cata Rioja Reserva 2018` |
| `/resumen <topic>` | Wine blog social media post | `/resumen vintage wines guide` |
| `/3 <question>` | Direct GPT-3.5 query (bypass agent) | `/3 Explain quantum physics` |
| `/4 <question>` | Direct GPT-4 query (bypass agent) | `/4 Write a poem about AI` |
| `/restart` | Restart bot service (systemctl) | `/restart` |
| `/adduser <id>` | Add authorized user | `/adduser 123456789` |
| No command | Route to LangChain agent | `What's the weather?` |

---

## Project structure

```
sebastian/
├── providers/              # Modular provider system
│   ├── __init__.py        # ProviderRegistry (aggregates all providers)
│   ├── base.py            # BaseProvider with retry logic
│   ├── config.py          # Provider configuration classes
│   ├── weather.py         # Weather provider (OpenMeteo)
│   ├── calendar.py        # Calendar provider (Google)
│   ├── storage.py         # Storage provider (Dropbox)
│   └── transcription.py   # Transcription provider (Whisper)
├── sebastian_bot.py       # Telegram bot handlers (entry point)
├── sebastian_agent.py     # LangChain agent orchestration
├── tools.py               # Core LangChain tools (wine, Q&A, prompts)
├── utils/
│   ├── utils.py           # Config loading, authorization, utilities
│   └── logging_config.py  # Loguru configuration
├── experiments/           # Test/experimental code
├── data/                  # Static data (refranes.txt)
├── config.yaml            # Main configuration (API keys, settings)
├── config.example.yaml    # Configuration template
├── requirements.txt       # Python dependencies
├── sebastian.service      # Systemd service file
├── Makefile               # Service management shortcuts
└── docs/                  # Documentation
    └── HOW-TO-ADD-PROVIDER.md
```

**Key modules**:
- **providers/**: Self-contained provider implementations with retry logic, health checks, and logging. Each provider integrates with one external service.
- **sebastian_bot.py**: Telegram bot entry point. Handles all commands, authorization checks, and routes messages to agent or providers.
- **sebastian_agent.py**: LangChain agent using OpenAI function calling. Combines core tools + provider tools and selects the right tool based on user input.
- **tools.py**: Core LangChain chains for wine expertise (tasting notes, investigation, social media), basic Q&A, and prompt enhancement (LazyPrompt).
- **utils/utils.py**: Configuration loading (config.yaml), authorization checking, service management (systemctl), and Telegram utilities.

---

## Critical design decisions

### Provider Pattern with Registry

**Why**: Bot integrates with 4+ external services (weather, calendar, storage, transcription). Early implementation had scattered code in separate directories without consistent error handling.

**Discarded alternatives**: Direct API calls in bot handlers (no consistency), scattered modules without base class (duplicate retry logic)

**Accepted trade-off**: Slightly more complex than direct API calls, but dramatically easier to extend. Upfront abstraction pays off after 2-3 providers.

---

### Abstract vs Concrete Providers

**Why**: Some providers (weather, calendar) have multiple potential implementations, while others (Dropbox, Whisper) are tightly coupled to specific services.

**Impact**: Weather and calendar providers inherit from abstract base classes (swappable), while storage and transcription are concrete (Dropbox/Whisper-specific). Reduces complexity while maintaining flexibility where needed.

---

### Retry Logic in BaseProvider

**Why**: External APIs fail frequently due to network issues, rate limits, temporary outages. Early implementation had no retries, causing user-visible failures.

**Discarded alternatives**: Retry logic in each provider (DRY violation), no retries (poor UX)

**Accepted trade-off**: Adds 4-12 seconds delay on persistent failures (2s + 4s + 8s). Acceptable because most transient errors resolve within 1-2 retries.

---

### LangChain Agent vs Rule-Based Routing

**Why**: Need flexible tool selection based on user intent. Rule-based routing (keyword matching) is brittle and hard to extend.

**Impact**: Agent uses OpenAI function calling to select tools dynamically. Tool descriptions guide selection. Easy to add new tools without modifying routing logic.

---

### Health Checks on Startup

**Why**: Prevent bot from starting with misconfigured providers. Better to fail fast at startup than fail randomly at runtime.

**Impact**: ProviderRegistry runs health checks during initialization. Non-critical failures log warnings but don't crash bot. Critical failures (missing config) raise exceptions.

---

## Data and models

### Main data model

**Main entity**: Message (Telegram message object)

Key fields:
- `text`: str - User's message text
- `chat.id`: int - Telegram chat ID (for sending responses)
- `chat.username`: str - Username (for authorization)
- `document`: object - File attachment (for storage provider)
- `voice`: object - Voice message (for transcription provider)

**Relationships**: Each message triggers provider interactions. Providers return data (weather reports, calendar events, file URLs, transcriptions) that get formatted and sent back.

---

### Data transformation flow

```
[Telegram Message Object]
  → [Authorization check: username/ID in config.yaml]
  → [Command parsing: extract command + arguments]
  → [Route to handler OR agent]
  → [Provider/Tool execution: fetch external data]
  → [Format response: plain text or image]
  → [Telegram API: send response to user]
```

**Formats**:
- Input: Telegram message object (JSON from Telegram API)
- Provider data: Python dicts/strings (weather JSON → Spanish text, calendar events → formatted list)
- Output: Plain text or image URL sent via Telegram bot.send_message()

---

## Configuration

### Critical environment variables

**Required**:
- `OPENAI_APIKEY`: OpenAI API key for GPT/DALL-E/Whisper (used by tools.py and transcription provider)
- `OPENAI_CHAT_MODEL`: Model for specialized chains (default: gpt-4o)
- `OPENAI_AGENT_MODEL`: Model for LangChain agent (default: gpt-4o)
- `OPENAI_LZP_MODEL`: Model for prompt enhancement (default: gpt-3.5-turbo)

**Optional**:
- `telegram_apikey`: Telegram bot token (in config.yaml, required for bot)
- `weather`: Weather provider config (cities, cache, refranes file)
- `google_calendar`: Google Calendar credentials (service account file, calendar ID)
- `dropbox`: Dropbox OAuth tokens (refresh token, app key/secret)

### Configuration files

**config.yaml** (root directory, YAML format):
- Telegram API key
- OpenAI API key and org ID
- Authorized users (usernames and IDs)
- Provider configurations (weather cities, calendar settings, Dropbox tokens)
- Log folder path

See config.example.yaml for template.

---

## Current state

**Version**: 2.0 (post provider refactoring)

**Last update**: February 2026

### Features

✅ **Implemented**:
- Telegram bot with command handlers
- LangChain agent with tool orchestration
- Provider system with retry logic and health checks
- Weather provider (OpenMeteo integration)
- Calendar provider (Google Calendar integration)
- Storage provider (Dropbox file uploads)
- Transcription provider (Whisper audio-to-text)
- Wine expertise tools (tasting notes, investigation, social media)
- Image generation (DALL-E 3)
- Prompt enhancement (LazyPrompt)
- User authorization system
- Service management (systemctl restart/stop)
- Structured logging (loguru)

📋 **Known TODOs**:
- Extract city names from user questions (currently hardcoded to Madrid)
- Add provider metrics (API call counts, latency, success rates)
- Circuit breaker pattern for failing providers
- Unit tests for provider classes
- Integration tests for bot commands

---

## Typical use cases

### Case 1: Weather inquiry via agent

**Goal**: User asks about weather, agent selects weather tool

**Flow**:
1. User sends "What's the weather like today?"
2. sebastian_bot.py routes to sebastian_agent.py (no command detected)
3. Agent analyzes question → selects WeatherSummary tool
4. Tool calls OpenMeteoWeatherProvider.get_current_weather("madrid")
5. Provider fetches from OpenMeteo API (with retry logic)
6. Returns Spanish weather report + random refran
7. Agent formats response → sebastian_bot.py → Telegram

**Example**:
```
User: What's the weather like today?
Bot: Este es el resumen meteorológico para hoy en madrid.
     Hora 14:30.
     Temperatura actual 18°C.
     Precipitacion actual 0mm.
     - temperatura máxima 22°
     - temperatura mínima 12°.
     - El amanecer sera a las 07:45
     - El anochecer sera a las 19:30.
     - La máxima probabilidad de precipitacion será del 10%.
     El refran para hoy es: En abril, aguas mil.
```

---

### Case 2: Calendar events via command

**Goal**: User checks tomorrow's calendar

**Flow**:
1. User sends `/calendario`
2. sebastian_bot.py detects command → calendar_command() handler
3. Handler calls ProviderRegistry.get('calendar').get_events()
4. GoogleCalendarProvider queries Google Calendar API (with retry logic)
5. Returns formatted event list
6. Handler sends response via Telegram

**Example**:
```
User: /calendario
Bot: Título: Team Meeting
     Fecha: 2026-02-14T10:00

     Título: Lunch with John
     Fecha: 2026-02-14T13:00
```

---

### Case 3: Wine tasting notes

**Goal**: Generate professional tasting notes for wine

**Flow**:
1. User sends `/nota_cata Rioja Reserva 2018, 13.5% alcohol, aged in oak`
2. sebastian_bot.py detects command → nota_cata_command() handler
3. Handler calls WineTasteNote tool from tools.py
4. Tool uses GPT-4 with specialized wine sommelier prompt
5. Returns structured tasting note (visual, nose, palate, conclusion)
6. Handler sends response via Telegram

---

## Limitations and caveats

### Known limitations

- **City extraction**: Weather tools currently hardcoded to Madrid. City name extraction from user questions is planned but not implemented.
- **Single language**: All prompts and responses are in Spanish (except GPT direct queries which respond in user's language).
- **No conversation history**: Agent doesn't maintain conversation context across messages.
- **Rate limits**: No built-in rate limiting for OpenAI API calls.

### Non-intuitive behaviors

- **Agent verbosity**: Agent runs with verbose=True and return_intermediate_steps=True, which logs detailed execution steps. Useful for debugging but verbose in production.
- **Weather cache**: Weather data cached for 1 hour via requests_cache. May return stale data if cache isn't cleared.
- **Health check failures**: Non-critical health check failures (e.g., calendar API down) log warnings but don't prevent bot from starting. Critical failures (missing config) crash the bot.

---

## Development context

**Original motivation**: Personal assistant bot for daily tasks (weather, calendar, file uploads) with conversational AI capabilities powered by GPT models.

**Evolution**: Started with simple command handlers → added LangChain agent for flexible tool selection → refactored from scattered provider directories to centralized provider system with retry logic and health checks.

**Current usage**:
- Frequency: Daily
- Context: Personal Telegram bot for productivity (weather checks, calendar, file sharing) and creative tasks (wine tasting notes, image generation)

---

## Key code patterns

### Most common usage pattern

```python
# Accessing a provider in sebastian_bot.py
def some_command_handler(message):
    if authorized(message.chat.username, message.chat.id):
        # Get provider from registry
        provider = provider_registry.get('calendar')
        if provider:
            # Call provider method (retry logic automatic)
            events = provider.get_events(days_ahead=1)
            bot.reply_to(message, events)
        else:
            bot.reply_to(message, "Calendar provider not configured")
```

---

### Extension pattern

```python
# How to add a new provider (see docs/HOW-TO-ADD-PROVIDER.md)

# 1. Create config class in providers/config.py
class NewProviderConfig(ProviderConfig):
    def __init__(self, config_dict: dict):
        self.api_key = config_dict.get('api_key')

    def validate(self) -> bool:
        if not self.api_key:
            raise ValueError("api_key not specified")
        return True

# 2. Create provider class in providers/new_provider.py
class NewProvider(BaseProvider):
    def __init__(self, config: NewProviderConfig):
        super().__init__(config)
        self.client = SomeAPIClient(config.api_key)

    def health_check(self) -> bool:
        # Verify connectivity
        self.client.ping()
        return True

    def some_method(self):
        # Use _call_with_retry for API calls
        return self._call_with_retry(self.client.fetch_data)

# 3. Register in providers/__init__.py
if 'new_provider' in self.config:
    config = NewProviderConfig(self.config['new_provider'])
    self.providers['new_provider'] = NewProvider(config)
```

---

## Notes for Claude Web

**Context for architecture discussions**:
- Provider pattern is central to extensibility. All external service integrations should go through providers.
- LangChain agent uses OpenAI function calling. Tool descriptions are critical for proper selection.
- Bot is designed for personal use (single user or small group). No multi-tenancy or per-user state.

**Pending decisions**:
- Should weather tools extract city names dynamically or maintain hardcoded cities?
- Should providers expose metrics (call counts, latency) for monitoring?
- Should health checks be mandatory (crash on failure) or optional (log warnings)?

**Improvement areas**:
- Provider system could benefit from circuit breaker pattern
- Agent could use conversation history for context
- Tool descriptions could be generated dynamically from provider metadata

---

## Notes for Claude Code

**Project conventions**:
- All providers inherit from BaseProvider
- All API calls should use BaseProvider._call_with_retry()
- Use loguru for all logging (not print statements)
- Configuration validation happens in ProviderConfig.validate()
- Health checks should be simple (ping, list, or minimal API call)

**Areas requiring attention**:
- weather/ and mycalendar/ directories are deprecated (code migrated to providers/)
- tools.py chains use older LangChain syntax (PromptTemplate + ChatOpenAI), could be modernized
- No unit tests for providers yet (integration tests via manual Telegram testing)

**When contributing**:
- Follow provider pattern for new integrations (see docs/HOW-TO-ADD-PROVIDER.md)
- Add health checks to verify connectivity
- Use structured logging with context (logger.info(f"Action completed: {details}"))
- Test authorization system (only authorized users can use commands)
- Update config.example.yaml when adding new config options

---

*Last updated: February 13, 2026*
*Generated from: Provider refactoring completion (Phase 5/5)*
