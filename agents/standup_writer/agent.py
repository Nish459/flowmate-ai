import sys
from pathlib import Path

from google.adk.agents import Agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import activity_tool, upcoming_tickets_tool  # noqa: E402
from config.settings import settings  # noqa: E402

root_agent = Agent(
    name="standup_writer",
    model=settings.gemini_model,
    instruction=(
        "You are the Standup Writer agent for FlowMate. Call get_developer_activity() "
        "to get each engineer's recently closed, active/in-review, and blocked "
        "tickets, and call get_upcoming_tickets() (no arguments -- you want every "
        "engineer's upcoming work) to get each engineer's not-yet-started tickets. "
        "Both tools already return every assigned engineer's rows in one call, "
        "keyed by assigned_to -- group by that field yourself, don't call either "
        "tool per person.\n\n"
        "For each engineer, write a standup block with four sections:\n"
        "Done -- tickets that were Resolved/Closed recently\n"
        "Doing -- tickets that are Active or In Review\n"
        "Blocked -- tickets that are blocked, including the blocked_reason\n"
        "Next -- New tickets not yet started, most urgent (lowest priority number) first\n\n"
        "Each line should be short: ticket ID, title, and brief context (e.g. how "
        "long blocked, or the priority for Next items). Omit a section for an "
        "engineer with nothing in it rather than inventing content. If an engineer "
        "has nothing in any section, skip them entirely."
    ),
    tools=[activity_tool, upcoming_tickets_tool],
)
