import operator

from agents.common import firestore_client


class _FakeDoc:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class _FakeQuery:
    _OPS = {">=": operator.ge, "<=": operator.le, "==": operator.eq}

    def __init__(self, docs):
        self._docs = docs

    def where(self, field, op, value):
        op_fn = self._OPS[op]
        return _FakeQuery([d for d in self._docs if op_fn(d[field], value)])

    def order_by(self, field):
        return _FakeQuery(sorted(self._docs, key=lambda d: d[field]))

    def stream(self):
        return [_FakeDoc(d) for d in self._docs]


class _FakeDocRef:
    def __init__(self, store, doc_id):
        self._store = store
        self._doc_id = doc_id

    def set(self, data):
        self._store[self._doc_id] = data

    def get(self):
        return _FakeSnapshot(self._store.get(self._doc_id))


class _FakeSnapshot:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class _FakeScansCollection:
    """Stands in for the top-level `scans` collection (flat, unlike standups)."""

    def __init__(self):
        self.store: dict = {}

    def document(self, doc_id):
        return _FakeDocRef(self.store, doc_id)


class _FakeDaysCollection:
    def __init__(self):
        self.store: dict = {}

    def document(self, doc_id):
        return _FakeDocRef(self.store, doc_id)

    def where(self, field, op, value):
        return _FakeQuery(list(self.store.values())).where(field, op, value)

    def order_by(self, field):
        return _FakeQuery(list(self.store.values())).order_by(field)


class _FakeEngineerDoc:
    def __init__(self, client, engineer):
        self._client = client
        self._engineer = engineer

    def collection(self, name):
        assert name == "days"
        return self._client._engineers.setdefault(self._engineer, _FakeDaysCollection())


class _FakeStandupsCollection:
    def __init__(self, client):
        self._client = client

    def document(self, engineer):
        return _FakeEngineerDoc(self._client, engineer)


class _FakeClient:
    def __init__(self):
        self._engineers: dict = {}
        self.scans = _FakeScansCollection()

    def collection(self, name):
        if name == firestore_client.settings.firestore_scans_collection:
            return self.scans
        assert name == firestore_client.settings.firestore_standups_collection
        return _FakeStandupsCollection(self)


def test_write_standup_snapshot_denormalizes_date_and_engineer(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(firestore_client, "_get_client", lambda: fake_client)

    firestore_client.write_standup_snapshot("Jane Doe", "2026-08-26", {"done": [], "doing": []})

    stored = fake_client._engineers["Jane Doe"].store["2026-08-26"]
    assert stored == {
        "done": [],
        "doing": [],
        "date": "2026-08-26",
        "engineer": "Jane Doe",
    }


def test_get_standup_history_filters_by_date_range_and_orders_chronologically(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(firestore_client, "_get_client", lambda: fake_client)

    for d in ["2026-08-20", "2026-08-24", "2026-08-25", "2026-08-30"]:
        firestore_client.write_standup_snapshot("Jane Doe", d, {"done": []})

    result = firestore_client.get_standup_history("Jane Doe", "2026-08-24", "2026-08-25")

    assert [r["date"] for r in result] == ["2026-08-24", "2026-08-25"]


def test_get_standup_history_is_scoped_to_the_requested_engineer(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(firestore_client, "_get_client", lambda: fake_client)

    firestore_client.write_standup_snapshot("Jane Doe", "2026-08-26", {"done": []})
    firestore_client.write_standup_snapshot("John Smith", "2026-08-26", {"done": []})

    result = firestore_client.get_standup_history("Jane Doe", "2026-08-01", "2026-08-31")

    assert len(result) == 1
    assert result[0]["engineer"] == "Jane Doe"


def test_write_and_read_latest_scan_round_trip(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(firestore_client, "_get_client", lambda: fake_client)

    snapshot = {"generated_at": "2026-08-27T10:00:00+00:00", "agents": {"ticket_watcher": {"text": "x", "ok": True}}}
    firestore_client.write_scan_snapshot(snapshot)

    assert firestore_client.get_latest_scan() == snapshot


def test_get_latest_scan_returns_none_when_never_cached(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(firestore_client, "_get_client", lambda: fake_client)

    assert firestore_client.get_latest_scan() is None


def test_write_scan_snapshot_overwrites_the_single_latest_doc(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(firestore_client, "_get_client", lambda: fake_client)

    firestore_client.write_scan_snapshot({"generated_at": "first", "agents": {}})
    firestore_client.write_scan_snapshot({"generated_at": "second", "agents": {}})

    assert firestore_client.get_latest_scan()["generated_at"] == "second"
    assert len(fake_client.scans.store) == 1
