"""Chat REST endpoints (PLAN.md §8, §9).

`GET /api/chat` returns persisted conversation history (for restoring the
chat panel on page load). `POST /api/chat` runs the full LLM chat flow:
build context -> call the LLM (or the deterministic mock, when
`LLM_MOCK=true`) -> auto-execute any trades/watchlist changes through the
*same* DB functions (and the same `PriceCache` / `MarketDataSource`) the
REST trade and watchlist routes use -> persist both the user and assistant
messages -> return the assistant's message plus the executed/failed
actions.

Needs the shared `PriceCache` (to price trades and build portfolio context)
and the running `MarketDataSource` (to keep SSE in sync with watchlist
changes), so this module exposes a `create_chat_router(price_cache,
market_source)` factory — the same pattern `create_portfolio_router` /
`create_watchlist_router` use. `app.main` wires it up at startup.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db
from app.api.portfolio import compute_total_value
from app.llm import ChatResponse, LLMError, build_messages, get_chat_response, get_mock_response
from app.market import MarketDataSource, PriceCache

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str


def _llm_mock_enabled() -> bool:
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"


def _openrouter_key_configured() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def _execute_trades(price_cache: PriceCache, trades: list) -> list[dict]:
    """Auto-execute each proposed trade via `db.execute_trade`, pricing it
    from the shared `PriceCache` (same lookup `POST /api/portfolio/trade`
    uses). A failing trade is recorded with success=False and does not
    prevent the remaining trades/watchlist changes from being attempted.
    """
    results: list[dict] = []
    for trade in trades:
        ticker = trade.ticker.strip().upper()
        if not ticker:
            results.append(
                {
                    "ticker": trade.ticker,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "success": False,
                    "reason": "Ticker must not be empty.",
                }
            )
            continue

        price = price_cache.get_price(ticker)
        if price is None:
            results.append(
                {
                    "ticker": ticker,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "success": False,
                    "reason": f"No current price available for {ticker!r}; cannot execute trade.",
                }
            )
            continue

        result = db.execute_trade(ticker=ticker, side=trade.side, quantity=trade.quantity, price=price)
        if not result.success:
            results.append(
                {
                    "ticker": ticker,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "success": False,
                    "reason": result.reason,
                }
            )
            continue

        # Per PLAN.md §7, a snapshot is recorded immediately after each
        # trade, mirroring the REST trade route.
        total_value = compute_total_value(price_cache)
        db.record_snapshot(total_value)

        results.append(
            {
                "ticker": result.ticker,
                "side": result.side,
                "quantity": result.quantity,
                "price": result.price,
                "cash_balance": result.cash_balance,
                "position_quantity": result.position_quantity,
                "avg_cost": result.avg_cost,
                "total_value": total_value,
                "success": True,
            }
        )
    return results


async def _execute_watchlist_changes(source: MarketDataSource, changes: list) -> list[dict]:
    """Auto-execute each proposed watchlist change via
    `db.add_to_watchlist` / `db.remove_from_watchlist`, also updating the
    live `MarketDataSource` (same as `app.api.watchlist`) so SSE stays in
    sync. A failed removal (ticker not present) does not prevent the
    remaining actions from being attempted.
    """
    results: list[dict] = []
    for change in changes:
        ticker = change.ticker.strip().upper()
        if not ticker:
            results.append(
                {
                    "ticker": change.ticker,
                    "action": change.action,
                    "success": False,
                    "reason": "Ticker must not be empty.",
                }
            )
            continue

        if change.action == "add":
            added = db.add_to_watchlist(ticker)
            await source.add_ticker(ticker)
            results.append(
                {
                    "ticker": ticker,
                    "action": "add",
                    "success": True,
                    "already_present": not added,
                }
            )
        else:  # "remove"
            removed = db.remove_from_watchlist(ticker)
            if removed:
                await source.remove_ticker(ticker)
                results.append({"ticker": ticker, "action": "remove", "success": True})
            else:
                results.append(
                    {
                        "ticker": ticker,
                        "action": "remove",
                        "success": False,
                        "reason": f"{ticker} is not on the watchlist.",
                    }
                )
    return results


def create_chat_router(price_cache: PriceCache, source: MarketDataSource) -> APIRouter:
    router = APIRouter(prefix="/api/chat", tags=["chat"])

    @router.get("")
    async def get_history(limit: int = 20) -> list[dict]:
        return db.get_chat_messages(limit=limit)

    @router.post("")
    async def post_message(request: ChatRequest) -> dict:
        mock_enabled = _llm_mock_enabled()
        if not mock_enabled and not _openrouter_key_configured():
            raise HTTPException(
                status_code=503,
                detail="AI assistant unavailable: OPENROUTER_API_KEY not configured",
            )

        db.append_chat_message("user", request.message)

        if mock_enabled:
            parsed = get_mock_response(request.message)
        else:
            messages = build_messages(price_cache, request.message)
            try:
                parsed = get_chat_response(messages)
            except LLMError:
                logger.exception("LLM call failed or returned unparseable output.")
                parsed = ChatResponse(
                    message=(
                        "Sorry, I had trouble processing that request. Please try again "
                        "in a moment."
                    ),
                )

        executed_trades = _execute_trades(price_cache, parsed.trades)
        executed_watchlist_changes = await _execute_watchlist_changes(
            source, parsed.watchlist_changes
        )

        actions = {"trades": executed_trades, "watchlist_changes": executed_watchlist_changes}
        db.append_chat_message("assistant", parsed.message, actions=actions)

        return {
            "message": parsed.message,
            "trades": executed_trades,
            "watchlist_changes": executed_watchlist_changes,
        }

    return router
