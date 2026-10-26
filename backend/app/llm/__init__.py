"""LLM chat integration package (PLAN.md §9): structured-output schema,
prompt construction, the real litellm/Cerebras client, and deterministic
mock responses for `LLM_MOCK=true`.
"""

from __future__ import annotations

from .client import LLMError, get_chat_response
from .mock import get_mock_response
from .prompt import build_messages, build_portfolio_context
from .schema import ChatResponse, TradeAction, WatchlistChange

__all__ = [
    "LLMError",
    "get_chat_response",
    "get_mock_response",
    "build_messages",
    "build_portfolio_context",
    "ChatResponse",
    "TradeAction",
    "WatchlistChange",
]
