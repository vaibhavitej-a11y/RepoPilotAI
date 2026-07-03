"""Shared helpers for invoking ADK LlmAgents from analysis skills."""
import asyncio
import logging
import os
import re

from google.adk import Runner
from google.adk.agents.base_agent import BaseAgent
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

logger = logging.getLogger(__name__)

MAX_LLM_RETRIES = 5
SKILL_COOLDOWN_SECONDS = 2.0


def extract_json_text(raw: str) -> str:
    """Strip markdown code fences and isolate a JSON object from LLM text."""
    text = raw.strip()
    if not text:
        return text

    fence_match = re.search(
        r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        return fence_match.group(1).strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]

    return text


def _retry_delay_seconds(exc: BaseException, attempt: int) -> float:
    """Extract retry delay from a rate-limit error, or use exponential backoff."""
    message = str(exc)
    match = re.search(r"retry in ([0-9.]+)s", message, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return min(60.0, 5.0 * (2**attempt))


def _is_retryable_llm_error(exc: BaseException) -> bool:
    message = str(exc)
    if any(token in message for token in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")):
        return True
    if exc.__cause__ is not None:
        return _is_retryable_llm_error(exc.__cause__)
    return any(_is_retryable_llm_error(sub) for sub in getattr(exc, "exceptions", ()))


async def _run_agent_once(
    agent: BaseAgent,
    prompt: str,
    *,
    app_name: str,
    session_id: str,
) -> str:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=app_name,
        user_id="skill-system",
        session_id=session_id,
    )
    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=session_service,
    )

    response_text = ""
    async for event in runner.run_async(
        user_id="skill-system",
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = "".join(
                part.text for part in event.content.parts if part.text
            )

    return response_text


async def run_agent_prompt(
    agent: BaseAgent,
    prompt: str,
    *,
    app_name: str,
    session_id: str,
) -> str:
    """Run an ADK agent via Runner and return the final response text."""
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError(
            "GEMINI_API_KEY is not set in the process environment for skill execution."
        )

    last_error: Exception | None = None
    for attempt in range(MAX_LLM_RETRIES):
        try:
            response_text = await _run_agent_once(
                agent,
                prompt,
                app_name=app_name,
                session_id=f"{session_id}-{attempt}",
            )
            logger.info(
                "Agent %s raw response (%d chars): %r",
                agent.name,
                len(response_text),
                response_text[:2000] if len(response_text) > 2000 else response_text,
            )
            return response_text
        except Exception as exc:
            last_error = exc
            if _is_retryable_llm_error(exc) and attempt < MAX_LLM_RETRIES - 1:
                delay = _retry_delay_seconds(exc, attempt)
                logger.warning(
                    "Agent %s hit transient LLM error (attempt %d/%d); retrying in %.1fs: %s",
                    agent.name,
                    attempt + 1,
                    MAX_LLM_RETRIES,
                    delay,
                    type(exc).__name__,
                )
                await asyncio.sleep(delay)
                continue
            raise

    assert last_error is not None
    raise last_error
