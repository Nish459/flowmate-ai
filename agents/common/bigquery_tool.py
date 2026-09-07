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
        sql: A SELECT statement, optionally preceded by a WITH clause of CTEs
            that themselves only SELECT. Only these read-only forms are
            permitted.
        params: Optional query parameters for values that originate from an
            LLM tool call argument -- never interpolate those into `sql`
            directly, bind them here instead.

    Returns:
        A list of rows, each represented as a dict of column name to value.
    """
    normalized = sql.strip().upper()
    if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
        raise ValueError("query_bigquery only permits SELECT (optionally WITH ... SELECT) statements.")
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


# Staleness cutoff anchored to the dataset's own latest changed_date rather
# than CURRENT_TIMESTAMP(). The synthetic dataset's clock is frozen at
# generation time and drifts behind wall-clock; at 6 days of drift, EVERY open
# ticket satisfied "changed_date < now() - 24h", so 'stale' matched all 441
# open tickets and (being first in the CASE below) completely masked the 66
# blocked and 13 unassigned ones. Anchoring keeps "stale" a meaningful subset
# no matter how long since the dataset was regenerated.
def _stale_cutoff_expr() -> str:
    return (
        f"(SELECT TIMESTAMP_SUB(MAX(changed_date), INTERVAL 24 HOUR) "
        f"FROM `{settings.bq_tickets_table_id}`)"
    )


# Flag precedence, defined once so the detail query and the counts query can
# never drift apart. Ordered most-actionable first: a blocked ticket that also
# hasn't moved in 24h is blocked *because* it's blocked, so reporting it as
# merely "stale" buries the useful reason.
def _flag_reason_case() -> str:
    return f"""
           CASE
             WHEN is_blocked THEN 'blocked'
             WHEN assigned_to IS NULL THEN 'missing_assignee'
             WHEN changed_date < {_stale_cutoff_expr()} THEN 'stale'
           END AS flag_reason
"""


def _flagged_where() -> str:
    return f"""
    WHERE state NOT IN ('Resolved', 'Closed')
      AND (
        changed_date < {_stale_cutoff_expr()}
        OR is_blocked
        OR assigned_to IS NULL
      )
