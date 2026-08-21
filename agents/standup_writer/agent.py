import sys
from pathlib import Path

from google.adk.agents import Agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import tickets_tool  # noqa: E402
from config.settings import settings  # noqa: E402

root_agent = Agent(
    name="standup_writer",
    model=settings.gemini_model,
    instruction=(
        "You read each developer's ticket activity and write their standup: "
        "done, doing, blocked. "
        "STUB: full behavior lands in the Aug 26 milestone."
    ),
    tools=[tickets_tool],
)
