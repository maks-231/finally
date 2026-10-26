"""Portfolio REST endpoints (PLAN.md §8).

Routes need read access to the live `PriceCache` to value positions, so this
module exposes a `create_portfolio_router(price_cache)` factory — the same
pattern `app.market.create_stream_router` uses — rather than reaching for a
module-level global. `app.main` wires it up at startup.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.market import PriceCache


class TradeRequest(BaseModel):
    ticker: str
    quantity: float = Field(gt=0)
    side: Literal["buy", "sell"]


def _current_price(price_cache: PriceCache, ticker: str, avg_cost: float) -> tuple[float, bool]:
    """Resolve the price to value a position at.

    Returns (price, is_live). Falls back to the position's avg_cost (and
    is_live=False) if the ticker has no price in the cache yet — this keeps
    `/api/portfolio` well-defined even for a ticker that was bought and then
    removed from the watchlist (and so stopped receiving live updates).
    """
    price = price_cache.get_price(ticker)
    if price is None:
        return avg_cost, False
    return price, True


def _position_view(price_cache: PriceCache, position: dict) -> dict:
    ticker = position["ticker"]
    quantity = position["quantity"]
    avg_cost = position["avg_cost"]
    price, is_live = _current_price(price_cache, ticker, avg_cost)

    market_value = quantity * price
    cost_basis = quantity * avg_cost
    unrealized_pnl = market_value - cost_basis
    unrealized_pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0

    return {
        "ticker": ticker,
        "quantity": quantity,
        "avg_cost": avg_cost,
        "current_price": price,
        "price_is_live": is_live,
        "market_value": market_value,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_percent": unrealized_pnl_percent,
        "updated_at": position.get("updated_at"),
    }


def compute_total_value(price_cache: PriceCache, user_id: str = "default") -> float:
    """cash + sum(quantity * current/fallback price) across all positions.

    Shared by the trade endpoint (post-trade snapshot) and the independent
    30s snapshot background task in `app.main` (PLAN.md §7).
    """
    cash = db.get_cash_balance(user_id=user_id)
    positions = db.get_positions(user_id=user_id)
    total = cash
    for position in positions:
        price, _ = _current_price(price_cache, position["ticker"], position["avg_cost"])
        total += position["quantity"] * price
    return total


def create_portfolio_router(price_cache: PriceCache) -> APIRouter:
    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

    @router.get("")
    async def get_portfolio() -> dict:
        cash_balance = db.get_cash_balance()
        positions = [_position_view(price_cache, p) for p in db.get_positions()]
        total_value = cash_balance + sum(p["market_value"] for p in positions)
        return {
            "cash_balance": cash_balance,
            "positions": positions,
            "total_value": total_value,
        }

    @router.post("/trade")
    async def trade(request: TradeRequest) -> dict:
        ticker = request.ticker.upper()
        price = price_cache.get_price(ticker)
        if price is None:
            raise HTTPException(
                status_code=400,
                detail=f"No current price available for {ticker!r}; cannot execute trade.",
            )

        result = db.execute_trade(
            ticker=ticker,
            side=request.side,
            quantity=request.quantity,
            price=price,
        )
        if not result.success:
            raise HTTPException(status_code=400, detail=result.reason)

        # Per PLAN.md §7, a snapshot is recorded immediately after each trade,
        # in addition to the independent 30s cadence.
        total_value = compute_total_value(price_cache)
        db.record_snapshot(total_value)

        return {
            "ticker": result.ticker,
            "side": result.side,
            "quantity": result.quantity,
            "price": result.price,
            "cash_balance": result.cash_balance,
            "position_quantity": result.position_quantity,
            "avg_cost": result.avg_cost,
            "total_value": total_value,
        }

    @router.get("/history")
    async def history() -> list[dict]:
        return db.get_snapshot_history()

    return router
