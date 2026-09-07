import sys
from pathlib import Path

from google.adk.agents import Agent
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import flagged_ticket_counts_tool, flagged_tickets_tool  # noqa: E402
from config.settings import settings  # noqa: E402


class TicketWatcherFinding(BaseModel):
    title: str = Field(description="Short label, e.g. '170 stale tickets, concentrated in DevOps'.")
    body: str = Field(description="A few sentences with the most urgent examples. Reference real ticket IDs.")
    teams: list[str] = Field(description="Every team that appears among the tickets this finding covers.")
    flag_reasons: list[str] = Field(
        description="Subset of ['stale', 'blocked', 'missing_assignee'] this finding is about."
    )


class TicketWatcherFindings(BaseModel):
    findings: list[TicketWatcherFinding]


root_agent = Agent(
    name="ticket_watcher",
    model=settings.gemini_model,
    instruction=(
        "You are the Ticket Watcher agent for FlowMate. Call BOTH tools before "
        "answering:\n"
        "- get_flagged_ticket_counts() -- the full total per flag reason across the "
        "whole backlog.\n"
        "- get_flagged_tickets() -- the most urgent flagged tickets in detail. This "
        "list is deliberately capped, so it is a sample of the most urgent ones, NOT "
        "the complete set. The tool already computes which flag applies via the "
        "flag_reason field, so do not re-derive it yourself.\n\n"
        "Produce one finding PER flag_reason that has any tickets (stale / blocked / "
        "missing_assignee) -- do not skip a category just because another one is "
        "bigger. Each finding's title should state the total count for that reason "
        "(from get_flagged_ticket_counts()) and call out which team(s) it's "
        "concentrated in, if any. The body should name the most urgent 3-5 examples "
        "from get_flagged_tickets() with ticket ID, team, and why it's flagged (how "
        "long stale, or the blocked_reason) -- not every ticket, just enough to be "
        "concrete. If a team is disproportionately represented within a reason "
        "(e.g. most of the blocked tickets are DevOps), say so explicitly -- that's "
        "more useful than a flat list.\n\n"
        "For every finding, list every team it concerns in `teams`, and which "
        "flag_reason(s) it's about in `flag_reasons` (usually just one, since each "
        "finding covers one reason)."
    ),
    tools=[flagged_ticket_counts_tool, flagged_tickets_tool],
    output_schema=TicketWatcherFindings,
)
