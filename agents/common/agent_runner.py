"""Programmatic single-turn invocation of an ADK agent -- lets the FastAPI
backend drive a "scan" without shelling out to `adk run`/`adk web`. Uses the
same InMemoryRunner pattern those CLI tools use internally.
"""

from __future__ import annotations

from google.adk.agents import BaseAgent
from google.adk.runners import InMemoryRunner
from google.genai import types


async def run_agent_once(agent: BaseAgent, prompt: str, app_name: str, user_id: str = "flowmate-api") -> str:
    """Run one turn against `agent` with `prompt` and return its final text response."""
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
