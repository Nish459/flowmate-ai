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

    def query(self, sql):
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
