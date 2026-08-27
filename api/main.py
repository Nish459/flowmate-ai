"""FlowMate FastAPI backend -- the HTTP boundary between the (future) React
frontend and FlowMate's agents/Firestore/BigQuery. Depends on agents/ and
config/ only, never the reverse (see CLAUDE.md's module-boundary rule).
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.bottleneck_detector.agent import root_agent as bottleneck_detector  # noqa: E402
from agents.common.agent_runner import run_agent_once  # noqa: E402
from agents.common.firestore_client import (  # noqa: E402
    get_latest_scan,
    get_standup_history,
    write_scan_snapshot,
    write_standup_snapshot,
)
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


def _merge_scan_results(new_results: dict, previous: dict | None, generated_at: str) -> dict:
    """Build the cache document, preserving the last *successful* output for any
    agent that failed this run.

    A full sequential scan takes ~6.5 min and can partly fail on the free tier's
    quota. Without this merge, one quota-failed refresh would overwrite good
    cached output with error strings -- i.e. break the demo precisely when the
    API is being flaky. Per-agent `generated_at` records how stale each panel is.
    """
    previous_agents = (previous or {}).get("agents", {})
    agents = {}
    for name, result in new_results.items():
        if result["ok"]:
            agents[name] = {**result, "generated_at": generated_at}
            continue
        prior = previous_agents.get(name)
        if prior and prior.get("ok"):
            agents[name] = prior
        else:
            agents[name] = {**result, "generated_at": generated_at}
    return {"generated_at": generated_at, "agents": agents}


@app.post("/scan")
async def scan() -> dict:
    """Run all 4 agents sequentially, cache the result to Firestore, and return it.

    This is the *refresh* path and is slow by nature (~6.5 min measured: each
    agent turn needs multiple Gemini round trips). The dashboard should read
    `GET /scan/latest` instead so it renders instantly; run this in the
    background or ahead of a demo.

    Sequential, not concurrent: the Gemini Developer API key this project
    uses sits on the free tier (5 req/min, 20 req/day for gemini-3.6-flash),
    and running 4 agents at once blows past that immediately in practice.
    run_agent_once already retries transient errors (429/503) with backoff; the
    per-agent try/except here isolates a failure that survives those retries to
    just that one panel instead of 500ing the whole response.
    """
    new_results = {}
    for name, (agent, prompt) in _SCAN_AGENTS.items():
        try:
            new_results[name] = {"text": await run_agent_once(agent, prompt, app_name=name), "ok": True}
        except Exception as exc:
            new_results[name] = {"text": f"Error: {exc}", "ok": False}

    generated_at = datetime.now(timezone.utc).isoformat()
    snapshot = _merge_scan_results(new_results, get_latest_scan(), generated_at)
    write_scan_snapshot(snapshot)
    return snapshot


@app.get("/scan/latest")
def latest_scan() -> dict:
    """Return the cached scan output -- what the dashboard loads. Instant, no
    Gemini calls, so demo rendering never waits on a live multi-minute scan."""
    cached = get_latest_scan()
    if cached is None:
        raise HTTPException(status_code=404, detail="No cached scan yet -- POST /scan first.")
    return cached


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
