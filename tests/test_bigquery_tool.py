import pytest

from agents.common import bigquery_tool


def test_query_bigquery_rejects_non_select_statements():
    with pytest.raises(ValueError):
        bigquery_tool.query_bigquery("DELETE FROM tickets WHERE 1=1")


def test_query_bigquery_rejects_non_select_case_insensitively():
    with pytest.raises(ValueError):
        bigquery_tool.query_bigquery("update tickets set state = 'Closed'")


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
    assert isinstance(bigquery_tool.pending_reviews_tool, FunctionTool)
    assert isinstance(bigquery_tool.activity_tool, FunctionTool)
    assert isinstance(bigquery_tool.upcoming_tickets_tool, FunctionTool)


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
    sql = bigquery_tool._developer_activity_sql(days=7)
    assert sql.strip().upper().startswith("SELECT")
    assert "INTERVAL 7 DAY" in sql
    assert "'Resolved', 'Closed'" in sql
    assert "'Active', 'In Review', 'Blocked'" in sql


def test_get_developer_activity_defaults_to_one_day(monkeypatch):
    captured = {}

    def fake_query_bigquery(sql, params=None):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(bigquery_tool, "query_bigquery", fake_query_bigquery)

    bigquery_tool.get_developer_activity()

    assert captured["sql"] == bigquery_tool._developer_activity_sql(days=1)


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
