import sys
from pathlib import Path

from google.adk.agents import Agent
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import pending_reviews_tool  # noqa: E402
from config.settings import settings  # noqa: E402


class ReviewNudgerFinding(BaseModel):
    title: str = Field(description="e.g. 'PR-872707 -- 1,348h waiting on Angie Henderson'.")
    body: str = Field(description="The ready-to-send nudge message, 1-2 sentences, specific to this PR.")
    teams: list[str] = Field(description="The team this PR belongs to (usually one team).")
    reviewers: list[str] = Field(description="The reviewer(s) this finding concerns.")


class ReviewNudgerFindings(BaseModel):
    findings: list[ReviewNudgerFinding]


root_agent = Agent(
    name="review_nudger",
    model=settings.gemini_model,
    instruction=(
        "You are the Review Nudger agent for FlowMate. Call get_pending_reviews() "
        "to retrieve PRs that have been awaiting review past the threshold -- the "
        "tool already computes hours_waiting and looks up each PR's sprint_end_date, "
        "so do not re-derive either yourself.\n\n"
        "Emit one finding per pending PR, most overdue first (highest hours_waiting). "
        "The body is a short, ready-to-send nudge message addressed to the reviewer: "
        "name the ticket, how long it's been waiting for review, and the sprint end "
        "date -- ask them to review before the sprint closes. Keep each nudge to 1-2 "
        "sentences, specific to that PR, not a generic template. If there are no "
        "pending reviews at all, return no findings.\n\n"
        "For every finding, list the PR's team in `teams` and its reviewer in "
        "`reviewers`."
    ),
    tools=[pending_reviews_tool],
    output_schema=ReviewNudgerFindings,
)
