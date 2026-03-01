"""Anthropic tool definitions for the Orchestrator."""
from .calendar_tools import CALENDAR_TOOLS
from .weather_tools import WEATHER_TOOLS
from .inventory_tools import INVENTORY_TOOLS
from .shopping_tools import SHOPPING_TOOLS
from .notes_tools import NOTES_TOOLS

ALL_TOOLS = (
    CALENDAR_TOOLS +
    WEATHER_TOOLS +
    INVENTORY_TOOLS +
    SHOPPING_TOOLS +
    NOTES_TOOLS
)
