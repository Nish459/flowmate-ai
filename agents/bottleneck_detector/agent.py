import sys
from pathlib import Path

from google.adk.agents import Agent
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import (  # noqa: E402
    at_risk_tickets_tool,
    bug_close_rate_trend_tool,
    reviewer_latency_tool,
    team_type_close_rates_tool,
)
from config.settings import settings  # noqa: E402


class BottleneckFinding(BaseModel):
    title: str = Field(description="e.g. 'TFS-10634 -- High risk (0 days left)'.")
    body: str = Field(description="1-3 sentences naming the specific signal(s) that drove the risk call, with real numbers.")
    risk_level: str = Field(description="One of 'High', 'Medium', 'Low'.")
    teams: list[str] = Field(description="The team(s) this finding's ticket(s) belong to.")
    work_item_types: list[str] = Field(description="The work item type(s) involved, e.g. ['Bug'].")
    states: list[str] = Field(description="The ticket state(s) involved, e.g. ['Blocked'].")


class BottleneckFindings(BaseModel):
    findings: list[BottleneckFinding]


root_agent = Agent(
    name="bottleneck_detector",
    model=settings.gemini_model,
    instruction=(
        "You are the Bottleneck Detector agent for FlowMate -- the differentiator "
        "over simple rule-based alerting (an overdue ticket flag alone is not "
        "interesting; a ticket that's overdue AND matches a historically slow "
        "pattern is). Call all four tools before answering:\n\n"
        "- get_open_tickets_at_risk() -- open tickets in the current sprint, with "
        "days_until_sprint_end, tags, priority, blocked status, and reviewer/"
        "review_status (reviewer may be null -- that just means no review signal "
        "exists yet for that ticket).\n"
        "- get_team_type_close_rates() -- historical close_rate and "
        "avg_cycle_time_hours per team x work_item_type, from finished sprints "
        "only.\n"
        "- get_reviewer_latency_stats() -- avg_latency_hours and "
        "changes_requested_rate per reviewer, from completed reviews only.\n"
        "- get_bug_close_rate_by_sprint() -- Bug close rate per sprint in "
        "chronological order, so you can see if recent sprints trend worse.\n\n"
        "For each at-risk ticket, cross-reference it against the other three "
        "tools' results -- don't just restate that it's open:\n"
        "1. Does its (team, work_item_type) pair have a close_rate well below "
        "other pairs, or a much higher avg_cycle_time_hours? (Ignore pairs with "
        "few tickets -- the tool already filters those out.)\n"
        "2. Do its tags mention things like migration or database work, and does "
        "that combination line up with a slow (team, work_item_type) pair from "
        "signal 1?\n"
        "3. If it has a reviewer, is that reviewer's avg_latency_hours or "
        "changes_requested_rate much higher than their peers in the stats list?\n"
        "4. If it's a Bug, do the most recent sprints in the trend show a "
        "meaningfully lower close rate than earlier ones?\n\n"
        "Emit one finding per ticket that has at least one real signal from above -- "
        "leave tickets with none of these signals out entirely rather than flagging "
        "everything; a list that flags every ticket is worthless. Combine whichever "
        "signals apply into a High/Medium/Low `risk_level`, and put the specific "
        "signal(s) that drove it in the body, citing actual numbers (e.g. 'this "
        "team+type combo has a 32% close rate vs 70%+ elsewhere') and "
        "days_until_sprint_end. If nothing in the current sprint shows real risk "
        "signal, return no findings rather than inventing one.\n\n"
        "For every finding, list its ticket's team in `teams`, work_item_type in "
        "`work_item_types`, and state in `states`."
    ),
    tools=[
        at_risk_tickets_tool,
        team_type_close_rates_tool,
        reviewer_latency_tool,
        bug_close_rate_trend_tool,
    ],
    output_schema=BottleneckFindings,
)
