# Market Data Backend — Design

Consolidated design reference for FinAlly's market data subsystem: the unified `MarketDataSource` interface, the `PriceCache`, the GBM simulator, and the Massive (Polygon.io) REST client. This document describes the system **as actually implemented** in `backend/app/market/` (8 modules, ~770 lines, 73 passing tests, 84% coverage) — it consolidates and supersedes the three topic docs (`MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md`) and the original pre-build sketch in `planning/archive/MARKET_DATA_DESIGN.md` into a single reference. See `MARKET_DATA_SUMMARY.md` for the short status summary.

## 1. Architecture

```
MarketDataSource (ABC)
├── SimulatorDataSource  →  GBM simulator (default, no API key needed)
└── MassiveDataSource    →  Polygon.io REST poller (when MASSIVE_API_KEY is set)
        │
        ▼
   PriceCache (thread-safe, in-memory, single shared instance)
        │
        ├──→ SSE stream endpoint  (GET /api/stream/prices)
        ├──→ Portfolio valuation  (reads price_cache.get_price(ticker))
        └──→ Trade execution      (reads price_cache.get_price(ticker))
```

Both data sources are **producers** that push into a shared `PriceCache` on their own schedule — the simulator ticks every 500ms, Massive polls every 15s by default. Everything downstream (SSE, portfolio math, trade execution) is a **consumer** that reads current state from the cache. Nothing downstream imports `massive` or the simulator directly, and nothing downstream needs to know which source is active.

### Design goals

1. **Source-agnostic downstream code.** SSE streaming, portfolio math, and trade execution depend on one cache type, never on a provider.
2. **Zero-config default.** No `MASSIVE_API_KEY` → the app still fully works, using the simulator. This is the expected path for most students running the project.
3. **Single point of truth for "current price."** Both producers write through the same cache API; there's exactly one place that computes `change` / `change_percent` / `direction`.
4. **Cheap to extend.** A third source (e.g. a future WebSocket-based real-time feed, see §8.5) is just another `MarketDataSource` implementation — no changes needed anywhere else.

### File structure (as built)

```
backend/
  app/
    market/
      __init__.py          # Public API surface (re-exports below)
      models.py             # PriceUpdate
      interface.py          # MarketDataSource ABC
      cache.py               # PriceCache
      factory.py             # create_market_data_source()
      massive_client.py      # MassiveDataSource
      simulator.py            # GBMSimulator + SimulatorDataSource
      seed_prices.py           # SEED_PRICES, TICKER_PARAMS, correlation constants
      stream.py                # create_stream_router() — SSE endpoint factory
  tests/
    market/                   # 73 tests across 6 modules, 84% overall coverage
```

Public API, from `app/market/__init__.py`:

```python
from app.market import (
    PriceUpdate,              # Immutable price snapshot dataclass
    PriceCache,                # Thread-safe in-memory price store
    MarketDataSource,           # Abstract interface for data providers
    create_market_data_source,  # Factory that selects simulator or Massive
    create_stream_router,       # FastAPI router factory for the SSE endpoint
)
```

---

## 2. Core Data Model — `PriceUpdate`

The only data structure that leaves the market data layer. Neither `massive` types nor simulator internals ever reach the cache, the SSE layer, or API routes.

```python
# app/market/models.py
from __future__ import annotations
import time
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from previous update."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

`change`, `change_percent`, and `direction` are computed **properties**, not stored fields set at construction time. This keeps `PriceUpdate` a pure value object — the derived fields can never drift from `price` / `previous_price`, because they're recomputed from them every access.

---

## 3. Abstract Interface — `MarketDataSource`

```python
# app/market/interface.py
from __future__ import annotations
from abc import ABC, abstractmethod

class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code never calls the data source directly for prices
    — it reads from the cache.

    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL", ...])
        # ... app runs ...
        await source.add_ticker("TSLA")
        await source.remove_ticker("GOOGL")
        # ... app shutting down ...
        await source.stop()
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.
        Starts a background task. Call exactly once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources. Safe to call repeatedly."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set and from the PriceCache."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the current list of actively tracked tickers."""
```

The interface deliberately has **no method that returns a price**. Both implementations push into the cache on their own cadence — 500ms for the simulator, 2–15s for Massive — and callers always read current state from the cache. This decouples "how often does the source refresh" from "how often does the consumer want to read," which matters because the two run at very different rates.

---

## 4. Price Cache — `PriceCache`

Shared, thread-safe store. Both data sources write to it; the SSE streamer, portfolio valuation, and trade execution all read from it.

```python
# app/market/cache.py
from __future__ import annotations
import time
from threading import Lock
from .models import PriceUpdate

class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming endpoint, portfolio valuation, trade execution.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price. Computes direction/change from the previous price.
        If this is the first update for the ticker, previous_price == price."""
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Snapshot of all current prices. Returns a shallow copy."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        """Monotonic counter bumped on every update — cheap SSE change detection."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

