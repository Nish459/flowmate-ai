"""Programmatic single-turn invocation of an ADK agent -- lets the FastAPI
backend drive a "scan" without shelling out to `adk run`/`adk web`. Uses the
same InMemoryRunner pattern those CLI tools use internally.
"""

from __future__ import annotations

import asyncio

from google.adk.agents import BaseAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from google.genai.errors import APIError

# The Gemini Developer API key this project uses (aistudio.google.com) sits
# on the free tier -- 5 requests/minute for gemini-3.6-flash, regardless of
# GCP project billing -- and a single agent turn can burn 2+ of those
# (one to decide a tool call, one for the final answer). 429 (rate limited)
# and 503 (model overloaded) are both transient; worth a retry. Anything
# else (4xx like a bad request) is not going to succeed on retry.
_RETRYABLE_STATUS_CODES = {429, 503}
_MAX_ATTEMPTS = 2
# Google's own 429 responses include a suggested retryDelay (observed ~51s
# for this project's quota) -- honor that when present rather than guessing;
# a short fixed/exponential backoff (tried first, and too short) just retries
# straight back into the same unexpired 60s quota window and fails again.
_DEFAULT_BACKOFF_SECONDS = 20.0
_MAX_BACKOFF_SECONDS = 60.0


def _extract_retry_delay_seconds(exc: APIError) -> float | None:
    """Parse the server-suggested retry delay (e.g. '51s') out of a 429/503
    error's details, if present."""
    try:
        for detail in exc.details.get("error", {}).get("details", []):
            if detail.get("@type", "").endswith("RetryInfo"):
                delay = detail.get("retryDelay", "")
                if delay.endswith("s"):
                    return float(delay[:-1])
    except (AttributeError, TypeError, ValueError):
        pass
    return None


async def run_agent_once(agent: BaseAgent, prompt: str, app_name: str, user_id: str = "flowmate-api") -> str:
    """Run one turn against `agent` with `prompt` and return its final text
    response, retrying with backoff on transient Gemini errors."""
    last_error: APIError | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            runner = InMemoryRunner(agent=agent, app_name=app_name)
            session = await runner.session_service.create_session(app_name=app_name, user_id=user_id)

            final_text_parts: list[str] = []
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_text_parts.extend(part.text for part in event.content.parts if part.text)

            return "".join(final_text_parts)
        except APIError as exc:
            if exc.code not in _RETRYABLE_STATUS_CODES:
                raise
            last_error = exc
            if attempt < _MAX_ATTEMPTS - 1:
                delay = _extract_retry_delay_seconds(exc) or _DEFAULT_BACKOFF_SECONDS
                await asyncio.sleep(min(delay, _MAX_BACKOFF_SECONDS))

    raise last_error
