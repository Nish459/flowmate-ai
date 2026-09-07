from datetime import date, timedelta

from fastapi.testclient import TestClient

from api import main as api_main

client = TestClient(api_main.app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def _stub_scan_cache(monkeypatch, previous=None):
    """Stub the Firestore read/write around /scan and capture what got cached."""
    captured = {}
    monkeypatch.setattr(api_main, "get_latest_scan", lambda: previous)
    monkeypatch.setattr(api_main, "write_scan_snapshot", lambda snap: captured.update(snap))
    return captured


def _fake_findings_json(app_name):
    return f'{{"findings": [], "source": "{app_name}"}}'


def test_scan_returns_all_four_agent_responses(monkeypatch):
    async def fake_run_agent_once(agent, prompt, app_name):
        return _fake_findings_json(app_name)

    monkeypatch.setattr(api_main, "run_agent_once", fake_run_agent_once)
    _stub_scan_cache(monkeypatch)

    resp = client.post("/scan")

    assert resp.status_code == 200
    agents = resp.json()["agents"]
    assert set(agents.keys()) == {"ticket_watcher", "bottleneck_detector", "review_nudger", "standup_writer"}
    assert agents["ticket_watcher"]["text"] == _fake_findings_json("ticket_watcher")
    assert agents["ticket_watcher"]["ok"] is True


def test_scan_isolates_a_failing_agent_from_the_others(monkeypatch):
    async def flaky_run_agent_once(agent, prompt, app_name):
        if app_name == "review_nudger":
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return _fake_findings_json(app_name)

    monkeypatch.setattr(api_main, "run_agent_once", flaky_run_agent_once)
    _stub_scan_cache(monkeypatch)

    resp = client.post("/scan")

    assert resp.status_code == 200
    agents = resp.json()["agents"]
    assert agents["ticket_watcher"]["text"] == _fake_findings_json("ticket_watcher")
    assert agents["review_nudger"]["ok"] is False
    assert "429 RESOURCE_EXHAUSTED" in agents["review_nudger"]["text"]


def test_scan_treats_invalid_json_as_a_failure(monkeypatch):
    async def fake_run_agent_once(agent, prompt, app_name):
        if app_name == "standup_writer":
            return "not valid json"
        return _fake_findings_json(app_name)

    monkeypatch.setattr(api_main, "run_agent_once", fake_run_agent_once)
    _stub_scan_cache(monkeypatch)

    resp = client.post("/scan")

    assert resp.status_code == 200
    agents = resp.json()["agents"]
    assert agents["standup_writer"]["ok"] is False
    assert agents["ticket_watcher"]["ok"] is True


def test_scan_accepts_valid_standup_writer_json(monkeypatch):
    async def fake_run_agent_once(agent, prompt, app_name):
        if app_name == "standup_writer":
            return '{"findings": []}'
        return _fake_findings_json(app_name)

    monkeypatch.setattr(api_main, "run_agent_once", fake_run_agent_once)
    _stub_scan_cache(monkeypatch)

    resp = client.post("/scan")

    assert resp.status_code == 200
    agents = resp.json()["agents"]
    assert agents["standup_writer"]["ok"] is True
    assert agents["standup_writer"]["text"] == '{"findings": []}'


def test_scan_caches_its_result(monkeypatch):
    async def fake_run_agent_once(agent, prompt, app_name):
        return _fake_findings_json(app_name)

    monkeypatch.setattr(api_main, "run_agent_once", fake_run_agent_once)
    captured = _stub_scan_cache(monkeypatch)

    client.post("/scan")

    assert set(captured["agents"].keys()) == set(api_main._SCAN_AGENTS.keys())
    assert captured["generated_at"]


def test_merge_scan_results_keeps_last_good_output_for_a_failed_agent():
    previous = {
        "generated_at": "2026-08-26T10:00:00+00:00",
        "agents": {
            "ticket_watcher": {"text": "good old output", "ok": True, "generated_at": "2026-08-26T10:00:00+00:00"},
        },
    }
    new_results = {"ticket_watcher": {"text": "Error: 429", "ok": False}}

    merged = api_main._merge_scan_results(new_results, previous, "2026-08-27T10:00:00+00:00")

    # A quota-failed refresh must not clobber a good cached panel.
    assert merged["agents"]["ticket_watcher"]["text"] == "good old output"
    assert merged["agents"]["ticket_watcher"]["generated_at"] == "2026-08-26T10:00:00+00:00"
    assert merged["generated_at"] == "2026-08-27T10:00:00+00:00"


def test_merge_scan_results_prefers_fresh_success_over_cached():
    previous = {
        "agents": {"ticket_watcher": {"text": "stale", "ok": True, "generated_at": "2026-08-26T10:00:00+00:00"}}
    }
    new_results = {"ticket_watcher": {"text": "fresh", "ok": True}}

    merged = api_main._merge_scan_results(new_results, previous, "2026-08-27T10:00:00+00:00")

    assert merged["agents"]["ticket_watcher"]["text"] == "fresh"
    assert merged["agents"]["ticket_watcher"]["generated_at"] == "2026-08-27T10:00:00+00:00"


def test_merge_scan_results_surfaces_error_when_no_prior_success():
    new_results = {"ticket_watcher": {"text": "Error: 429", "ok": False}}

    merged = api_main._merge_scan_results(new_results, None, "2026-08-27T10:00:00+00:00")

    assert merged["agents"]["ticket_watcher"]["ok"] is False
    assert "Error: 429" in merged["agents"]["ticket_watcher"]["text"]


def test_latest_scan_returns_cached_output(monkeypatch):
    cached = {"generated_at": "2026-08-27T10:00:00+00:00", "agents": {"ticket_watcher": {"text": "x", "ok": True}}}
    monkeypatch.setattr(api_main, "get_latest_scan", lambda: cached)

    resp = client.get("/scan/latest")

    assert resp.status_code == 200
    assert resp.json() == cached


def test_latest_scan_404s_when_nothing_cached(monkeypatch):
    monkeypatch.setattr(api_main, "get_latest_scan", lambda: None)

    resp = client.get("/scan/latest")

    assert resp.status_code == 404


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


def test_engineers_returns_the_bigquery_tool_result(monkeypatch):
    monkeypatch.setattr(api_main, "get_all_engineers", lambda: ["Abigail Shaffer", "Angie Henderson"])

    resp = client.get("/engineers")

    assert resp.status_code == 200
    assert resp.json() == ["Abigail Shaffer", "Angie Henderson"]


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


def test_panels_returns_structured_data_from_all_four_sources(monkeypatch):
    monkeypatch.setattr(api_main, "get_flagged_tickets_full", lambda: [{"ticket_id": "TFS-1"}])
    monkeypatch.setattr(api_main, "get_flagged_ticket_counts", lambda: [{"flag_reason": "stale", "ticket_count": 1}])
    monkeypatch.setattr(api_main, "get_pending_reviews", lambda: [{"pr_id": "PR-1"}])
    monkeypatch.setattr(api_main, "get_open_tickets_at_risk", lambda: [{"ticket_id": "TFS-2"}])
    monkeypatch.setattr(api_main, "build_daily_snapshots", lambda: {"Jane": {"done": []}})
    monkeypatch.setattr(api_main, "write_panels_snapshot", lambda snap: None)

    resp = client.get("/panels")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_watcher"] == {
        "tickets": [{"ticket_id": "TFS-1"}],
        "counts": [{"flag_reason": "stale", "ticket_count": 1}],
    }
    assert data["review_nudger"] == {"reviews": [{"pr_id": "PR-1"}]}
    assert data["bottleneck_detector"] == {"tickets": [{"ticket_id": "TFS-2"}]}
    assert data["standup_writer"] == {"engineers": {"Jane": {"done": []}}}
    assert data["generated_at"]


