"""FlowMate orchestrator: Ticket Watcher + Bottleneck Detector run in
parallel, then feed into Review Nudger + Standup Writer, per the project
architecture. Run with `adk run agents/orchestrator` or `adk web`.
"""

import sys
from pathlib import Path

from google.adk.agents import ParallelAgent, SequentialAgent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.bottleneck_detector.agent import root_agent as bottleneck_detector  # noqa: E402
from agents.review_nudger.agent import root_agent as review_nudger  # noqa: E402
from agents.standup_writer.agent import root_agent as standup_writer  # noqa: E402
from agents.ticket_watcher.agent import root_agent as ticket_watcher  # noqa: E402

_watch_and_detect = ParallelAgent(
    name="watch_and_detect",
    sub_agents=[ticket_watcher, bottleneck_detector],
)
_nudge_and_summarize = SequentialAgent(
    name="nudge_and_summarize",
    sub_agents=[review_nudger, standup_writer],
)

root_agent = SequentialAgent(
    name="flowmate_orchestrator",
    sub_agents=[_watch_and_detect, _nudge_and_summarize],
)
