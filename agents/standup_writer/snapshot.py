"""Deterministic daily standup snapshot builder for the Firestore history
cache -- separate from the interactive `standup_writer` LLM agent
(agents/standup_writer/agent.py), which produces prose for on-demand use.

Bucketing a ticket into done/doing/blocked/next is a pure function of its
`state` field -- already exact, already returned by the existing BigQuery
tools -- so it belongs in code rather than being asked of an LLM, the same
principle already applied to Ticket Watcher's date arithmetic living in SQL.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agents.common.bigquery_tool import get_developer_activity, get_upcoming_tickets  # noqa: E402

_DONE_STATES = {"Resolved", "Closed"}
_DOING_STATES = {"Active", "In Review"}


def _bucket_snapshots(activity_rows: list[dict], upcoming_rows: list[dict]) -> dict[str, dict]:
    """Group activity/upcoming ticket rows by assigned_to into per-engineer
    {done, doing, blocked, next} lists."""
    snapshots: dict[str, dict] = {}

    def bucket(engineer: str) -> dict:
        return snapshots.setdefault(engineer, {"done": [], "doing": [], "blocked": [], "next": []})

    for row in activity_rows:
        engineer = row["assigned_to"]
        if not engineer:
            continue
        entry = {"ticket_id": row["ticket_id"], "title": row["title"], "state": row["state"]}
        if row["is_blocked"] or row["state"] == "Blocked":
            entry["blocked_reason"] = row["blocked_reason"]
            bucket(engineer)["blocked"].append(entry)
        elif row["state"] in _DONE_STATES:
            bucket(engineer)["done"].append(entry)
        elif row["state"] in _DOING_STATES:
            bucket(engineer)["doing"].append(entry)

    for row in upcoming_rows:
        engineer = row["assigned_to"]
        if not engineer:
            continue
        bucket(engineer)["next"].append(
            {"ticket_id": row["ticket_id"], "title": row["title"], "priority": row["priority"]}
        )

    return snapshots


def build_daily_snapshots(days: int = 1) -> dict[str, dict]:
    """Return {engineer: {done, doing, blocked, next}} for every engineer
    with relevant activity or upcoming work, computed live from BigQuery."""
    activity_rows = get_developer_activity(days=days)
    upcoming_rows = get_upcoming_tickets()
    return _bucket_snapshots(activity_rows, upcoming_rows)