def test_panels_caches_its_result(monkeypatch):
    monkeypatch.setattr(api_main, "get_flagged_tickets_full", lambda: [])
    monkeypatch.setattr(api_main, "get_flagged_ticket_counts", lambda: [])
    monkeypatch.setattr(api_main, "get_pending_reviews", lambda: [])
    monkeypatch.setattr(api_main, "get_open_tickets_at_risk", lambda: [])
    monkeypatch.setattr(api_main, "build_daily_snapshots", lambda: {})
    captured = {}
    monkeypatch.setattr(api_main, "write_panels_snapshot", lambda snap: captured.update(snap))

    client.get("/panels")

    assert captured["generated_at"]
    assert captured["ticket_watcher"] == {"tickets": [], "counts": []}


def test_latest_panels_returns_cached_output(monkeypatch):
    cached = {"generated_at": "2026-08-30T10:00:00+00:00", "ticket_watcher": {"tickets": [], "counts": []}}
    monkeypatch.setattr(api_main, "get_latest_panels", lambda: cached)

    resp = client.get("/panels/latest")

    assert resp.status_code == 200
    assert resp.json() == cached


def test_latest_panels_404s_when_nothing_cached(monkeypatch):
    monkeypatch.setattr(api_main, "get_latest_panels", lambda: None)

    resp = client.get("/panels/latest")

    assert resp.status_code == 404


def test_standup_history_respects_explicit_range(monkeypatch):
    captured = {}

    def fake_get_history(engineer, start, end):
        captured["args"] = (engineer, start, end)
        return []

    monkeypatch.setattr(api_main, "get_standup_history", fake_get_history)

    resp = client.get("/standups/Jane?start=2026-08-01&end=2026-08-05")

    assert resp.status_code == 200
    assert captured["args"] == ("Jane", "2026-08-01", "2026-08-05")