"""

# The dataset has ~440 flagged tickets. Listing all of them takes ~97s of
# token-by-token generation and produces output no human reads, so the detail
# query is capped and get_flagged_ticket_counts() reports the full totals
# alongside it -- nothing is hidden, it's just summarized instead of dumped.
FLAGGED_TICKETS_DEFAULT_LIMIT = 25


def _flagged_tickets_sql(limit: int = FLAGGED_TICKETS_DEFAULT_LIMIT) -> str:
    """SQL for Ticket Watcher: the most urgent open tickets that are stale
    (24h+ untouched), blocked, or missing an assignee. Filtering lives in SQL
    rather than the LLM's reasoning -- date arithmetic should be exact, not
    inferred. Capped at `limit`; see FLAGGED_TICKETS_DEFAULT_LIMIT.
    """
    return f"""
    SELECT ticket_id, title, team, state, assigned_to, priority, sprint_id,
           changed_date, is_blocked, blocked_reason,
           {_flag_reason_case().strip()}
    FROM `{settings.bq_tickets_table_id}`
    {_flagged_where().strip()}
    ORDER BY priority ASC, changed_date ASC
    LIMIT {limit}
    """


def _flagged_ticket_counts_sql() -> str:
    """SQL for Ticket Watcher: full totals per flag_reason, so the agent can
    report "showing 25 of 441" rather than implying the capped detail list is
    everything."""
    return f"""
    SELECT flag_reason, COUNT(*) AS ticket_count
    FROM (
      SELECT {_flag_reason_case().strip()}
      FROM `{settings.bq_tickets_table_id}`
      {_flagged_where().strip()}
    )
    GROUP BY flag_reason
    ORDER BY ticket_count DESC
    """


def get_flagged_tickets() -> list[dict]:
    """Return the most urgent open tickets that are stale (24h+ untouched), blocked, or missing an assignee."""
    return query_bigquery(_flagged_tickets_sql())


# For the dashboard's filterable table, not the LLM tool -- a browser can
# filter/sort/paginate client-side, so it gets a much higher cap than the
# 25-row LLM-facing default (see FLAGGED_TICKETS_DEFAULT_LIMIT's docstring for
# why that one stays small).
FLAGGED_TICKETS_TABLE_LIMIT = 500


def get_flagged_tickets_full(limit: int = FLAGGED_TICKETS_TABLE_LIMIT) -> list[dict]:
    """Return flagged tickets for the dashboard table -- same filtering as
    get_flagged_tickets(), much less aggressively capped."""
    return query_bigquery(_flagged_tickets_sql(limit))


def get_flagged_ticket_counts() -> list[dict]:
    """Return the total number of flagged tickets per flag reason (stale / blocked / missing_assignee)."""
    return query_bigquery(_flagged_ticket_counts_sql())


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


ACTIVITY_DEFAULT_PER_ENGINEER_LIMIT = 8


def _developer_activity_sql(days: int = 1, per_engineer_limit: int = ACTIVITY_DEFAULT_PER_ENGINEER_LIMIT) -> str:
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
    generation. (Ticket Watcher's flagged-tickets query had the mirror-image
    version of this bug: "older than 24h" gets *more* true as drift grows, so
    at 6 days of drift it matched every open ticket and masked the blocked and
    unassigned ones behind it. Both are now anchored the same way -- any new
    query comparing a dataset timestamp against "now" should anchor too.)

    `days` is a real parameter (not hardcoded to "today") so a future
    "what did I do last week" recall can call this with days=7 instead of
    needing a separate query function.

    Capped at `per_engineer_limit` tickets *per engineer* via ROW_NUMBER
    (not a plain LIMIT, which would drop whole engineers off the end of the
    list): a standup is a scannable summary, and the uncapped ~200 rows took
    ~18k characters of generation. Partitioning keeps every engineer present
    with their most urgent tickets.
    """
    return f"""
    WITH recent AS (
      SELECT ticket_id, title, work_item_type, state, priority, team, sprint_id,
             assigned_to, changed_date, closed_date, is_blocked, blocked_reason,
             ROW_NUMBER() OVER (
               PARTITION BY assigned_to
               ORDER BY priority ASC, changed_date DESC
             ) AS rn
      FROM `{settings.bq_tickets_table_id}`
      WHERE assigned_to IS NOT NULL
        AND state IN ('Resolved', 'Closed', 'Active', 'In Review', 'Blocked')
        AND changed_date >= (
          SELECT TIMESTAMP_SUB(MAX(changed_date), INTERVAL {days} DAY)
          FROM `{settings.bq_tickets_table_id}`
        )
    )
    SELECT ticket_id, title, work_item_type, state, priority, team, sprint_id,
           assigned_to, changed_date, closed_date, is_blocked, blocked_reason
    FROM recent
    WHERE rn <= {per_engineer_limit}
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


def _open_tickets_at_risk_sql() -> str:
    """SQL for Bottleneck Detector: every open ticket in the *current* sprint,
    with enough context (tags, priority, blocked status, reviewer if any) for
    Gemini to cross-reference against the other three signal tools.

    "Current sprint" = the soonest sprint whose end date is at or after the
    dataset's own MAX(changed_date) (a proxy for "now" -- see
    _developer_activity_sql's docstring for why CURRENT_TIMESTAMP() would
    drift stale here). The generator guarantees the last generated sprint's
    end_date equals generation-time "now", so this reliably resolves to that
    last sprint, matching the demo's "N days before sprint end" framing.

    The LEFT JOIN to pr_reviews means most New/Active tickets simply have a
    NULL reviewer -- that's a real absence of signal, not a bug, and the
    agent's instruction treats it as such.
    """
    return f"""
    WITH anchor AS (
      SELECT MAX(changed_date) AS now_ts FROM `{settings.bq_tickets_table_id}`
    ),
    sprints AS (
      SELECT DISTINCT sprint_id, sprint_end_date FROM `{settings.bq_team_velocity_table_id}`
    ),
    current_sprint AS (
      SELECT s.sprint_id, s.sprint_end_date
      FROM sprints s, anchor a
      WHERE s.sprint_end_date >= a.now_ts
      ORDER BY s.sprint_end_date ASC
      LIMIT 1
    )
    SELECT t.ticket_id, t.title, t.team, t.work_item_type, t.tags, t.priority, t.state,
           t.sprint_id, cs.sprint_end_date,
           TIMESTAMP_DIFF(cs.sprint_end_date, (SELECT now_ts FROM anchor), DAY) AS days_until_sprint_end,
           t.is_blocked, t.blocked_reason, t.comment_count, t.created_date, t.changed_date,
           pr.reviewer, pr.review_status
    FROM `{settings.bq_tickets_table_id}` t
    JOIN current_sprint cs ON t.sprint_id = cs.sprint_id
    LEFT JOIN `{settings.bq_pr_reviews_table_id}` pr ON pr.ticket_id = t.ticket_id
    WHERE t.state NOT IN ('Resolved', 'Closed')
    ORDER BY t.priority ASC
    """


def get_open_tickets_at_risk() -> list[dict]:
    """Return open tickets in the current sprint, with context for cross-referencing risk signals."""
    return query_bigquery(_open_tickets_at_risk_sql())


def _team_type_close_rates_sql() -> str:
    """SQL for Bottleneck Detector: historical (finished-sprint-only)
    close rate and average cycle time per team x work_item_type. "Historical"
    excludes the current (still-open) sprint so a team's in-progress sprint
    doesn't trivially look bad just for having open tickets -- anchored the
    same way as _open_tickets_at_risk_sql.

    Deliberately generic (GROUP BY team, work_item_type over all data) rather
    than hardcoding the DevOps/Bug pattern from patterns.py -- the point is
    for Gemini to discover the outlier itself from an aggregation, the same
    way a human analyst would.
    """
    return f"""
    WITH anchor AS (
      SELECT MAX(changed_date) AS now_ts FROM `{settings.bq_tickets_table_id}`
    ),
    finished_sprints AS (
      SELECT DISTINCT sprint_id FROM `{settings.bq_team_velocity_table_id}`, anchor
      WHERE sprint_end_date < anchor.now_ts
    )
    SELECT t.team, t.work_item_type,
           ROUND(COUNTIF(t.state IN ('Resolved', 'Closed')) / COUNT(*), 3) AS close_rate,
           ROUND(AVG(TIMESTAMP_DIFF(COALESCE(t.closed_date, t.changed_date), t.created_date, HOUR)), 1)
             AS avg_cycle_time_hours,
           COUNT(*) AS ticket_count
    FROM `{settings.bq_tickets_table_id}` t
    WHERE t.sprint_id IN (SELECT sprint_id FROM finished_sprints)
    GROUP BY t.team, t.work_item_type
    HAVING COUNT(*) >= 5
    ORDER BY close_rate ASC
    """


def get_team_type_close_rates() -> list[dict]:
    """Return historical close rate and cycle time per team x work item type, from finished sprints only."""
    return query_bigquery(_team_type_close_rates_sql())


def _reviewer_latency_stats_sql() -> str:
    """SQL for Bottleneck Detector: per-reviewer average review latency and
    changes-requested rate, over completed reviews only. Generic GROUP BY --
    doesn't hardcode which reviewer is slow.
    """
    return f"""
    SELECT reviewer,
           ROUND(AVG(review_latency_hours), 1) AS avg_latency_hours,
           ROUND(COUNTIF(review_status = 'Changes Requested') / COUNT(*), 3) AS changes_requested_rate,
           COUNT(*) AS review_count
    FROM `{settings.bq_pr_reviews_table_id}`
    WHERE review_status != 'Pending'
    GROUP BY reviewer
    HAVING COUNT(*) >= 5
    ORDER BY avg_latency_hours DESC
    """


def get_reviewer_latency_stats() -> list[dict]:
    """Return each reviewer's average review latency and changes-requested rate."""
    return query_bigquery(_reviewer_latency_stats_sql())


