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


def query_bigquery(sql: str, params: list[bigquery.ScalarQueryParameter] | None = None) -> list[dict]:
    """Run a read-only SQL query against the FlowMate BigQuery dataset and
    return the results as a list of row dicts.

    Args:
        sql: A SELECT statement. Only SELECT statements are permitted.
        params: Optional query parameters for values that originate from an
            LLM tool call argument -- never interpolate those into `sql`
            directly, bind them here instead.

    Returns:
        A list of rows, each represented as a dict of column name to value.
    """
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("query_bigquery only permits SELECT statements.")
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    rows = _get_client().query(sql, job_config=job_config).result()
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


def _pending_reviews_sql(hours_threshold: int = 24) -> str:
    """SQL for Review Nudger: PRs still awaiting review past `hours_threshold`,
    joined to team_velocity for the sprint end date -- so a nudge can reference
    the real deadline instead of a generic ping.
    """
    return f"""
    SELECT pr.pr_id, pr.ticket_id, pr.author, pr.reviewer, pr.team, pr.sprint_id,
           pr.review_requested_date,
           TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), pr.review_requested_date, HOUR) AS hours_waiting,
           tv.sprint_end_date
    FROM `{settings.bq_pr_reviews_table_id}` pr
    JOIN `{settings.bq_team_velocity_table_id}` tv
      ON pr.team = tv.team AND pr.sprint_id = tv.sprint_id
    WHERE pr.review_status = 'Pending'
      AND pr.review_requested_date < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours_threshold} HOUR)
    ORDER BY hours_waiting DESC
    """


def get_pending_reviews() -> list[dict]:
    """Return PRs awaiting review past the threshold, with sprint end date for context."""
    return query_bigquery(_pending_reviews_sql())


def _developer_activity_sql(days: int = 1) -> str:
    """SQL for Standup Writer: per-engineer tickets touched in the last `days`
    that are either closed/resolved (done), active or in review (doing), or
    blocked (blocked). Requiring recent `changed_date` for all three keeps
    "doing" to work actually touched lately rather than the whole backlog of
    long-untouched Active tickets -- that staleness signal belongs to Ticket
    Watcher, not a daily standup. Covers all assigned engineers at once so one
    call can drive the whole team's standup.

    The "days ago" window is anchored to the dataset's own latest
    changed_date, not CURRENT_TIMESTAMP() -- the synthetic dataset's clock is
    frozen at generation time and drifts further behind real wall-clock time
    with every day it isn't regenerated, so anchoring to wall-clock time would
    make "recent activity" silently return nothing a day or two after
    generation. (Ticket Watcher's staleness check doesn't have this problem --
    "older than 24h" only gets *more* true as time passes, never less.)

    `days` is a real parameter (not hardcoded to "today") so a future
    "what did I do last week" recall can call this with days=7 instead of
    needing a separate query function.
    """
    return f"""
    SELECT ticket_id, title, work_item_type, state, priority, team, sprint_id,
           assigned_to, changed_date, closed_date, is_blocked, blocked_reason
    FROM `{settings.bq_tickets_table_id}`
    WHERE assigned_to IS NOT NULL
      AND state IN ('Resolved', 'Closed', 'Active', 'In Review', 'Blocked')
      AND changed_date >= (
        SELECT TIMESTAMP_SUB(MAX(changed_date), INTERVAL {days} DAY)
        FROM `{settings.bq_tickets_table_id}`
      )
    ORDER BY assigned_to, priority ASC
    """


def get_developer_activity(days: int = 1) -> list[dict]:
    """Return each assigned engineer's recently closed, active/in-review, and blocked tickets."""
    return query_bigquery(_developer_activity_sql(days))


def _upcoming_tickets_sql(engineer: str | None = None) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    """SQL for Standup Writer's "next" section: New-state tickets ordered by
    priority. `engineer` is LLM-suppliable, so it's always bound as a query
    parameter -- never interpolated into the SQL string.
    """
    base = f"""
    SELECT ticket_id, title, work_item_type, priority, team, sprint_id, assigned_to, created_date
    FROM `{settings.bq_tickets_table_id}`
    WHERE assigned_to IS NOT NULL AND state = 'New'
    """
    if engineer:
        sql = base + " AND assigned_to = @engineer ORDER BY priority ASC, created_date ASC"
        return sql, [bigquery.ScalarQueryParameter("engineer", "STRING", engineer)]
    sql = base + " ORDER BY assigned_to, priority ASC, created_date ASC"
    return sql, []


def get_upcoming_tickets(engineer: str | None = None) -> list[dict]:
    """Return New-state tickets ordered by priority -- for all engineers, or
    just one if `engineer` is given."""
    sql, params = _upcoming_tickets_sql(engineer)
    return query_bigquery(sql, params=params)


tickets_tool = FunctionTool(get_tickets_snapshot)
pr_reviews_tool = FunctionTool(get_pr_reviews_snapshot)
velocity_tool = FunctionTool(get_team_velocity_snapshot)
flagged_tickets_tool = FunctionTool(get_flagged_tickets)
pending_reviews_tool = FunctionTool(get_pending_reviews)
activity_tool = FunctionTool(get_developer_activity)
upcoming_tickets_tool = FunctionTool(get_upcoming_tickets)
raw_query_tool = FunctionTool(query_bigquery)
