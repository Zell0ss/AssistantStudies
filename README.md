# Sebastian AI Assistant Bot

A comprehensive Telegram bot powered by OpenAI's GPT models that provides various AI-driven functionalities including conversational AI, image generation, weather reports, wine expertise, and productivity features.

## Features

### Core Functionality
- **Multi-GPT Integration**: Supports both GPT-3.5 and GPT-4 models for different use cases
- **Image Generation**: DALL-E 3 powered image creation from text prompts
- **LangChain Agent System**: Advanced tool-calling capabilities with specialized chains
- **User Authorization**: Secure access control with authorized user management

### Specialized Capabilities
- **Weather Integration**: Real-time weather forecasts and detailed meteorological reports
- **Wine Expertise**: Professional sommelier-level wine tasting notes and wine research
- **Calendar Integration**: Google Calendar API integration for event management
- **File Management**: Dropbox integration for document uploads and storage
- **Social Media Content**: Automated social media post generation for wine blog promotion

### Productivity Features
- **Service Management**: Remote bot restart/stop functionality
- **Usage Monitoring**: OpenAI API usage tracking
- **Logging System**: Comprehensive logging for debugging and monitoring
- **Template System**: Pre-configured templates for wine tasting notes

## Installation

### Prerequisites
- Python 3.8+
- Telegram Bot Token
- OpenAI API Key
- Google Calendar API credentials (optional)
- Dropbox API credentials (optional)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd AssistantStudies
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**
   - Copy `config.example.yaml` to `config.yaml`
   - Configure your API keys and settings in `config.yaml`
   - Never commit your actual configuration file with API keys

4. **Google Calendar Setup** (Optional)
   - Place your Google API credentials in the `mycalendar/` folder
   - Follow Google Calendar API documentation for authentication setup

5. **Environment Variables**
   - Create a `.env` file with your OpenAI API configurations
   - Set `OPENAI_CHAT_MODEL`, `OPENAI_AGENT_MODEL`, etc.

## Usage

### Running the Bot
```bash
python sebastian_bot.py
```

### Available Commands

- `/start` or `/hola` - Welcome message
- `/ayuda` or `/help` - Display all available commands
- `/restart` - Restart the bot service (authorized users only)
- `/stop` - Stop the bot service (authorized users only)
- `/id_me` or `/whoami` - Get your Telegram user information
- `/adduser <user_id>` - Add a user to authorized list (authorized users only)
- `/imagen <prompt>` - Generate an image using DALL-E 3
- `/calendario` - Get tomorrow's calendar events
- `/consumo` - Link to OpenAI usage dashboard
- `/plantilla` - Get wine tasting note template
- `/nota_cata <wine_data>` - Generate professional wine tasting notes
- `/resumen <article_topic>` - Create social media content for wine blog
- `/3 <question>` - Direct query to GPT-3.5
- `/4 <question>` - Direct query to GPT-4

### System Service Setup

For production deployment, configure the bot as a systemd service:

1. **Edit the service file**
   ```bash
   # Edit sebastian.service with your paths
   WorkingDirectory=/path/to/your/project
   ExecStart=/path/to/your/venv/bin/python sebastian_bot.py
   ```

2. **Install and start the service**
   ```bash
   sudo cp sebastian.service /etc/systemd/system/
   sudo systemctl enable sebastian.service
   sudo systemctl daemon-reload
   sudo systemctl start sebastian.service
   ```

## Project Structure

```
AssistantStudies/
├── sebastian_bot.py              # Main Telegram bot implementation
├── sebastian_agent.py            # LangChain agent executor
├── tools.py                      # Specialized AI chains and tools
├── config.yaml                   # Configuration file (not tracked)
├── config.example.yaml           # Example configuration template
├── requirements.txt              # Python dependencies
├── sebastian.service             # Systemd service configuration
├── LICENSE                       # Project license
├── README.md                     # This file
├── Makefile                      # Build automation
├── test_oauth.py                 # OAuth testing utilities
├── token.json                    # OAuth tokens (not tracked)
├── credentials.json              # API credentials (not tracked)
├── tester.py                     # Testing utilities
├── tester.ipynb                  # Jupyter testing notebook
├── agent_creation.ipynb          # Agent development notebook
│
├── utils/                        # Utility functions
│   ├── __init__.py
│   └── utils.py                  # Configuration and helper functions
│
├── weather/                      # Weather integration module
│   ├── __init__.py
│   ├── openmeteo.py             # OpenMeteo API integration
│   └── refranes.txt             # Weather sayings database
│
├── mycalendar/                   # Google Calendar integration
│   ├── __init__.py
│   ├── googlecal.py             # Calendar API functions
│   ├── credentials.json         # Google API credentials (not tracked)
│   └── api-access.json          # API access tokens (not tracked)
│
├── mydropbox/                    # Dropbox integration
│   ├── upload_dropbox.py        # File upload functionality
│   ├── apicalls.md              # API documentation
│   └── test.txt                 # Test file
│
├── mp3totext/                    # Audio transcription module
│   ├── whisper_openai.py        # Whisper API integration
│   └── [audio files]            # Sample audio files and transcripts
│
├── logs/                         # Application logs
│   └── app.log                  # Main application log file
│
└── legacytests/                  # Legacy testing and experimental code
    ├── chatgpt_text.py          # Text-based ChatGPT testing
    ├── image_generation.py      # Image generation experiments
    ├── libraries.sh             # Installation scripts
    ├── piper_test.py            # TTS testing
    ├── radar_graph_generation.* # Data visualization experiments
    └── Voice/                   # Voice processing experiments
        ├── chatgpt_voice*.py    # Various voice implementations
        ├── text_to_voice.py     # TTS functionality
        ├── voice_to_text.py     # STT functionality
        └── *.onnx               # Voice model files
```

## Architecture

### Core Components
- **sebastian_bot.py**: Main Telegram bot implementation with command handlers
- **sebastian_agent.py**: LangChain agent executor managing tool orchestration
- **tools.py**: Specialized AI chains for different domains (weather, wine, etc.)
- **utils/utils.py**: Configuration management and utility functions

### Specialized Modules
- **weather/**: Real-time weather forecasting and meteorological reporting
- **mycalendar/**: Google Calendar API integration for event management
- **mydropbox/**: Dropbox API integration for file storage and sharing
- **mp3totext/**: Audio transcription using OpenAI Whisper

### Configuration Files
- **config.yaml**: Main configuration (API keys, settings) - excluded from version control
- **config.example.yaml**: Template showing required configuration structure
- **sebastian.service**: Systemd service configuration for production deployment

## Security Considerations

- All API keys must be stored in configuration files, never in code
- User authorization system prevents unauthorized access
- Logging system tracks all bot interactions
- Service management commands are restricted to authorized users

## Contributing

1. Fork the repository
2. Create a feature branch
3. Ensure all sensitive information is properly configured
4. Submit a pull request

## References

- [Microsoft IoT Audio Setup Guide](https://github.com/microsoft/IoT-For-Beginners/blob/main/6-consumer/lessons/1-speech-recognition/pi-audio.md)
- [Raspberry Pi ChatGPT Setup](https://pimylifeup.com/raspberry-pi-chatgpt/)
- [OpenAI API Usage Dashboard](https://platform.openai.com/usage)
- [OpenAI API Pricing](https://openai.com/pricing#language-models)

## License

See LICENSE file for details.