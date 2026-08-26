import asyncio

from agents.common import agent_runner


class _FakePart:
    def __init__(self, text):
        self.text = text


class _FakeContent:
    def __init__(self, parts):
        self.parts = parts


class _FakeEvent:
    def __init__(self, final, texts=None):
        self._final = final
        self.content = _FakeContent([_FakePart(t) for t in texts]) if texts else None

    def is_final_response(self):
        return self._final


class _FakeSession:
    id = "sess-1"


class _FakeSessionService:
    async def create_session(self, app_name, user_id):
        return _FakeSession()


class _FakeInMemoryRunner:
    def __init__(self, agent, app_name):
        self.agent = agent
        self.app_name = app_name
        self.session_service = _FakeSessionService()

    async def run_async(self, user_id, session_id, new_message):
        for event in [
            _FakeEvent(final=False, texts=["thinking..."]),
            _FakeEvent(final=True, texts=["final ", "answer"]),
        ]:
            yield event


def test_run_agent_once_extracts_only_final_response_text(monkeypatch):
    monkeypatch.setattr(agent_runner, "InMemoryRunner", _FakeInMemoryRunner)

    result = asyncio.run(agent_runner.run_agent_once(agent=object(), prompt="hi", app_name="test_agent"))

    assert result == "final answer"


def test_run_agent_once_returns_empty_string_if_no_final_response(monkeypatch):
    class _NoFinalRunner(_FakeInMemoryRunner):
        async def run_async(self, user_id, session_id, new_message):
            yield _FakeEvent(final=False, texts=["still thinking"])

    monkeypatch.setattr(agent_runner, "InMemoryRunner", _NoFinalRunner)

    result = asyncio.run(agent_runner.run_agent_once(agent=object(), prompt="hi", app_name="test_agent"))

    assert result == ""
