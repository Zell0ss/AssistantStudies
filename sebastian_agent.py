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
