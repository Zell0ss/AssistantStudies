"""Anthropic tool definitions for the Orchestrator."""
from .calendar_tools import CALENDAR_TOOLS
from .weather_tools import WEATHER_TOOLS
from .inventory_tools import INVENTORY_TOOLS
from .list_tools import LIST_TOOLS
from .notes_tools import NOTES_TOOLS
from .clarification_tools import CLARIFICATION_TOOLS
from .tasks_tools import TASKS_TOOLS
from .docs_tools import DOCS_TOOLS

ALL_TOOLS = (
    CALENDAR_TOOLS +
    WEATHER_TOOLS +
    INVENTORY_TOOLS +
    LIST_TOOLS +
    NOTES_TOOLS +
    CLARIFICATION_TOOLS +
    TASKS_TOOLS +
    DOCS_TOOLS
)
