import sys
from pathlib import Path

from google.adk.agents import Agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import activity_tool, upcoming_tickets_tool  # noqa: E402
from config.settings import settings  # noqa: E402

root_agent = Agent(
    name="personal_standup",
    model=settings.gemini_model,
    instruction=(
        "Generate ONE engineer's own daily standup -- the exact engineer name is "
        "given in the request. Call get_developer_activity(engineer=<that name>) "
        "for their recently closed, active/in-review, and blocked tickets, and "
        "get_upcoming_tickets(engineer=<that name>) for their upcoming work -- pass "
        "the exact name given, do not guess or normalize it.\n\n"
        "Write a short Done / Doing / Blocked / Next update in second person "
        "(\"You closed...\", \"You're blocked on...\"), referencing real ticket IDs. "
        "Keep each section to a few lines. Omit a section if it's empty rather than "
        "inventing content. This is a single person's own read of their day -- no "
        "team-wide comparison, no cross-referencing other engineers."
    ),
    tools=[activity_tool, upcoming_tickets_tool],
)
