import sys
from pathlib import Path

from google.adk.agents import Agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import tickets_tool  # noqa: E402
from config.settings import settings  # noqa: E402

root_agent = Agent(
    name="ticket_watcher",
    model=settings.gemini_model,
    instruction=(
        "You track ticket state changes for FlowMate: tickets that haven't "
        "moved in 24+ hours, blocked items, and missing assignees. "
        "STUB: full behavior lands in the Aug 24 milestone."
    ),
    tools=[tickets_tool],
)
