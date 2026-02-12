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
Telegram Message → sebastian_bot.py → sebastian_agent.py → tools.py → OpenAI/APIs
                    (handlers)        (LangChain agent)   (specialized chains)
```

### Key Files

**sebastian_bot.py** - Main entry point
- Telegram bot command handlers (`/start`, `/imagen`, `/calendario`, etc.)
- Authorization checking via `utils.utils.authorized()`
- Routes default messages (no command) to the LangChain agent
- Direct GPT calls for `/3` (GPT-3.5) and `/4` (GPT-4) commands

**sebastian_agent.py** - LangChain orchestration
- Creates the main agent using `create_openai_functions_agent()`
- Uses `AgentExecutor` with tools from `tools.py`
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

**weather/openmeteo.py**
- OpenMeteo API integration with caching (1-hour cache via requests_cache)
- Supports multiple cities via `CITIES` dict (Madrid, Gijón, Oviedo, Magán)
- Fetches current temp, precipitation, daily min/max, sunrise/sunset
- Returns weather report + random Spanish wine saying from `refranes.txt`

**mycalendar/googlecal.py**
- Google Calendar API integration
- Retrieves tomorrow's events via `get_events()`

**mydropbox/upload_dropbox.py**
- Dropbox API file upload functionality
- Called from bot when documents are sent to chat

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

## Logging

- Log file location: `{config["logfolder"]}/app.log`
- Configured in both sebastian_bot.py and utils/utils.py
- Uses Python logging module with basicConfig

## Important Notes

- The bot uses `bot.infinity_polling()` for continuous operation
- GPT models are configurable: `GPT4 = "gpt-4o"`, `GPT3 = "gpt-3.5-turbo"`
- DALL-E model: `DALLE3 = "dall-e-3"` (1024x1024, standard quality)
- Agent system runs with `verbose=True` and `return_intermediate_steps=True`
- Weather reports include random Spanish wine sayings for cultural flavor
- All sensitive data (API keys, tokens) must be in config.yaml or .env, never in code
