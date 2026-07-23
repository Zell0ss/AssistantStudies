"""Anthropic tool definitions for the Orchestrator."""
from .calendar_tools import CALENDAR_TOOLS, FAMILY_SUMMARY as CALENDAR_SUMMARY
from .weather_tools import WEATHER_TOOLS, FAMILY_SUMMARY as WEATHER_SUMMARY
from .inventory_tools import INVENTORY_TOOLS, FAMILY_SUMMARY as INVENTORY_SUMMARY
from .list_tools import LIST_TOOLS, FAMILY_SUMMARY as LIST_SUMMARY
from .notes_tools import NOTES_TOOLS, FAMILY_SUMMARY as NOTES_SUMMARY
from .clarification_tools import CLARIFICATION_TOOLS, FAMILY_SUMMARY as CLARIFICATION_SUMMARY
from .tasks_tools import TASKS_TOOLS, FAMILY_SUMMARY as TASKS_SUMMARY
from .docs_tools import DOCS_TOOLS, FAMILY_SUMMARY as DOCS_SUMMARY
from .memory_tools import MEMORY_TOOLS, FAMILY_SUMMARY as MEMORY_SUMMARY

ALL_TOOLS = (
    CALENDAR_TOOLS +
    WEATHER_TOOLS +
    INVENTORY_TOOLS +
    LIST_TOOLS +
    NOTES_TOOLS +
    CLARIFICATION_TOOLS +
    TASKS_TOOLS +
    DOCS_TOOLS +
    MEMORY_TOOLS
)

# Each entry pairs a family's tool list with its human-curated summary line.
# The coverage guardrail test sums tool-list lengths here against len(ALL_TOOLS)
# to catch a family added to ALL_TOOLS without a matching summary registered.
_TOOL_FAMILIES = [
    (CALENDAR_TOOLS, CALENDAR_SUMMARY),
    (WEATHER_TOOLS, WEATHER_SUMMARY),
    (INVENTORY_TOOLS, INVENTORY_SUMMARY),
    (LIST_TOOLS, LIST_SUMMARY),
    (NOTES_TOOLS, NOTES_SUMMARY),
    (CLARIFICATION_TOOLS, CLARIFICATION_SUMMARY),
    (TASKS_TOOLS, TASKS_SUMMARY),
    (DOCS_TOOLS, DOCS_SUMMARY),
    (MEMORY_TOOLS, MEMORY_SUMMARY),
]


def build_capabilities_digest() -> str:
    """Aggregate each tool family's FAMILY_SUMMARY into a short digest for Alfred's prompts."""
    return "\n".join(f"- {summary}" for _, summary in _TOOL_FAMILIES)