**Threading note**: `PriceCache` uses a plain `threading.Lock`, not an `asyncio.Lock`, because `MassiveDataSource` calls into it from a worker thread (via `asyncio.to_thread`, since the Massive REST client is synchronous) as well as from the event loop directly (the simulator path). A `threading.Lock` is safe from both contexts; an `asyncio.Lock` is only safe from within the event loop.

**Why a version counter**: the SSE endpoint (§7) polls `price_cache.version` every tick and skips serializing/sending a payload when nothing changed, instead of diffing dictionaries — the hot path for an idle connection becomes an integer comparison.

---

## 5. Factory — `create_market_data_source`

The single switch point for provider selection. Nothing else in the codebase branches on `MASSIVE_API_KEY`.

```python
# app/market/factory.py
from __future__ import annotations
import logging
import os
from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)

def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """MASSIVE_API_KEY set and non-empty -> MassiveDataSource; otherwise -> SimulatorDataSource.

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
```

---

## 6. Simulator — `GBMSimulator` + `SimulatorDataSource`

Default, zero-config path. Uses **Geometric Brownian Motion (GBM)** — the same stochastic process underlying Black-Scholes option pricing. Prices evolve continuously with random noise, can never go negative (the process is multiplicative via `exp()`), and produce the lognormal price-path distribution seen in real markets.

### 6.1 GBM math

At each time step:

```
S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
```

- `S(t)` — current price
- `mu` — annualized drift (expected return), e.g. `0.05` = 5%/year
- `sigma` — annualized volatility, e.g. `0.20` = 20%/year
- `dt` — time step as a fraction of a trading year
- `Z` — a (correlated) standard normal random draw

### 6.2 Choosing `dt`

For 500ms ticks over a 252-day trading year at 6.5 hours/day:

```
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600 = 5,896,800
DEFAULT_DT = 0.5 / 5,896,800 ≈ 8.48e-8
```

This tiny `dt` produces sub-cent moves per tick that compound naturally into realistic intraday ranges over the course of a session — a ticker with `sigma=0.50` (TSLA) drifts through roughly the right intraday range over minutes of wall-clock time.

### 6.3 Correlated moves

Real stocks don't move independently — sector peers tend to move together. The simulator builds a correlation matrix from sector groupings and applies a **Cholesky decomposition** to turn independent normal draws into correlated ones:

```
L = cholesky(correlation_matrix)
Z_correlated = L @ Z_independent
```

Cholesky decomposition requires the input matrix to be positive semi-definite, which any valid correlation matrix (1s on the diagonal, pairwise correlations in `[-1, 1]`, symmetric) satisfies.

### 6.4 Seed data and correlation structure

```python
# app/market/seed_prices.py
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00, "GOOGL": 175.00, "MSFT": 420.00, "AMZN": 185.00,
    "TSLA": 250.00, "NVDA": 800.00, "META": 500.00, "JPM": 195.00,
    "V": 280.00, "NFLX": 600.00,
}

TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},   # high volatility
    "NVDA":  {"sigma": 0.40, "mu": 0.08},   # high volatility, strong drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},   # low volatility (bank)
    "V":     {"sigma": 0.17, "mu": 0.04},   # low volatility (payments)
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}  # for tickers added at runtime

CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

INTRA_TECH_CORR = 0.6      # tech stocks move together
INTRA_FINANCE_CORR = 0.5   # finance stocks move together
CROSS_GROUP_CORR = 0.3     # cross-sector and unknown-ticker baseline
TSLA_CORR = 0.3            # TSLA checked against ANY other ticker first — it's a loner
```

Pairwise lookup checks TSLA first — even though it's not in its own explicit group, any pair involving TSLA gets `0.3` regardless of the other ticker's sector — then falls through to tech/finance intra-group checks, defaulting to `CROSS_GROUP_CORR` otherwise. A ticker added at runtime that isn't in `SEED_PRICES` starts at a random price drawn uniformly from `$50`–`$300`, with `DEFAULT_PARAMS` volatility/drift, and correlates with everything at the `0.3` baseline.

### 6.5 Random shock events

Each tick, each ticker independently has a small chance of a sudden 2–5% jump, for visual drama on the dashboard:

