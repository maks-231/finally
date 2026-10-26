"""Builds the message list sent to the LLM for the chat flow (PLAN.md §9).

Three ingredients, per §9's "How It Works":
  1. A system message ("System Prompt Guidance") instructing the model to
     behave as FinAlly and always respond with valid structured JSON.
  2. Portfolio context — cash, positions with live P&L, watchlist with live
     prices, and total portfolio value — read from the DB (`app.db`) and
     priced via the shared `PriceCache` (same source the REST portfolio/
     watchlist routes use; never a second cache).
  3. Recent conversation history (`get_chat_messages(limit=20)`, oldest
     first) followed by the new user message.
"""

from __future__ import annotations

import json

from app import db
from app.market import PriceCache

SYSTEM_PROMPT = (
    "You are FinAlly, an AI trading assistant embedded in a simulated "
    "trading terminal. You have direct, authorized access to the user's "
    "simulated portfolio and watchlist and can act on their behalf.\n\n"
    "Responsibilities:\n"
    "- Analyze portfolio composition, risk concentration, and P&L using the "
    "portfolio context provided to you.\n"
    "- Suggest trades with clear, data-driven reasoning.\n"
    "- Execute trades when the user asks for one or agrees to a suggestion, "
    "by including them in the `trades` field. Trades execute automatically "
    "with no confirmation step, so only include a trade when the user has "
    "actually requested or agreed to it.\n"
    "- Manage the watchlist proactively (add tickers worth monitoring, "
    "remove ones that are no longer relevant) via `watchlist_changes`.\n"
    "- Be concise and data-driven; prefer concrete numbers over vague "
    "language.\n"
    "- Every trade goes through the same validation as a manual trade "
    "(sufficient cash for buys, no short selling for sells) and may fail; "
    "if a past action in the conversation failed, acknowledge it honestly.\n\n"
    "You must always respond with valid JSON matching the required "
    "structured output schema: a `message` string (required), an optional "
    "`trades` array of {ticker, side, quantity}, and an optional "
    "`watchlist_changes` array of {ticker, action}. Omit `trades` or "
    "`watchlist_changes` (or leave them empty) when no action is warranted."
)


def _position_context(price_cache: PriceCache, position: dict) -> dict:
    ticker = position["ticker"]
    quantity = position["quantity"]
    avg_cost = position["avg_cost"]
    price = price_cache.get_price(ticker)
    if price is None:
        price = avg_cost

    market_value = quantity * price
    cost_basis = quantity * avg_cost
    unrealized_pnl = market_value - cost_basis
    unrealized_pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0

    return {
        "ticker": ticker,
        "quantity": quantity,
        "avg_cost": round(avg_cost, 4),
        "current_price": round(price, 4),
        "market_value": round(market_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "unrealized_pnl_percent": round(unrealized_pnl_percent, 2),
    }


def _watchlist_context(price_cache: PriceCache, tickers: list[str]) -> list[dict]:
    result = []
    for ticker in tickers:
        price = price_cache.get_price(ticker)
        result.append({"ticker": ticker, "price": round(price, 4) if price is not None else None})
    return result


def build_portfolio_context(price_cache: PriceCache, user_id: str = "default") -> dict:
    """Assemble the live portfolio/watchlist snapshot handed to the LLM."""
    cash_balance = db.get_cash_balance(user_id=user_id)
    positions = [_position_context(price_cache, p) for p in db.get_positions(user_id=user_id)]
    total_portfolio_value = cash_balance + sum(p["market_value"] for p in positions)
    watchlist = _watchlist_context(price_cache, db.get_watchlist(user_id=user_id))

    return {
        "cash_balance": round(cash_balance, 2),
        "positions": positions,
        "watchlist": watchlist,
        "total_portfolio_value": round(total_portfolio_value, 2),
    }


def build_messages(
    price_cache: PriceCache, user_message: str, user_id: str = "default"
) -> list[dict]:
    """Build the full `messages` list for the litellm `completion()` call:
    system prompt, portfolio context, last 20 chat_messages rows (oldest
    first), then the new user message.
    """
    context = build_portfolio_context(price_cache, user_id=user_id)
    history = db.get_chat_messages(limit=20, user_id=user_id)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": "Current portfolio context (JSON):\n" + json.dumps(context, indent=2),
        },
    ]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages
