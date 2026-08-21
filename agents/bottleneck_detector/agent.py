import sys
from pathlib import Path

from google.adk.agents import Agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import (  # noqa: E402
    pr_reviews_tool,
    tickets_tool,
    velocity_tool,
)
from config.settings import settings  # noqa: E402

root_agent = Agent(
    name="bottleneck_detector",
    model=settings.gemini_model,
    instruction=(
        "You reason across historical sprint data (tickets, PR reviews, and "
        "team velocity) to flag tickets with a high probability of missing "
        "the sprint deadline, days before it happens. "
        "STUB: full behavior lands in the Aug 27 milestone."
    ),
    tools=[tickets_tool, pr_reviews_tool, velocity_tool],
)