```python
event_probability = 0.001   # ~0.1% per ticker per tick

if random.random() < event_probability:
    shock_magnitude = random.uniform(0.02, 0.05)
    shock_sign = random.choice([-1, 1])
    price *= 1 + shock_magnitude * shock_sign
```

At 2 ticks/sec, `0.001` probability means an event roughly every 500 seconds *per ticker*. With 10 tickers in the default watchlist, expect a visible event somewhere in the grid roughly every 50 seconds — frequent enough to be interesting without feeling chaotic. Shocks are independent per ticker per tick; there's no correlation applied to the shock itself, only to the base GBM diffusion term, so two tickers can shock in the same tick purely by chance.

### 6.6 `GBMSimulator` — pure math, no asyncio

```python
# app/market/simulator.py
import math, random
import numpy as np

class GBMSimulator:
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR    # ~8.48e-8

    def __init__(self, tickers: list[str], dt: float = DEFAULT_DT,
                 event_probability: float = 0.001) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None
        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def step(self) -> dict[str, float]:
        """Advance all tickers by one time step. Hot path — called every 500ms."""
        n = len(self._tickers)
        if n == 0:
            return {}

        z_independent = np.random.standard_normal(n)
        z = self._cholesky @ z_independent if self._cholesky is not None else z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            mu, sigma = self._params[ticker]["mu"], self._params[ticker]["sigma"]
            drift = (mu - 0.5 * sigma**2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            if random.random() < self._event_prob:
                shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
                self._prices[ticker] *= 1 + shock

            result[ticker] = round(self._prices[ticker], 2)
        return result

    def add_ticker(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()     # O(n^2), but n < 50 — negligible

    def remove_ticker(self, ticker: str) -> None:
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    def _add_ticker_internal(self, ticker: str) -> None:
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return
        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = corr[j, i] = rho
        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        tech, finance = CORRELATION_GROUPS["tech"], CORRELATION_GROUPS["finance"]
        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

Notes:
- Prices can never go negative — the update is `price *= exp(...)`, and `exp()` is always positive regardless of its argument.
- The Cholesky decomposition is rebuilt on every `add_ticker` / `remove_ticker`, not incrementally updated. `O(n^2)` is trivial at the expected scale (watchlists of single/low-double-digit tickers).
- `round(price, 2)` happens only on the returned value, so the simulator's internal running price retains full float precision between ticks — rounding doesn't compound error over time the way it would if the rounded value were fed back in as the next step's `S(t)`.

### 6.7 `SimulatorDataSource` — the `MarketDataSource` adapter

`GBMSimulator` is pure, synchronous, in-memory math with no knowledge of asyncio, the cache, or the rest of the app. `SimulatorDataSource` adapts it to the `MarketDataSource` interface: an `asyncio.Task` loop calls `step()` every `update_interval` (default 0.5s) and writes each resulting price into the shared `PriceCache`.

```python
class SimulatorDataSource(MarketDataSource):
    def __init__(self, price_cache: PriceCache, update_interval: float = 0.5,
                 event_probability: float = 0.001) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)
        # Seed the cache synchronously so SSE clients get data on their very
        # first tick, rather than waiting out the first update_interval.
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        while True:
            try:
                if self._sim:
                    for ticker, price in self._sim.step().items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

The broad `except Exception` inside `_run_loop` is deliberate: one bad step (e.g. a transient numpy issue) logs and gets retried next tick, rather than silently killing the background `asyncio.Task` and leaving the watchlist frozen with no further indication anything went wrong.

---

## 7. Integration with SSE

```python
# app/market/stream.py
from __future__ import annotations
import asyncio, json, logging
from collections.abc import AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from .cache import PriceCache

router = APIRouter(prefix="/api/stream", tags=["streaming"])

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Factory pattern injects the PriceCache without module-level globals."""

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
            },
        )

    return router

async def _generate_events(
    price_cache: PriceCache, request: Request, interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    yield "retry: 1000\n\n"  # tells EventSource to auto-reconnect after 1s on drop

    last_version = -1
    try:
        while True:
            if await request.is_disconnected():
                break

            current_version = price_cache.version
            if current_version != last_version:
                last_version = current_version
                prices = price_cache.get_all()
                if prices:
                    data = {ticker: update.to_dict() for ticker, update in prices.items()}
                    yield f"data: {json.dumps(data)}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass  # client disconnected mid-await; let the generator end cleanly
```

Each connected client runs its own copy of `_generate_events`, each polling the **same** `price_cache.version` — polling the counter rather than diffing `get_all()` dictionaries keeps the hot path (every 500ms, per connected client) to an integer comparison when nothing changed.

