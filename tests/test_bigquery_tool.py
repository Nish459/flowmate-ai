import pytest

from agents.common import bigquery_tool


def test_query_bigquery_rejects_non_select_statements():
    with pytest.raises(ValueError):
        bigquery_tool.query_bigquery("DELETE FROM tickets WHERE 1=1")


def test_query_bigquery_rejects_non_select_case_insensitively():
    with pytest.raises(ValueError):
        bigquery_tool.query_bigquery("update tickets set state = 'Closed'")


def test_query_bigquery_allows_with_clause_ctes(monkeypatch):
    class _FakeQueryJob:
        def result(self):
            return []

    class _FakeClient:
        def query(self, sql, job_config=None):
            return _FakeQueryJob()

    monkeypatch.setattr(bigquery_tool, "_get_client", lambda: _FakeClient())

    # Should not raise -- a WITH ... SELECT CTE is still read-only.
    bigquery_tool.query_bigquery("WITH x AS (SELECT 1) SELECT * FROM x")


class _FakeRow:
    def __init__(self, data):
        self._data = data

    def items(self):
        return self._data.items()


class _FakeQueryJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows

    def query(self, sql, job_config=None):
        return _FakeQueryJob(self._rows)


def test_query_bigquery_runs_select_and_returns_row_dicts(monkeypatch):
    fake_rows = [_FakeRow({"ticket_id": "TFS-1", "state": "Blocked"})]
    monkeypatch.setattr(bigquery_tool, "_get_client", lambda: _FakeClient(fake_rows))

    result = bigquery_tool.query_bigquery("SELECT * FROM tickets")

    assert result == [{"ticket_id": "TFS-1", "state": "Blocked"}]


def test_snapshot_tools_are_wrapped_as_function_tools():
    from google.adk.tools.function_tool import FunctionTool

    assert isinstance(bigquery_tool.tickets_tool, FunctionTool)
    assert isinstance(bigquery_tool.pr_reviews_tool, FunctionTool)
    assert isinstance(bigquery_tool.velocity_tool, FunctionTool)
    assert isinstance(bigquery_tool.flagged_tickets_tool, FunctionTool)
    assert isinstance(bigquery_tool.flagged_ticket_counts_tool, FunctionTool)
    assert isinstance(bigquery_tool.pending_reviews_tool, FunctionTool)
    assert isinstance(bigquery_tool.activity_tool, FunctionTool)
    assert isinstance(bigquery_tool.upcoming_tickets_tool, FunctionTool)
    assert isinstance(bigquery_tool.at_risk_tickets_tool, FunctionTool)
    assert isinstance(bigquery_tool.team_type_close_rates_tool, FunctionTool)
    assert isinstance(bigquery_tool.reviewer_latency_tool, FunctionTool)
    assert isinstance(bigquery_tool.bug_close_rate_trend_tool, FunctionTool)


def test_flagged_tickets_sql_covers_all_three_flag_conditions():
    sql = bigquery_tool._flagged_tickets_sql()
    assert "INTERVAL 24 HOUR" in sql
    assert "is_blocked" in sql
    assert "assigned_to IS NULL" in sql
    assert "'stale'" in sql
    assert "'blocked'" in sql
    assert "'missing_assignee'" in sql
    # Terminal-state tickets should never be flagged.
    assert "NOT IN ('Resolved', 'Closed')" in sql


def test_flagged_tickets_staleness_is_anchored_to_dataset_not_wallclock():
    """Regression: with CURRENT_TIMESTAMP(), 6 days of dataset clock drift made
    every open ticket 'stale', which (being first in the CASE) masked all the
    blocked and unassigned tickets entirely."""
    sql = bigquery_tool._flagged_tickets_sql()
    assert "CURRENT_TIMESTAMP" not in sql
    assert "MAX(changed_date)" in sql


def test_flagged_tickets_precedence_puts_blocked_before_stale():
    """A blocked ticket that also hasn't moved in 24h should report as blocked --
    the blocker is the actionable reason, 'stale' buries it."""
    case_sql = bigquery_tool._flag_reason_case()
    assert case_sql.index("'blocked'") < case_sql.index("'stale'")
    assert case_sql.index("'missing_assignee'") < case_sql.index("'stale'")


def test_flagged_tickets_sql_is_capped():
    sql = bigquery_tool._flagged_tickets_sql(limit=10)
    assert "LIMIT 10" in sql


def test_flagged_ticket_counts_sql_reports_totals_per_reason():
    sql = bigquery_tool._flagged_ticket_counts_sql()
    assert "COUNT(*)" in sql
    assert "GROUP BY flag_reason" in sql
    # Counts must be uncapped -- they exist to report the true totals behind
    # the capped detail list.
    assert "LIMIT" not in sql.upper()


