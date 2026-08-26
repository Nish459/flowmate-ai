import asyncio

import pytest
from google.genai.errors import ClientError, ServerError

from agents.common import agent_runner


async def _instant_sleep(seconds):
    return None


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


def test_run_agent_once_retries_on_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr(agent_runner.asyncio, "sleep", _instant_sleep)
    attempts = {"count": 0}

    class _FlakyThenOkRunner(_FakeInMemoryRunner):
        async def run_async(self, user_id, session_id, new_message):
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise ClientError(429, {"error": {"message": "rate limited"}})
            yield _FakeEvent(final=True, texts=["ok now"])

    monkeypatch.setattr(agent_runner, "InMemoryRunner", _FlakyThenOkRunner)

    result = asyncio.run(agent_runner.run_agent_once(agent=object(), prompt="hi", app_name="test_agent"))

    assert result == "ok now"
    assert attempts["count"] == 2


def test_run_agent_once_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(agent_runner.asyncio, "sleep", _instant_sleep)
    attempts = {"count": 0}

    class _AlwaysOverloadedRunner(_FakeInMemoryRunner):
        async def run_async(self, user_id, session_id, new_message):
            attempts["count"] += 1
            raise ServerError(503, {"error": {"message": "overloaded"}})
            yield  # pragma: no cover -- unreachable, keeps this an async generator

    monkeypatch.setattr(agent_runner, "InMemoryRunner", _AlwaysOverloadedRunner)

    with pytest.raises(ServerError):
        asyncio.run(agent_runner.run_agent_once(agent=object(), prompt="hi", app_name="test_agent"))

    assert attempts["count"] == agent_runner._MAX_ATTEMPTS


def test_extract_retry_delay_seconds_parses_retry_info_detail():
    exc = ClientError(
        429,
        {
            "error": {
                "code": 429,
                "message": "quota exceeded",
                "details": [
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "51s"},
                ],
            }
        },
    )

    assert agent_runner._extract_retry_delay_seconds(exc) == 51.0


def test_extract_retry_delay_seconds_returns_none_when_absent():
    exc = ClientError(429, {"error": {"code": 429, "message": "quota exceeded", "details": []}})

    assert agent_runner._extract_retry_delay_seconds(exc) is None


def test_run_agent_once_honors_server_suggested_retry_delay(monkeypatch):
    monkeypatch.setattr(agent_runner.asyncio, "sleep", _instant_sleep)
    slept = {}

    async def _capturing_sleep(seconds):
        slept["seconds"] = seconds

    monkeypatch.setattr(agent_runner.asyncio, "sleep", _capturing_sleep)
    attempts = {"count": 0}

    class _FlakyWithRetryInfoRunner(_FakeInMemoryRunner):
        async def run_async(self, user_id, session_id, new_message):
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise ClientError(
                    429,
                    {
                        "error": {
                            "details": [
                                {"@type": ".../google.rpc.RetryInfo", "retryDelay": "51s"},
                            ]
                        }
                    },
                )
            yield _FakeEvent(final=True, texts=["ok now"])

    monkeypatch.setattr(agent_runner, "InMemoryRunner", _FlakyWithRetryInfoRunner)

    result = asyncio.run(agent_runner.run_agent_once(agent=object(), prompt="hi", app_name="test_agent"))

    assert result == "ok now"
    assert slept["seconds"] == 51.0


def test_run_agent_once_does_not_retry_non_transient_errors(monkeypatch):
    monkeypatch.setattr(agent_runner.asyncio, "sleep", _instant_sleep)
    attempts = {"count": 0}

    class _BadRequestRunner(_FakeInMemoryRunner):
        async def run_async(self, user_id, session_id, new_message):
            attempts["count"] += 1
            raise ClientError(400, {"error": {"message": "bad request"}})
            yield  # pragma: no cover -- unreachable, keeps this an async generator

    monkeypatch.setattr(agent_runner, "InMemoryRunner", _BadRequestRunner)

    with pytest.raises(ClientError):
        asyncio.run(agent_runner.run_agent_once(agent=object(), prompt="hi", app_name="test_agent"))

    assert attempts["count"] == 1
