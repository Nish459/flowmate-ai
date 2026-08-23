import sys
from pathlib import Path

from google.adk.agents import Agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import pending_reviews_tool  # noqa: E402
from config.settings import settings  # noqa: E402

root_agent = Agent(
    name="review_nudger",
    model=settings.gemini_model,
    instruction=(
        "You are the Review Nudger agent for FlowMate. Call get_pending_reviews() "
        "to retrieve PRs that have been awaiting review past the threshold -- the "
        "tool already computes hours_waiting and looks up each PR's sprint_end_date, "
        "so do not re-derive either yourself.\n\n"
        "Group the results by team. Within each team, list the most overdue PRs "
        "first (highest hours_waiting). For each PR, draft a short, ready-to-send "
        "nudge message addressed to the reviewer: name the ticket, how long it's "
        "been waiting for review, and the sprint end date -- ask them to review "
        "before the sprint closes. Keep each nudge to 1-2 sentences, specific to "
        "that PR, not a generic template. If a team has no pending reviews, say so "
        "briefly. If there are none at all, say review turnaround is healthy."
    ),
    tools=[pending_reviews_tool],
)
