from agents.standup_writer import snapshot


def test_bucket_snapshots_groups_by_state_into_done_doing_blocked():
    activity_rows = [
        {"ticket_id": "TFS-1", "title": "Fix bug", "state": "Closed", "assigned_to": "Jane",
         "is_blocked": False, "blocked_reason": None},
        {"ticket_id": "TFS-2", "title": "Add feature", "state": "Active", "assigned_to": "Jane",
         "is_blocked": False, "blocked_reason": None},
        {"ticket_id": "TFS-3", "title": "Waiting review", "state": "In Review", "assigned_to": "Jane",
         "is_blocked": False, "blocked_reason": None},
        {"ticket_id": "TFS-4", "title": "Stuck", "state": "Blocked", "assigned_to": "Jane",
         "is_blocked": True, "blocked_reason": "Waiting on external API vendor"},
    ]

    result = snapshot._bucket_snapshots(activity_rows, [])

    jane = result["Jane"]
    assert [t["ticket_id"] for t in jane["done"]] == ["TFS-1"]
    assert [t["ticket_id"] for t in jane["doing"]] == ["TFS-2", "TFS-3"]
    assert [t["ticket_id"] for t in jane["blocked"]] == ["TFS-4"]
    assert jane["blocked"][0]["blocked_reason"] == "Waiting on external API vendor"
    assert jane["next"] == []


def test_bucket_snapshots_is_blocked_flag_wins_over_state():
    # A ticket that's Active but flagged is_blocked should land in blocked, not doing.
    activity_rows = [
        {"ticket_id": "TFS-5", "title": "Flagged active", "state": "Active", "assigned_to": "Jane",
         "is_blocked": True, "blocked_reason": "Blocked by unresolved dependency ticket"},
    ]

    result = snapshot._bucket_snapshots(activity_rows, [])

    assert [t["ticket_id"] for t in result["Jane"]["blocked"]] == ["TFS-5"]
    assert result["Jane"]["doing"] == []


def test_bucket_snapshots_fills_next_from_upcoming_rows():
    upcoming_rows = [
        {"ticket_id": "TFS-6", "title": "Not started", "priority": 2, "assigned_to": "Jane"},
        {"ticket_id": "TFS-7", "title": "Also not started", "priority": 1, "assigned_to": "John"},
    ]

    result = snapshot._bucket_snapshots([], upcoming_rows)

    assert [t["ticket_id"] for t in result["Jane"]["next"]] == ["TFS-6"]
    assert [t["ticket_id"] for t in result["John"]["next"]] == ["TFS-7"]


def test_bucket_snapshots_skips_rows_with_no_assignee():
    activity_rows = [
        {"ticket_id": "TFS-8", "title": "Unassigned", "state": "Active", "assigned_to": None,
         "is_blocked": False, "blocked_reason": None},
    ]

    result = snapshot._bucket_snapshots(activity_rows, [])

    assert result == {}


def test_build_daily_snapshots_calls_activity_and_upcoming_tools(monkeypatch):
    captured = {}

    def fake_activity(days):
        captured["days"] = days
        return [{"ticket_id": "TFS-1", "title": "Fix bug", "state": "Closed", "assigned_to": "Jane",
                  "is_blocked": False, "blocked_reason": None}]

    def fake_upcoming():
        return [{"ticket_id": "TFS-9", "title": "Later", "priority": 3, "assigned_to": "Jane"}]

    monkeypatch.setattr(snapshot, "get_developer_activity", fake_activity)
    monkeypatch.setattr(snapshot, "get_upcoming_tickets", fake_upcoming)

    result = snapshot.build_daily_snapshots(days=7)

    assert captured["days"] == 7
    assert [t["ticket_id"] for t in result["Jane"]["done"]] == ["TFS-1"]
    assert [t["ticket_id"] for t in result["Jane"]["next"]] == ["TFS-9"]
