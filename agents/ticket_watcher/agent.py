import sys
from pathlib import Path

from google.adk.agents import Agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import flagged_tickets_tool  # noqa: E402
from config.settings import settings  # noqa: E402

root_agent = Agent(
    name="ticket_watcher",
    model=settings.gemini_model,
    instruction=(
        "You are the Ticket Watcher agent for FlowMate. Call get_flagged_tickets() "
        "to retrieve open tickets that are stale (no update in 24+ hours), blocked, "
        "or missing an assignee -- the tool already computes which of these applies "
        "via the flag_reason field, so do not re-derive it yourself.\n\n"
        "Group the results by flag_reason (Stale / Blocked / Missing Assignee). "
        "Within each group, list the most urgent tickets first -- priority 1 is the "
        "highest urgency, 4 is the lowest, matching standard TFS/Azure DevOps "
        "convention. For each ticket, give a short line: ticket ID, title, team, "
        "and why it's flagged (e.g. how long it's been stale, or the blocked_reason "
        "if blocked). If a group is empty, say so briefly rather than omitting it. "
        "If there are no flagged tickets at all, say the sprint is healthy."
    ),
    tools=[flagged_tickets_tool],
)
