"""Health check endpoint (PLAN.md §8, §11).

No dependencies on runtime state, so this is a plain module-level router
(unlike `portfolio`/`watchlist`, which need the live `PriceCache`/
`MarketDataSource` and so use a factory function instead).
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe for Docker's HEALTHCHECK and deployment platforms."""
    return {"status": "ok"}
