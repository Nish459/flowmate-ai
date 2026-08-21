import sys
from pathlib import Path

from google.adk.agents import Agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import pr_reviews_tool  # noqa: E402
from config.settings import settings  # noqa: E402

root_agent = Agent(
    name="review_nudger",
    model=settings.gemini_model,
    instruction=(
        "You find PRs sitting without review past a threshold and draft a "
        "follow-up message that references the sprint end date. "
        "STUB: full behavior lands in the Aug 26 milestone."
    ),
    tools=[pr_reviews_tool],
)
