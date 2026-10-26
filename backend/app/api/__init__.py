"""API routers for the FinAlly backend.

Each module exposes a module-level `router` (an `APIRouter`) that
`app.main` includes. Routers that need access to shared runtime state
(the `PriceCache` and the running `MarketDataSource`) expose a small
factory function instead (see `portfolio.create_portfolio_router` and
`watchlist.create_watchlist_router`), mirroring the pattern already used
by `app.market.create_stream_router`.
"""