def _bug_close_rate_by_sprint_sql() -> str:
    """SQL for Bottleneck Detector: Bug-only close rate per sprint, ordered by
    sprint end date -- lets Gemini see a declining-trend signal directly as a
    time series rather than being told "recent sprints are worse."
    """
    return f"""
    SELECT t.sprint_id, s.sprint_end_date,
           ROUND(COUNTIF(t.state IN ('Resolved', 'Closed')) / COUNT(*), 3) AS bug_close_rate,
           COUNT(*) AS bug_count
    FROM `{settings.bq_tickets_table_id}` t
    JOIN (
      SELECT DISTINCT sprint_id, sprint_end_date FROM `{settings.bq_team_velocity_table_id}`
    ) s ON s.sprint_id = t.sprint_id
    WHERE t.work_item_type = 'Bug'
    GROUP BY t.sprint_id, s.sprint_end_date
    ORDER BY s.sprint_end_date ASC
    """


def get_bug_close_rate_by_sprint() -> list[dict]:
    """Return Bug-ticket close rate per sprint, ordered chronologically."""
    return query_bigquery(_bug_close_rate_by_sprint_sql())


def _all_engineers_sql() -> str:
    """SQL for the dashboard's Standup History engineer dropdown: distinct
    assigned engineers, alphabetical. Deliberately not routed through
    get_developer_activity()/build_daily_snapshots() -- those pull full
    per-engineer ticket detail, which is unrelated work for populating a
    dropdown."""
    return f"""
    SELECT DISTINCT assigned_to AS engineer
    FROM `{settings.bq_tickets_table_id}`
    WHERE assigned_to IS NOT NULL
    ORDER BY engineer
    """


def get_all_engineers() -> list[str]:
    """Return every distinct engineer name that has assigned tickets, alphabetically."""
    return [row["engineer"] for row in query_bigquery(_all_engineers_sql())]


tickets_tool = FunctionTool(get_tickets_snapshot)
pr_reviews_tool = FunctionTool(get_pr_reviews_snapshot)
velocity_tool = FunctionTool(get_team_velocity_snapshot)
flagged_tickets_tool = FunctionTool(get_flagged_tickets)
flagged_ticket_counts_tool = FunctionTool(get_flagged_ticket_counts)
pending_reviews_tool = FunctionTool(get_pending_reviews)
activity_tool = FunctionTool(get_developer_activity)
upcoming_tickets_tool = FunctionTool(get_upcoming_tickets)
at_risk_tickets_tool = FunctionTool(get_open_tickets_at_risk)
team_type_close_rates_tool = FunctionTool(get_team_type_close_rates)
reviewer_latency_tool = FunctionTool(get_reviewer_latency_stats)
bug_close_rate_trend_tool = FunctionTool(get_bug_close_rate_by_sprint)
raw_query_tool = FunctionTool(query_bigquery)
