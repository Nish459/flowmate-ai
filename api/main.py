"""FlowMate FastAPI backend -- the HTTP boundary between the (future) React
frontend and FlowMate's agents/Firestore/BigQuery. Depends on agents/ and
config/ only, never the reverse (see CLAUDE.md's module-boundary rule).
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.bottleneck_detector.agent import root_agent as bottleneck_detector  # noqa: E402
from agents.common.agent_runner import run_agent_once  # noqa: E402
from agents.common.firestore_client import get_standup_history, write_standup_snapshot  # noqa: E402
from agents.review_nudger.agent import root_agent as review_nudger  # noqa: E402
from agents.standup_writer.agent import root_agent as standup_writer  # noqa: E402
from agents.standup_writer.snapshot import build_daily_snapshots  # noqa: E402
from agents.ticket_watcher.agent import root_agent as ticket_watcher  # noqa: E402

app = FastAPI(title="FlowMate API")

# Same prompts already verified live against each agent in its own milestone.
_SCAN_AGENTS = {
    "ticket_watcher": (ticket_watcher, "What tickets need attention right now?"),
    "bottleneck_detector": (bottleneck_detector, "Which tickets are at risk of missing the deadline?"),
    "review_nudger": (review_nudger, "What needs a nudge?"),
    "standup_writer": (standup_writer, "Give me today's standups."),
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/scan")
async def scan() -> dict:
    """Run all 4 agents sequentially and return each one's response, keyed
    by agent name -- drives the demo dashboard's 4 panels.

    Sequential, not concurrent: the Gemini Developer API key this project
    uses sits on the free tier (5 req/min for gemini-3.6-flash), and running
    4 agents at once blows past that immediately in practice. run_agent_once
    already retries transient errors (429/503) with backoff; a per-agent
    try/except here still isolates a failure that survives those retries to
    just that one panel instead of 500ing the whole response.
    """
    results = {}
    for name, (agent, prompt) in _SCAN_AGENTS.items():
        try:
            results[name] = await run_agent_once(agent, prompt, app_name=name)
        except Exception as exc:
            results[name] = f"Error: {exc}"
    return results


@app.post("/standups/snapshot")
def generate_standup_snapshot() -> dict:
    """Compute today's structured done/doing/blocked/next per engineer and
    cache each to Firestore. The "daily job" -- allowed to hardcode today's
    date since it's Phase 1's only caller; the query functions underneath
    stay parameterized for a future recall/chat endpoint."""
    today = date.today().isoformat()
    snapshots = build_daily_snapshots()
    for engineer, snapshot in snapshots.items():
        write_standup_snapshot(engineer, today, snapshot)
    return {"date": today, "engineers_written": list(snapshots.keys())}


@app.get("/standups/{engineer}")
def standup_history(engineer: str, start: str | None = None, end: str | None = None) -> list[dict]:
    """Browse an engineer's cached standup history. Defaults to the last 7 days."""
    if end is None:
        end = date.today().isoformat()
    if start is None:
        start = (date.today() - timedelta(days=7)).isoformat()
    return get_standup_history(engineer, start, end)
