"""Deterministic mock LLM responses for `LLM_MOCK=true` (PLAN.md §5, §9).

Used in place of a real `app.llm.client.get_chat_response` call so E2E tests
and local development can exercise the full chat -> auto-execution pipeline
without an OpenRouter API key or network access.

Trigger rules (checked in this order, case-insensitive, matched anywhere in
the user's message):

1. Watchlist add    : "add <TICKER> to watchlist" or "add <TICKER> to the
                       watchlist"
                       -> watchlist_changes=[{ticker: TICKER, action: "add"}]
2. Watchlist remove : "remove <TICKER> from watchlist" or "remove <TICKER>
                       from the watchlist"
                       -> watchlist_changes=[{ticker: TICKER, action:
                       "remove"}]
3. Trade            : "buy <QTY> shares of <TICKER>" / "buy <QTY> <TICKER>"
                       or the same with "sell" instead of "buy"
                       -> trades=[{ticker: TICKER, side: "buy"|"sell",
                       quantity: QTY}]
                       (QTY is a positive number, e.g. "10" or "2.5"; TICKER
                       is 1-5 letters, e.g. AAPL, GOOGL, V. Case-insensitive;
                       "shares of" is optional.)
                       Note: this only builds the structured trade request —
                       the actual success/failure (e.g. insufficient cash)
                       is decided by `db.execute_trade` in `app/api/chat.py`,
                       exactly as for a real LLM response. Request an
                       oversized quantity (e.g. "buy 999999 shares of AAPL")
                       to deterministically exercise the failure path.
4. Anything else    : a plain conversational reply with no actions.

Only the first matching rule applies (watchlist rules are checked before
the trade rule since they use disjoint keywords, so overlap is not
expected in practice).
"""

from __future__ import annotations

import re

from .schema import ChatResponse, TradeAction, WatchlistChange

_TICKER = r"[A-Za-z]{1,5}"

_WATCHLIST_ADD_RE = re.compile(
    rf"\badd\s+({_TICKER})\s+to\s+(?:the\s+)?watchlist\b", re.IGNORECASE
)
_WATCHLIST_REMOVE_RE = re.compile(
    rf"\bremove\s+({_TICKER})\s+from\s+(?:the\s+)?watchlist\b", re.IGNORECASE
)
_TRADE_RE = re.compile(
    rf"\b(buy|sell)\s+(\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?({_TICKER})\b", re.IGNORECASE
)


def get_mock_response(user_message: str) -> ChatResponse:
    """Deterministically map a user message to a `ChatResponse`. See module
    docstring for the exact trigger rules.
    """
    add_match = _WATCHLIST_ADD_RE.search(user_message)
    if add_match:
        ticker = add_match.group(1).upper()
        return ChatResponse(
            message=f"Mock mode: adding {ticker} to your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="add")],
        )

    remove_match = _WATCHLIST_REMOVE_RE.search(user_message)
    if remove_match:
        ticker = remove_match.group(1).upper()
        return ChatResponse(
            message=f"Mock mode: removing {ticker} from your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="remove")],
        )

    trade_match = _TRADE_RE.search(user_message)
    if trade_match:
        side = trade_match.group(1).lower()
        quantity = float(trade_match.group(2))
        ticker = trade_match.group(3).upper()
        return ChatResponse(
            message=f"Mock mode: executing a {side} order for {quantity:g} shares of {ticker}.",
            trades=[TradeAction(ticker=ticker, side=side, quantity=quantity)],
        )

    return ChatResponse(
        message=(
            "Mock mode: I received your message - "
            f'"{user_message}". (Deterministic placeholder response; set '
            "LLM_MOCK=false and provide OPENROUTER_API_KEY for real AI "
            "analysis.)"
        ),
    )
