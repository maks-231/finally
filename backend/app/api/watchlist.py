"""Watchlist REST endpoints (PLAN.md §8).

Mutating routes must keep three things in sync: the DB (source of truth for
what's on the watchlist across restarts), the running `MarketDataSource`
(so the SSE stream immediately starts/stops producing updates for the
ticker), and — implicitly — the `PriceCache` (the market data source removes
cache entries itself on `remove_ticker`, per its documented contract).

Needs both the `PriceCache` (to report live prices) and the running
`MarketDataSource` (to add/remove tickers), so this module exposes a
`create_watchlist_router(price_cache, source)` factory, wired up by
`app.main` at startup.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db
from app.market import MarketDataSource, PriceCache


class WatchlistAddRequest(BaseModel):
    ticker: str


def _watchlist_entry(price_cache: PriceCache, ticker: str) -> dict:
    update = price_cache.get(ticker)
    if update is None:
        return {
            "ticker": ticker,
            "price": None,
            "previous_price": None,
            "change": None,
            "change_percent": None,
            "direction": None,
            "timestamp": None,
        }
    return update.to_dict()


def create_watchlist_router(price_cache: PriceCache, source: MarketDataSource) -> APIRouter:
    router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

    @router.get("")
    async def get_watchlist() -> list[dict]:
        tickers = db.get_watchlist()
        return [_watchlist_entry(price_cache, ticker) for ticker in tickers]

    @router.post("")
    async def add_ticker(request: WatchlistAddRequest) -> dict:
        ticker = request.ticker.strip().upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="Ticker must not be empty.")

        added = db.add_to_watchlist(ticker)
        await source.add_ticker(ticker)
        return {"ticker": ticker, "added": added}

    @router.delete("/{ticker}")
    async def remove_ticker(ticker: str) -> dict:
        ticker = ticker.strip().upper()
        removed = db.remove_from_watchlist(ticker)
        if not removed:
            raise HTTPException(
                status_code=404, detail=f"Ticker {ticker!r} is not on the watchlist."
            )
        await source.remove_ticker(ticker)
        return {"ticker": ticker, "removed": removed}

    return router
