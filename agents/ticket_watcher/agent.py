import sys
from pathlib import Path

from google.adk.agents import Agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import flagged_ticket_counts_tool, flagged_tickets_tool  # noqa: E402
from config.settings import settings  # noqa: E402

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
        "Start with a one-line summary of the totals from get_flagged_ticket_counts() "
        "(e.g. '441 tickets need attention: 380 stale, 45 blocked, 16 unassigned').\n\n"
        "Then, for each flag_reason group (Stale / Blocked / Missing Assignee), list "
        "the tickets from get_flagged_tickets() that fall in it, most urgent first -- "
        "priority 1 is the highest urgency, 4 is the lowest, matching standard "
        "TFS/Azure DevOps convention. Give each ticket ONE short line: ticket ID, "
        "title, team, and why it's flagged (how long stale, or the blocked_reason). "
        "Keep it scannable -- no paragraphs per ticket.\n\n"
        "Make clear you're showing the most urgent items, not all of them, and say "
        "how many more exist in that group per the counts. If a group has no tickets "
        "at all, say so briefly. If nothing is flagged anywhere, say the sprint is "
        "healthy."
    ),
    tools=[flagged_ticket_counts_tool, flagged_tickets_tool],
)
