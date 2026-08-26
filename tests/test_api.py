from datetime import date, timedelta

from fastapi.testclient import TestClient

from api import main as api_main

client = TestClient(api_main.app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_scan_returns_all_four_agent_responses(monkeypatch):
    async def fake_run_agent_once(agent, prompt, app_name):
        return f"response for {app_name}"

    monkeypatch.setattr(api_main, "run_agent_once", fake_run_agent_once)

    resp = client.post("/scan")

    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"ticket_watcher", "bottleneck_detector", "review_nudger", "standup_writer"}
    assert data["ticket_watcher"] == "response for ticket_watcher"


def test_scan_isolates_a_failing_agent_from_the_others(monkeypatch):
    async def flaky_run_agent_once(agent, prompt, app_name):
        if app_name == "review_nudger":
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return f"response for {app_name}"

    monkeypatch.setattr(api_main, "run_agent_once", flaky_run_agent_once)

    resp = client.post("/scan")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_watcher"] == "response for ticket_watcher"
    assert "429 RESOURCE_EXHAUSTED" in data["review_nudger"]


def test_generate_standup_snapshot_writes_each_engineer(monkeypatch):
    written = {}

    def fake_build_daily_snapshots():
        return {"Jane": {"done": []}, "John": {"done": []}}

    def fake_write(engineer, snapshot_date, snapshot):
        written[engineer] = (snapshot_date, snapshot)

    monkeypatch.setattr(api_main, "build_daily_snapshots", fake_build_daily_snapshots)
    monkeypatch.setattr(api_main, "write_standup_snapshot", fake_write)

    resp = client.post("/standups/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    assert set(data["engineers_written"]) == {"Jane", "John"}
    assert data["date"] == date.today().isoformat()
    assert set(written.keys()) == {"Jane", "John"}


def test_standup_history_defaults_to_last_seven_days(monkeypatch):
    captured = {}

    def fake_get_history(engineer, start, end):
        captured["args"] = (engineer, start, end)
        return [{"date": start}]

    monkeypatch.setattr(api_main, "get_standup_history", fake_get_history)

    resp = client.get("/standups/Jane")

    assert resp.status_code == 200
    engineer, start, end = captured["args"]
    assert engineer == "Jane"
    assert end == date.today().isoformat()
    assert start == (date.today() - timedelta(days=7)).isoformat()


def test_standup_history_respects_explicit_range(monkeypatch):
    captured = {}

    def fake_get_history(engineer, start, end):
        captured["args"] = (engineer, start, end)
        return []

    monkeypatch.setattr(api_main, "get_standup_history", fake_get_history)

    resp = client.get("/standups/Jane?start=2026-08-01&end=2026-08-05")

    assert resp.status_code == 200
    assert captured["args"] == ("Jane", "2026-08-01", "2026-08-05")
