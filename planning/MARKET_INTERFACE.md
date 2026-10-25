# Market Data Interface Design

Unified Python interface for market data in FinAlly: one abstract interface, two implementations (`SimulatorDataSource`, `MassiveDataSource`), selected by environment variable. All downstream code — SSE streaming, portfolio valuation, trade execution — depends only on the interface and a shared cache, never on which provider is active.

This describes the design as it is actually implemented in `backend/app/market/` (8 modules). It supersedes `planning/archive/MARKET_INTERFACE.md`, correcting it in one place where the sketch diverged from the shipped code and from the real Massive API field names documented in `MASSIVE_API.md`.

## Design Goals

1. **Source-agnostic downstream code.** SSE streaming, portfolio math, and trade execution read from one cache type and never import `massive` or the simulator directly.
2. **Zero-config default.** No API key → the app still fully works, using the simulator. This is the common case for students running the project.
3. **Single point of truth for "current price."** Both producers write through the same cache API; there's exactly one place that computes `change`/`direction`.
4. **Cheap to extend.** A third source (e.g., a future WebSocket-based real-time source, see `MASSIVE_API.md`) is just another `MarketDataSource` implementation — no changes needed elsewhere.

## Core Data Model — `PriceUpdate`

```python
from dataclasses import dataclass, field
import time

@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""
    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
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

`change`, `change_percent`, and `direction` are computed **properties**, not stored fields — this is the one meaningful change from the original sketch (which stored `change`/`direction` as plain fields set at construction time). Deriving them keeps `PriceUpdate` a pure value object and makes it impossible for the stored fields to drift from `price`/`previous_price`.

This is the only data structure that leaves the market data layer. Neither `massive` types nor simulator internals ever reach the cache, SSE layer, or API routes.

## Abstract Interface — `MarketDataSource`

```python
from abc import ABC, abstractmethod

class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code never calls the data source directly for prices
    — it reads from the cache.
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing updates for the given tickers. Call exactly once."""

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

The interface deliberately has **no method that returns a price**. Both implementations are producers that push into a shared cache on their own cadence (500ms for the simulator, 2–15s for Massive) — callers always read current state from the cache, never from the source. This decouples "how often does the source refresh" from "how often does the consumer want to read," which matters because the two run at very different rates.

## Price Cache — `PriceCache`

Shared, thread-safe store. Both data sources write to it; the SSE streamer, portfolio valuation, and trade execution all read from it.

```python
import time
from threading import Lock

class PriceCache:
    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # bumped on every update — cheap SSE change detection

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
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

    def get(self, ticker: str) -> PriceUpdate | None: ...
    def get_price(self, ticker: str) -> float | None: ...   # convenience: just the float
    def get_all(self) -> dict[str, PriceUpdate]: ...          # shallow-copy snapshot
    def remove(self, ticker: str) -> None: ...

    @property
    def version(self) -> int: ...   # monotonic counter for SSE change detection
```

The `version` counter lets the SSE endpoint skip serializing/sending a payload when nothing changed since the last tick, instead of diffing dictionaries.

**Threading note**: `PriceCache` uses a plain `threading.Lock`, not an `asyncio.Lock`, because `MassiveDataSource` calls into it from a worker thread (via `asyncio.to_thread`) as well as from the event loop. A `threading.Lock` is safe from both contexts; an `asyncio.Lock` would not be.

## Factory — `create_market_data_source`

```python
import os

def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """MASSIVE_API_KEY set and non-empty -> MassiveDataSource; otherwise -> SimulatorDataSource.

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```

This is the single switch point for provider selection. Nothing else in the codebase branches on `MASSIVE_API_KEY`.

## `MassiveDataSource`

Backed by `massive.RESTClient.get_snapshot_all` (one call per poll, covers the whole watchlist). See `MASSIVE_API.md` for full endpoint documentation and field mapping.

```python
import asyncio
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

class MassiveDataSource(MarketDataSource):
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

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)

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
            snapshots = await asyncio.to_thread(
                self._client.get_snapshot_all,
                market_type=SnapshotMarketType.STOCKS,
                tickers=self._tickers,
            )
            for snap in snapshots:
                try:
                    self._cache.update(
                        ticker=snap.ticker,
                        price=snap.last_trade.price,
                        timestamp=snap.last_trade.sip_timestamp / 1_000_000_000,  # ns -> s
                    )
                except (AttributeError, TypeError) as e:
                    logger.warning("Skipping snapshot for %s: %s", getattr(snap, "ticker", "?"), e)
        except Exception as e:
            logger.error("Massive poll failed: %s", e)  # retry next interval, don't crash the task
```

**Action item surfaced by this research** (see `MASSIVE_API.md` → Corrections): the field names above (`last_trade.sip_timestamp`, nanosecond conversion) differ from what's currently in `backend/app/market/massive_client.py` (`last_trade.timestamp`, millisecond conversion, and `day.previous_close` elsewhere in the module for day-change math). The current code's `except (AttributeError, TypeError)` means a field mismatch fails closed (tickers silently stop updating) rather than crashing — it should be verified against the real installed `massive` package, since the existing test suite mocks the client and would not catch a field-name drift against the live API.

## `SimulatorDataSource`

Backed by the GBM simulator — see `MARKET_SIMULATOR.md` for the math and implementation. Wraps `GBMSimulator` in a 500ms `asyncio` loop:

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
        for ticker in tickers:                     # seed the cache immediately,
            price = self._sim.get_price(ticker)    # so SSE has data before the first tick
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

## Integration with SSE

```python
async def _generate_events(price_cache: PriceCache, request: Request, interval: float = 0.5):
    yield "retry: 1000\n\n"
    last_version = -1
    while True:
        if await request.is_disconnected():
            break
        if price_cache.version != last_version:
            last_version = price_cache.version
            prices = price_cache.get_all()
            if prices:
                data = {ticker: update.to_dict() for ticker, update in prices.items()}
                yield f"data: {json.dumps(data)}\n\n"
        await asyncio.sleep(interval)
```

Polling the `version` counter rather than diffing `get_all()` dictionaries keeps the hot path (every 500ms, per connected client) to an integer comparison when nothing changed.

## File Structure (as built)

```
backend/
  app/
    market/
      __init__.py
      models.py              # PriceUpdate
      interface.py           # MarketDataSource ABC
      cache.py                # PriceCache
      factory.py              # create_market_data_source()
      massive_client.py       # MassiveDataSource
      simulator.py            # GBMSimulator + SimulatorDataSource
      seed_prices.py          # SEED_PRICES, TICKER_PARAMS, correlation constants
      stream.py               # create_stream_router() — SSE endpoint factory
  tests/
    market/                  # 73 tests across 6 modules, 84% overall coverage
```

## Lifecycle

1. **App startup**: `cache = PriceCache()`; `source = create_market_data_source(cache)`; `await source.start(initial_tickers)`.
2. **Watchlist changes**: `await source.add_ticker(t)` / `await source.remove_ticker(t)`.
3. **SSE streaming**: reads `price_cache.get_all()` (gated on `version`) every ~500ms per connected client.
4. **Trade execution / portfolio valuation**: reads `price_cache.get_price(ticker)` synchronously.
5. **App shutdown**: `await source.stop()`.
