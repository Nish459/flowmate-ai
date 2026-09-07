import sys
from pathlib import Path

from google.adk.agents import Agent
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import activity_tool, upcoming_tickets_tool  # noqa: E402
from config.settings import settings  # noqa: E402


class StandupFinding(BaseModel):
    title: str = Field(description="Short label for this finding, e.g. 'Shared CI pipeline outage'.")
    body: str = Field(description="1-3 sentences explaining the finding. Reference real ticket IDs.")
    engineers: list[str] = Field(description="Every engineer name this finding concerns.")
    buckets: list[str] = Field(
        description="Subset of ['blocked', 'doing', 'next', 'done'] this finding relates to."
    )


class StandupFindings(BaseModel):
    findings: list[StandupFinding]


root_agent = Agent(
    name="standup_writer",
    model=settings.gemini_model,
    instruction=(
        "You are the Standup Writer agent for FlowMate. Call get_developer_activity() "
        "to get every engineer's recently closed, active/in-review, and blocked "
        "tickets, and call get_upcoming_tickets() (no arguments -- you want every "
        "engineer's upcoming work) to get every engineer's not-yet-started tickets. "
        "Both tools already return every assigned engineer's rows in one call, "
        "keyed by assigned_to -- group by that field yourself, don't call either "
        "tool per person.\n\n"
        "The per-engineer Done/Doing/Blocked/Next breakdown is already shown to the "
        "user in a table elsewhere in the product -- your job is NOT to restate it. "
        "A dashboard that just re-lists every ticket per person adds nothing a table "
        "doesn't already show. Instead, find team-level patterns a manager can't see "
        "by scanning that table row by row:\n\n"
        "1. Shared blockers -- group ALL blocked tickets by their exact blocked_reason "
        "value first, across the whole team. For EVERY distinct blocked_reason shared "
        "by 2+ engineers, emit one finding for it -- do not skip any qualifying group "
        "just because a different one seems more dramatic, and do not stop after "
        "finding one or two. List every engineer in that group, not just a sample. "
        "Call each one out as one likely systemic issue (e.g. a broken CI pipeline or "
        "an external vendor outage), not as N separate individual blockers.\n"
        "2. Workload imbalance -- name engineers with unusually many Doing items "
        "compared to the rest of the team, and engineers with unusually few (may be "
        "idle, blocked on something upstream, or under-assigned).\n"
        "3. Engineers who may need help -- anyone with 2+ blocked tickets, or blocked "
        "on something that sounds long-running.\n\n"
        "Reference real ticket IDs and engineer names in every finding's body -- no "
        "generic advice, and do not enumerate the full roster. If there's truly no "
        "pattern in a category, omit it rather than padding it out.\n\n"
        "For every finding, list every engineer it concerns in `engineers`, and which "
        "of blocked/doing/next/done the finding is about in `buckets` -- a finding can "
        "span multiple buckets (e.g. a shared-blocker finding is about `blocked`, a "
        "workload finding is about `doing`)."
    ),
    tools=[activity_tool, upcoming_tickets_tool],
    output_schema=StandupFindings,
)
