"""Shared, read-only BigQuery access for all four FlowMate agents.

Exposes a generic query tool plus three narrow snapshot tools (one per
synthetic table). Real per-agent filtering/aggregation logic is deferred to
each agent's own milestone -- today's job is proving the tool plumbing runs
end-to-end against real BigQuery data.
"""

from __future__ import annotations

import sys
from pathlib import Path

from google.adk.tools.function_tool import FunctionTool
from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import settings  # noqa: E402

_client: bigquery.Client | None = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=settings.gcp_project_id)
    return _client


def query_bigquery(sql: str) -> list[dict]:
    """Run a read-only SQL query against the FlowMate BigQuery dataset and
    return the results as a list of row dicts.

    Args:
        sql: A SELECT statement. Only SELECT statements are permitted.

    Returns:
        A list of rows, each represented as a dict of column name to value.
    """
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("query_bigquery only permits SELECT statements.")
    rows = _get_client().query(sql).result()
    return [dict(row.items()) for row in rows]


def get_tickets_snapshot() -> list[dict]:
    """Return a sample of the most recently changed tickets."""
    return query_bigquery(
        f"SELECT * FROM `{settings.bq_tickets_table_id}` ORDER BY changed_date DESC LIMIT 50"
    )


def get_pr_reviews_snapshot() -> list[dict]:
    """Return a sample of the most recently created PR reviews."""
    return query_bigquery(
        f"SELECT * FROM `{settings.bq_pr_reviews_table_id}` ORDER BY created_date DESC LIMIT 50"
    )


def get_team_velocity_snapshot() -> list[dict]:
    """Return team velocity rows for the most recent sprints."""
    return query_bigquery(
        f"SELECT * FROM `{settings.bq_team_velocity_table_id}` ORDER BY sprint_start_date DESC LIMIT 50"
    )


def _flagged_tickets_sql() -> str:
    """SQL for Ticket Watcher: open tickets that are stale (24h+ untouched),
    blocked, or missing an assignee. Filtering lives in SQL rather than the
    LLM's reasoning -- date arithmetic should be exact, not inferred.
    """
    return f"""
    SELECT ticket_id, title, team, state, assigned_to, priority, sprint_id,
           changed_date, is_blocked, blocked_reason,
           CASE
             WHEN state NOT IN ('Resolved', 'Closed')
                  AND changed_date < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
               THEN 'stale'
             WHEN is_blocked THEN 'blocked'
             WHEN assigned_to IS NULL AND state NOT IN ('Resolved', 'Closed')
               THEN 'missing_assignee'
           END AS flag_reason
    FROM `{settings.bq_tickets_table_id}`
    WHERE state NOT IN ('Resolved', 'Closed')
      AND (
        changed_date < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        OR is_blocked
        OR assigned_to IS NULL
      )
    ORDER BY priority ASC, changed_date ASC
    """


def get_flagged_tickets() -> list[dict]:
    """Return open tickets that are stale (24h+ untouched), blocked, or missing an assignee."""
    return query_bigquery(_flagged_tickets_sql())


tickets_tool = FunctionTool(get_tickets_snapshot)
pr_reviews_tool = FunctionTool(get_pr_reviews_snapshot)
velocity_tool = FunctionTool(get_team_velocity_snapshot)
flagged_tickets_tool = FunctionTool(get_flagged_tickets)
raw_query_tool = FunctionTool(query_bigquery)
