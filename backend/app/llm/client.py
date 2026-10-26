"""Thin wrapper around the litellm `completion()` call (cerebras-inference
skill / PLAN.md §9). Returns a parsed `ChatResponse`, raising `LLMError` on
any failure (network/API error, or malformed/unparseable structured output)
so `app/api/chat.py` can fall back gracefully instead of crashing.
"""

from __future__ import annotations

from litellm import completion

from .schema import ChatResponse

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


class LLMError(Exception):
    """Raised when the LLM call fails or returns output that doesn't match
    the `ChatResponse` schema."""


def get_chat_response(messages: list[dict]) -> ChatResponse:
    """Call the LLM with structured-output enforcement and parse the result
    into a `ChatResponse`. Raises `LLMError` on any failure.
    """
    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=ChatResponse,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any transport/API failure
        raise LLMError(f"LLM call failed: {exc}") from exc

    try:
        content = response.choices[0].message.content
        return ChatResponse.model_validate_json(content)
    except Exception as exc:  # noqa: BLE001 - malformed/unparseable structured output
        raise LLMError(f"Could not parse LLM response as structured output: {exc}") from exc
