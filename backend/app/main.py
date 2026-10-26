"""FastAPI app factory / entrypoint for the FinAlly backend (PLAN.md §6-§8, §11).

Responsibilities wired up here:
  - Lazily initialize the DB (handled transparently by `app.db` on first
    call; `db.init_db()` is also invoked explicitly at startup so a cold
    start doesn't pay the init cost on the first request).
  - Create the shared `PriceCache` and market data source, start the source
    with the current watchlist tickers from the DB.
  - Mount the SSE price stream router (`app.market.create_stream_router`).
  - Run an independent `asyncio` background task that records a portfolio
    snapshot every 30 seconds (separate cadence from the ~500ms market tick
    loop, per PLAN.md §7).
  - Register all `/api/*` routers *before* mounting the built frontend
    static export at `/`, so the catch-all static mount never shadows an
    API route.
  - On shutdown, stop the market data source and cancel the snapshot task
    cleanly.

`app/api/chat.py` (LLM engineer's responsibility) is not created here, but
adding it is a single `app.include_router(chat.router)` call inside
`create_app`, alongside the others below.

Exposes `create_app()` (a factory, used by tests to build an isolated app —
its own `PriceCache` and market data source — per test) plus a module-level
`app = create_app()` for the `app.main:app` entrypoint uvicorn/the Dockerfile
expect.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.api.chat import create_chat_router
from app.api.health import router as health_router
from app.api.portfolio import compute_total_value, create_portfolio_router
from app.api.watchlist import create_watchlist_router
from app.market import PriceCache, create_market_data_source, create_stream_router

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 30

# backend/app/main.py -> parents[1] is backend/. Matches the Dockerfile's
# `COPY --from=frontend-build /app/frontend/out ./static` destination
# (WORKDIR /app/backend), i.e. backend/static.
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _snapshot_loop_factory(price_cache: PriceCache, interval: float = SNAPSHOT_INTERVAL_SECONDS):
    async def _snapshot_loop() -> None:
        """Independent background task: record a portfolio snapshot every
        `interval` seconds. Deliberately decoupled from the market data tick
        loop (PLAN.md §7) and from the immediate post-trade snapshot in
        `app.api.portfolio.trade`.
        """
        while True:
            try:
                await asyncio.sleep(interval)
                total_value = compute_total_value(price_cache)
                db.record_snapshot(total_value)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive; keep the loop alive
                logger.exception("Snapshot background task failed; will retry next interval.")

    return _snapshot_loop


def create_app(*, static_dir: Path | None = None) -> FastAPI:
    """Build a fresh FastAPI app with its own `PriceCache` and market data
    source. Used both for the production `app` singleton below and for
    isolated test apps (each test gets its own cache/source instances and,
    via `FINALLY_DB_PATH`, its own database).
    """
    price_cache = PriceCache()
    market_source = create_market_data_source(price_cache)
    resolved_static_dir = static_dir if static_dir is not None else STATIC_DIR

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        db.init_db()

        tickers = db.get_watchlist()
        await market_source.start(tickers)

        snapshot_task = asyncio.create_task(_snapshot_loop_factory(price_cache)())

        try:
            yield
        finally:
            await market_source.stop()
            snapshot_task.cancel()
            try:
                await snapshot_task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="FinAlly", lifespan=lifespan)

    # ----------------------------------------------------------------------
    # /api/* routes. Must all be registered before the catch-all static
    # mount below, since Starlette resolves routes in registration order
    # and a Mount("/") would otherwise shadow everything after it.
    # ----------------------------------------------------------------------
    app.include_router(health_router)
    app.include_router(create_portfolio_router(price_cache))
    app.include_router(create_watchlist_router(price_cache, market_source))
    app.include_router(create_stream_router(price_cache))
    app.include_router(create_chat_router(price_cache, market_source))

    # Exposed for tests / introspection (e.g. asserting on cache state).
    app.state.price_cache = price_cache
    app.state.market_source = market_source

    # ----------------------------------------------------------------------
    # Static frontend (Next.js `output: 'export'`). Guarded so the app
    # still starts (and all /api/* routes stay testable) in environments
    # where the frontend hasn't been built yet, e.g. local backend
    # development.
    # ----------------------------------------------------------------------
    if resolved_static_dir.is_dir():
        app.mount("/", StaticFiles(directory=resolved_static_dir, html=True), name="static")
    else:
        logger.warning(
            "Static frontend directory not found at %s; skipping static file "
            "mount. API routes remain available; `/` will 404 until the "
            "frontend is built.",
            resolved_static_dir,
        )

    return app


app = create_app()