Wire-up, once per app:

```python
from app.market import PriceCache, create_market_data_source, create_stream_router

price_cache = PriceCache()
app.include_router(create_stream_router(price_cache))
```

---

## 8. Massive API (real market data)

### 8.1 Overview

- **Product**: Massive — Polygon.io rebranded. Legacy `polygon-api-client` endpoints and domain still work; new package name is `massive`.
- **Python package**: `massive` — `uv add massive`. Min Python 3.9+.
- **Auth**: `MASSIVE_API_KEY` env var, or passed explicitly to `RESTClient(api_key=...)`.
- **Two transports**: a synchronous `RESTClient` (used here) and a `WebSocketClient` for push-based streaming (not used — see §8.5).

```python
from massive import RESTClient
client = RESTClient()                 # reads MASSIVE_API_KEY from env
client = RESTClient(api_key="...")    # or pass explicitly
```

### 8.2 Rate limits

| Tier | Limit |
|------|-------|
| Free | 5 requests/minute |
| Paid | Substantially higher, scales with plan |

The free tier is the binding constraint for a polling design: exceeding it returns HTTP 429. FinAlly's default poll interval (15s) keeps a single watchlist comfortably under 5 req/min, since it's always exactly one request per poll regardless of watchlist size.

### 8.3 `get_snapshot_all` — the endpoint FinAlly uses

Returns current data for an arbitrary list of tickers in **one HTTP request** — what makes polling a multi-symbol watchlist viable on the free tier.

**REST**: `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT`

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient()
snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
)
for snap in snapshots:
    print(snap.ticker, snap.last_trade.price)
```

`TickerSnapshot` field shape (`massive/rest/models/snapshot.py`):

```python
@modelclass
class TickerSnapshot:
    day: Optional[Agg] = None                # today's OHLCV so far
    last_quote: Optional[LastQuote] = None    # current NBBO bid/ask
    last_trade: Optional[LastTrade] = None    # most recent trade
    min: Optional[MinuteSnapshot] = None       # most recent minute bar
    prev_day: Optional[Agg] = None             # previous session's OHLCV
    ticker: Optional[str] = None
    todays_change: Optional[float] = None       # absolute day change (top-level)
    todays_change_percent: Optional[float] = None  # % day change (top-level)
    updated: Optional[int] = None                # ns since epoch
```

Field reference:

| What you want | Field |
|---|---|
| Current/last traded price | `snap.last_trade.price` |
| Previous close | `snap.prev_day.close` (not under `day`) |
| Day change (absolute / %) | `snap.todays_change` / `snap.todays_change_percent` (top-level, not under `day`) |
| Today's OHLCV so far | `snap.day.open/.high/.low/.close/.volume/.vwap` |

### 8.4 `MassiveDataSource` — as implemented

```python
# app/market/massive_client.py
import asyncio, logging
from massive import RESTClient
from massive.rest.models import SnapshotMarketType
from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)

class MassiveDataSource(MarketDataSource):
    """Polls GET /v2/snapshot/.../tickers for all watched tickers in one call."""

    def __init__(self, api_key: str, price_cache: PriceCache, poll_interval: float = 15.0) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)
        await self._poll_once()  # immediate first poll so the cache isn't empty on startup
        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)  # picked up on the next poll

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        if not self._tickers or not self._client:
            return
        try:
            # RESTClient is synchronous; run it in a thread so it never blocks the event loop.
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            processed = 0
            for snap in snapshots:
                try:
                    price = snap.last_trade.price
                    timestamp = snap.last_trade.timestamp / 1000.0  # ms -> s
                    self._cache.update(ticker=snap.ticker, price=price, timestamp=timestamp)
                    processed += 1
                except (AttributeError, TypeError) as e:
                    logger.warning("Skipping snapshot for %s: %s", getattr(snap, "ticker", "???"), e)
            logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))
        except Exception as e:
            logger.error("Massive poll failed: %s", e)  # swallow — retry next interval

    def _fetch_snapshots(self) -> list:
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

Design notes:
- **Thread offload**: `RESTClient` is synchronous, so every call goes through `asyncio.to_thread` to avoid blocking the event loop — this is the only place in the market data subsystem that touches a thread pool.
- **Fail-soft per snapshot**: a single malformed/missing snapshot (`AttributeError`/`TypeError`) is logged and skipped rather than aborting the whole poll — one bad ticker doesn't take down the other nine.
- **Fail-soft per poll cycle**: the outer `try/except Exception` means a transient network error or a 429 doesn't crash the `asyncio.Task` — the loop just retries on the next `poll_interval`.
- **Add/remove is eventually consistent**: `add_ticker`/`remove_ticker` only mutate `self._tickers`; the new ticker doesn't get a price until the next scheduled poll (up to `poll_interval` seconds later), unlike the simulator which seeds immediately.

