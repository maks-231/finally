"""Structured-output schema for the LLM chat flow (PLAN.md §9).

These pydantic models are the exact contract the LLM is asked to respond
with (via litellm's `response_format=ChatResponse`) and are also what
`app/llm/mock.py` constructs directly for `LLM_MOCK=true` mode. Both real
and mock paths funnel through `ChatResponse.model_validate_json` /
`ChatResponse.model_validate` so `app/api/chat.py` only ever deals with one
shape.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TradeAction(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    message: str
    trades: list[TradeAction] = []
    watchlist_changes: list[WatchlistChange] = []