def test_get_flagged_ticket_counts_runs_the_counts_sql(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["sql"] = sql
        return [{"flag_reason": "blocked", "ticket_count": 66}]

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    result = bigquery_tool.get_flagged_ticket_counts()

    assert result == [{"flag_reason": "blocked", "ticket_count": 66}]
    assert captured["sql"] == bigquery_tool._flagged_ticket_counts_sql()


def test_flagged_tickets_sql_is_select_only():
    sql = bigquery_tool._flagged_tickets_sql()
    assert sql.strip().upper().startswith("SELECT")


def test_get_flagged_tickets_runs_the_flagged_sql(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql):
        captured["sql"] = sql
        return [{"ticket_id": "TFS-1", "flag_reason": "stale"}]

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    result = bigquery_tool.get_flagged_tickets()

    assert result == [{"ticket_id": "TFS-1", "flag_reason": "stale"}]
    assert captured["sql"] == bigquery_tool._flagged_tickets_sql()


def test_get_flagged_tickets_full_uses_the_higher_table_limit(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    bigquery_tool.get_flagged_tickets_full()

    assert captured["sql"] == bigquery_tool._flagged_tickets_sql(bigquery_tool.FLAGGED_TICKETS_TABLE_LIMIT)
    assert f"LIMIT {bigquery_tool.FLAGGED_TICKETS_TABLE_LIMIT}" in captured["sql"]
    assert bigquery_tool.FLAGGED_TICKETS_TABLE_LIMIT > bigquery_tool.FLAGGED_TICKETS_DEFAULT_LIMIT


def test_query_bigquery_passes_params_to_job_config(monkeypatch):
    captured = {}

    class _FakeQueryJob:
        def result(self):
            return []

    class _FakeClient:
        def query(self, sql, job_config=None):
            captured["job_config"] = job_config
            return _FakeQueryJob()

    monkeypatch.setattr(bigquery_tool, "_get_client", lambda: _FakeClient())

    param = bigquery_tool.bigquery.ScalarQueryParameter("engineer", "STRING", "Jane Doe")
    bigquery_tool.query_bigquery("SELECT 1", params=[param])

    assert captured["job_config"].query_parameters == [param]


def test_pending_reviews_sql_is_select_only_and_joins_team_velocity():
    sql = bigquery_tool._pending_reviews_sql()
    assert sql.strip().upper().startswith("SELECT")
    assert "review_status = 'Pending'" in sql
    assert "JOIN" in sql
    assert "sprint_end_date" in sql
    assert "hours_waiting" in sql


def test_get_pending_reviews_runs_the_pending_reviews_sql(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["sql"] = sql
        return [{"pr_id": "PR-1", "hours_waiting": 48}]

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    result = bigquery_tool.get_pending_reviews()

    assert result == [{"pr_id": "PR-1", "hours_waiting": 48}]
    assert captured["sql"] == bigquery_tool._pending_reviews_sql()


def test_developer_activity_sql_covers_done_doing_blocked():
    sql, params = bigquery_tool._developer_activity_sql(days=7)
    assert sql.strip().upper().startswith("WITH")
    assert "INTERVAL 7 DAY" in sql
    assert "'Resolved', 'Closed'" in sql
    assert "'Active', 'In Review', 'Blocked'" in sql
    assert params == []


def test_developer_activity_sql_caps_per_engineer_not_globally():
    """A plain LIMIT would drop whole engineers off the end; the cap must be
    partitioned so every engineer keeps their most urgent tickets."""
    sql, _ = bigquery_tool._developer_activity_sql(per_engineer_limit=3)
    assert "PARTITION BY assigned_to" in sql
    assert "rn <= 3" in sql
    assert "LIMIT 3" not in sql


def test_developer_activity_sql_with_engineer_binds_a_parameter():
    sql, params = bigquery_tool._developer_activity_sql(engineer="Angie Henderson")
    assert "assigned_to = @engineer" in sql
    assert len(params) == 1
    assert params[0].name == "engineer"
    assert params[0].value == "Angie Henderson"


def test_get_developer_activity_defaults_to_one_day(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    bigquery_tool.get_developer_activity()

    expected_sql, expected_params = bigquery_tool._developer_activity_sql(days=1)
    assert captured["sql"] == expected_sql
    assert captured["params"] == expected_params


def test_get_developer_activity_with_engineer_passes_the_bound_parameter(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["params"] = params
        return []

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    bigquery_tool.get_developer_activity(engineer="Angie Henderson")

    assert captured["params"][0].value == "Angie Henderson"


def test_upcoming_tickets_sql_without_engineer_has_no_params():
    sql, params = bigquery_tool._upcoming_tickets_sql()
    assert sql.strip().upper().startswith("SELECT")
    assert "state = 'New'" in sql
    assert params == []


def test_upcoming_tickets_sql_with_engineer_binds_a_query_parameter():
    sql, params = bigquery_tool._upcoming_tickets_sql("Jane Doe")
    assert "@engineer" in sql
    assert "Jane Doe" not in sql  # value must be bound, never interpolated
    assert len(params) == 1
    assert params[0].name == "engineer"
    assert params[0].value == "Jane Doe"


def test_get_upcoming_tickets_runs_with_bound_params(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return [{"ticket_id": "TFS-2"}]

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    result = bigquery_tool.get_upcoming_tickets("Jane Doe")

    expected_sql, expected_params = bigquery_tool._upcoming_tickets_sql("Jane Doe")
    assert result == [{"ticket_id": "TFS-2"}]
    assert captured["sql"] == expected_sql
    assert captured["params"] == expected_params


def test_open_tickets_at_risk_sql_anchors_to_dataset_max_changed_date():
    sql = bigquery_tool._open_tickets_at_risk_sql()
    assert sql.strip().upper().startswith("WITH")
    assert "MAX(changed_date)" in sql
    assert "CURRENT_TIMESTAMP" not in sql
    assert "LEFT JOIN" in sql
    assert "days_until_sprint_end" in sql
    assert "NOT IN ('Resolved', 'Closed')" in sql


def test_get_open_tickets_at_risk_runs_the_at_risk_sql(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["sql"] = sql
        return [{"ticket_id": "TFS-1", "days_until_sprint_end": 5}]

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    result = bigquery_tool.get_open_tickets_at_risk()

    assert result == [{"ticket_id": "TFS-1", "days_until_sprint_end": 5}]
    assert captured["sql"] == bigquery_tool._open_tickets_at_risk_sql()


def test_team_type_close_rates_sql_excludes_current_sprint_and_filters_small_groups():
    sql = bigquery_tool._team_type_close_rates_sql()
    assert "sprint_end_date < anchor.now_ts" in sql
    assert "GROUP BY t.team, t.work_item_type" in sql
    assert "HAVING COUNT(*) >= 5" in sql
    assert "CURRENT_TIMESTAMP" not in sql


def test_get_team_type_close_rates_runs_the_close_rates_sql(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["sql"] = sql
        return [{"team": "DevOps", "work_item_type": "Bug", "close_rate": 0.3}]

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    result = bigquery_tool.get_team_type_close_rates()

    assert result == [{"team": "DevOps", "work_item_type": "Bug", "close_rate": 0.3}]
    assert captured["sql"] == bigquery_tool._team_type_close_rates_sql()


def test_reviewer_latency_stats_sql_excludes_pending_and_filters_small_groups():
    sql = bigquery_tool._reviewer_latency_stats_sql()
    assert "review_status != 'Pending'" in sql
    assert "GROUP BY reviewer" in sql
    assert "HAVING COUNT(*) >= 5" in sql


def test_get_reviewer_latency_stats_runs_the_latency_sql(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["sql"] = sql
        return [{"reviewer": "Angie Henderson", "avg_latency_hours": 81.6}]

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    result = bigquery_tool.get_reviewer_latency_stats()

    assert result == [{"reviewer": "Angie Henderson", "avg_latency_hours": 81.6}]
    assert captured["sql"] == bigquery_tool._reviewer_latency_stats_sql()


def test_bug_close_rate_by_sprint_sql_filters_to_bugs_and_orders_chronologically():
    sql = bigquery_tool._bug_close_rate_by_sprint_sql()
    assert "work_item_type = 'Bug'" in sql
    assert "GROUP BY t.sprint_id, s.sprint_end_date" in sql
    assert "ORDER BY s.sprint_end_date ASC" in sql


def test_get_bug_close_rate_by_sprint_runs_the_trend_sql(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["sql"] = sql
        return [{"sprint_id": "SPR-2026-07", "bug_close_rate": 0.38}]

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    result = bigquery_tool.get_bug_close_rate_by_sprint()

    assert result == [{"sprint_id": "SPR-2026-07", "bug_close_rate": 0.38}]
    assert captured["sql"] == bigquery_tool._bug_close_rate_by_sprint_sql()


def test_all_engineers_sql_excludes_unassigned_and_orders_alphabetically():
    sql = bigquery_tool._all_engineers_sql()
    assert "assigned_to IS NOT NULL" in sql
    assert "ORDER BY engineer" in sql


def test_get_all_engineers_returns_flat_sorted_list(monkeypatch):
    def fake_query_bigquery(sql, params=None):
        return [{"engineer": "Abigail Shaffer"}, {"engineer": "Angie Henderson"}]

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    result = bigquery_tool.get_all_engineers()

    assert result == ["Abigail Shaffer", "Angie Henderson"]