> **⚠️ Known field-mapping risk — verify against the installed `massive` package.** The code above reads `snap.last_trade.timestamp` as Unix **milliseconds**. Per the official client's model source (`massive/rest/models/snapshot.py`, `massive/rest/models/quotes.py`), the sibling `LastQuote` model uses `sip_timestamp` in **nanoseconds**, and `LastTrade` likely follows the same naming convention — meaning the field name and/or unit here may not match the real API response. Because the surrounding code catches `AttributeError`/`TypeError` per snapshot, a mismatch **fails silently**: the affected ticker just stops updating in the cache rather than raising. The existing test suite mocks `RESTClient`, so it would not catch this drift. **Before enabling `MASSIVE_API_KEY` against the live API, run one real (unmocked) poll and inspect the actual attribute names/units on a live `TickerSnapshot`.** Separately, `prev_day.close` / `todays_change` / `todays_change_percent` (§8.3) are documented here for a future day-change feature but are not currently read by `massive_client.py` — today it extracts only `price` and a timestamp.

### 8.5 Error handling

| Status | Meaning | Handling |
|---|---|---|
| 401 | Invalid/missing API key | Fatal — don't retry; surface to the operator |
| 403 | Plan doesn't include this endpoint/market | Fatal for that call — don't retry |
| 429 | Rate limit exceeded (5/min on free tier) | Transient — the outer `except Exception` logs and lets the next interval retry; the interval itself is not auto-tightened |
| 5xx | Server error | Transient — client has built-in retry/backoff; the poll-loop-level catch still swallows so one bad cycle doesn't kill the task |

### 8.6 Why not the WebSocket client

```python
from massive import WebSocketClient
ws = WebSocketClient(api_key="...", subscriptions=["T.AAPL", "T.META"])  # T.=trades
ws.run(handle_msg=lambda msgs: ...)
```

True push-based real-time requires `WebSocketClient`, but most exchanges require a paid real-time data plan for it (free tier WS access is typically delayed/limited), and it adds a persistent connection + reconnect/backoff state machine that REST polling avoids entirely. REST snapshot polling is the deliberately simpler choice for a course project. Because `MassiveDataSource` is just one `MarketDataSource` implementation, a future `WebSocketDataSource` could be added as a third implementation with zero changes to the cache, SSE layer, or any other downstream code.

---

## 9. Lifecycle (end to end)

1. **App startup**:
   ```python
   price_cache = PriceCache()
   source = create_market_data_source(price_cache)   # reads MASSIVE_API_KEY
   await source.start(initial_tickers)                # seeds + starts background task
   app.include_router(create_stream_router(price_cache))
   ```
2. **Watchlist changes** (manual or LLM-driven, per `PLAN.md` §8–9):
   ```python
   await source.add_ticker("TSLA")
   await source.remove_ticker("GOOGL")
   ```
3. **SSE streaming**: each connected client's generator reads `price_cache.get_all()`, gated on `price_cache.version`, every ~500ms.
4. **Trade execution / portfolio valuation**: synchronous `price_cache.get_price(ticker)` — no awaiting, no coupling to the active source.
5. **App shutdown**:
   ```python
   await source.stop()
   ```

---

## 10. Test suite

**73 tests, all passing, 84% overall coverage.**

| Module | Tests | Coverage |
|--------|-------|----------|
| test_models.py | 11 | models.py: 100% |
| test_cache.py | 13 | cache.py: 100% |
| test_simulator.py | 17 | simulator.py: 98% |
| test_simulator_source.py | 10 | (integration tests) |
| test_factory.py | 7 | factory.py: 100% |
| test_massive.py | 13 | massive_client.py: 56% (API methods are mocked — see §8.4 caveat) |

The lower coverage and the mocked `RESTClient` in `test_massive.py` are the direct cause of the field-mapping risk flagged in §8.4: the mocks assert the code calls the right methods with the right arguments, not that the real API's response shape matches what the code expects.

## 11. Manual demo

```bash
cd backend
uv run market_data_demo.py
```

A Rich terminal dashboard showing all 10 default tickers live, with sparklines, color-coded direction arrows, and an event log for notable price moves (random shocks). Runs 60 seconds or until Ctrl+C — useful for eyeballing that the simulator "feels alive" without needing the full frontend.
