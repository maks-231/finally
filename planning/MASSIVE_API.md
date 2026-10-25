# Massive API Reference (formerly Polygon.io)

Research notes on the Massive REST + WebSocket API and its official Python client, for retrieving real-time and end-of-day prices for multiple tickers. Sourced from the official `massive-com/client-python` repository (README, `docs/source/*.rst`, and model/client source files) via Context7, cross-checked against the client code already vendored into this project at `backend/app/market/massive_client.py`.

This supersedes `planning/archive/MASSIVE_API.md`, which predates this research pass and contains some field-mapping inaccuracies corrected below (see [Corrections vs. the archived doc](#corrections-vs-the-archived-doc)).

## Overview

- **Product**: Massive — Polygon.io rebranded. Legacy `polygon-api-client` endpoints and domain still work; new domain/package names are `massive.com` / `massive`.
- **Base URL**: `https://api.massive.com` (the Python client builds this internally; you never construct it by hand except when inspecting `raw=True` responses)
- **Python package**: `massive` — `pip install -U massive` / `uv add massive`
- **Min Python version**: 3.9+
- **Auth**: `MASSIVE_API_KEY` env var, or passed explicitly to the client constructor
- **Two transports**: a synchronous REST client (`RESTClient`) and a `WebSocketClient` for push-based streaming

```python
from massive import RESTClient

client = RESTClient()                 # reads MASSIVE_API_KEY from env
client = RESTClient("api_key")        # or pass the key directly (positional or api_key=)
```

## Rate Limits

| Tier | Limit |
|------|-------|
| Free | 5 requests/minute |
| Paid (all tiers) | Substantially higher; scales with plan — see massive.com/pricing |

The free tier is the binding constraint for a polling design: exceeding it returns HTTP 429. FinAlly's default poll interval (15s) keeps a single watchlist comfortably under 5 req/min as long as only one poll is in flight at a time.

## REST: Snapshots (closest thing to "real-time" over REST)

Massive has no true real-time REST endpoint — "real-time" over REST means polling a snapshot endpoint that reflects the latest trade/quote tick. True push-based real-time requires the WebSocket client (below). For a single-process, moderate-cadence terminal app, REST polling is simpler and sufficient.

### `get_snapshot_all` — all watched tickers in one call

This is the primary endpoint for FinAlly: it returns current data for an arbitrary list of tickers in **one HTTP request**, which is what makes polling multiple symbols on the free tier's 5 req/min viable.

**REST**: `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT`

**Client signature** (`massive/rest/snapshot.py`):

```python
def get_snapshot_all(
    self,
    market_type: Union[str, SnapshotMarketType],
    tickers: Optional[Union[str, List[str]]] = None,
    params: Optional[Dict[str, Any]] = None,
    raw: bool = False,
    include_otc: Optional[bool] = False,
    options: Optional[RequestOptionBuilder] = None,
) -> Union[List[TickerSnapshot], HTTPResponse]
```

`market_type` accepts either the enum or a plain string ("stocks" | "forex" | "crypto" | "indices"). `tickers` accepts a `list[str]` (joined internally with commas) or a pre-joined string.

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient()
tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=tickers,
)

for snap in snapshots:
    print(snap.ticker, snap.last_trade.price, snap.todays_change_percent)
```

### `TickerSnapshot` — actual field mapping

The client deserializes the raw camelCase JSON into a snake_case dataclass (`massive/rest/models/snapshot.py`). This is the part most worth getting right, because it differs from naive assumptions about where "previous close" and "day change" live:

```python
@modelclass
class TickerSnapshot:
    day: Optional[Agg] = None                       # today's OHLCV so far
    last_quote: Optional[LastQuote] = None           # current NBBO bid/ask
    last_trade: Optional[LastTrade] = None           # most recent trade
    min: Optional[MinuteSnapshot] = None              # most recent minute bar
    prev_day: Optional[Agg] = None                   # <-- previous session's OHLCV lives HERE
    ticker: Optional[str] = None
    todays_change: Optional[float] = None             # <-- absolute day change, TOP-LEVEL
    todays_change_percent: Optional[float] = None     # <-- % day change, TOP-LEVEL
    updated: Optional[int] = None                     # ns since epoch
    fair_market_value: Optional[float] = None         # business/advanced plans only
```

Field access, correctly:

| What you want | Field | Note |
|---|---|---|
| Current/last traded price | `snap.last_trade.price` | |
| Previous close | `snap.prev_day.close` | **not** `snap.day.previous_close` — there's no such field |
| Day change (absolute) | `snap.todays_change` | top-level on the snapshot, not nested under `day` |
| Day change (%) | `snap.todays_change_percent` | JSON key is `todaysChangePerc`; client attribute is `todays_change_percent` |
| Today's OHLCV so far | `snap.day.open/.high/.low/.close/.volume/.vwap` | `Agg` dataclass, shared with the aggregates endpoints |
| Bid/ask | `snap.last_quote.bid_price` / `.ask_price` | |
| Trade timestamp | `snap.last_trade.sip_timestamp` | sibling model `LastQuote` uses `sip_timestamp`; `LastTrade` follows the same convention — **verify against your installed client version**, see [Corrections](#corrections-vs-the-archived-doc) |

`Agg` (used for both `day` and `prev_day`) has `open, high, low, close, volume, vwap, timestamp, transactions` — the same shape as a bar from `list_aggs`.

### `get_snapshot_ticker` — single ticker, with extra detail

Useful for a detail view (e.g., when the user clicks a ticker), rather than polling the whole watchlist.

```python
snapshot = client.get_snapshot_ticker(
    market_type=SnapshotMarketType.STOCKS,
    ticker="AAPL",
)
print(snapshot.last_trade.price, snapshot.prev_day.close)
```

## REST: End-of-Day / Historical

### `get_previous_close_agg` — previous day's OHLC

**REST**: `GET /v2/aggs/ticker/{ticker}/prev`

```python
from massive import RESTClient

client = RESTClient()  # MASSIVE_API_KEY from env

agg = client.get_previous_close_agg("AAPL")
print(agg.open, agg.high, agg.low, agg.close, agg.volume)
```

Signature:

```python
def get_previous_close_agg(
    self,
    ticker: str,
    adjusted: Optional[bool] = None,
    params: Optional[Dict[str, Any]] = None,
    raw: bool = False,
    options: Optional[RequestOptionBuilder] = None,
) -> Union[PreviousCloseAgg, HTTPResponse]
```

`adjusted` defaults to `True` (split-adjusted). This is a single-ticker call — there is no batch "previous close for N tickers" endpoint; for end-of-day prices across a watchlist, either call this once per ticker or pull `prev_day` off `get_snapshot_all` (one call, covers the whole list, and is what FinAlly should prefer).

### `list_aggs` — historical bars (for charts)

**REST**: `GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`

`list_aggs` auto-paginates; `get_aggs` returns one page. Not needed for the live watchlist, but relevant if a historical-chart feature is added later.

```python
aggs = []
for a in client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="day",          # "minute" | "hour" | "day" | "week" | "month" | ...
    from_="2024-01-01",
    to="2024-01-31",
    limit=50000,
):
    aggs.append(a)

for a in aggs:
    print(a.timestamp, a.open, a.high, a.low, a.close, a.volume)
```

Raw JSON shape of one bar (`o/h/l/c/v/vw/t/n`):

```json
{"o": 174.03, "h": 174.88, "l": 171.94, "c": 174.31, "v": 78251328, "vw": 173.4143, "t": 1648785600000, "n": 661160}
```

`t` is Unix **milliseconds**.

## WebSocket: True Real-Time Streaming

REST polling (even at 2–15s) is not real-time in the strict sense — it's frequent sampling. For genuinely real-time ticks, Massive's `WebSocketClient` pushes trade/quote/minute-bar events as they happen.

```python
from massive import WebSocketClient
from massive.websocket.models import WebSocketMessage, EquityTrade
from typing import List

# "T.AAPL" = trades for AAPL, "T.*" = trades for every ticker.
# Prefixes: T.=trades, Q.=quotes, AM.=minute aggregates (also A. for second aggs on some feeds)
ws = WebSocketClient(api_key="<API_KEY>", subscriptions=["T.AAPL", "T.META"])

def handle_msg(msgs: List[WebSocketMessage]):
    for m in msgs:
        if isinstance(m, EquityTrade):
            print(m.symbol, m.price, m.size)

ws.run(handle_msg=handle_msg)
```

Constructor also accepts `feed` (`Feed.RealTime` by default) and `market` (`Market.Stocks` by default), plus `max_reconnects` for automatic reconnection. `ws.subscribe(*subscriptions)` can add subscriptions after construction.

**Why FinAlly doesn't use this today**: the WebSocket feed requires a paid real-time data plan for most exchanges (free tier WebSocket access is typically delayed/limited), and it adds a persistent connection + reconnect/backoff state machine that the REST-polling design avoids entirely. REST snapshot polling is deliberately the simpler choice for a course project; the interface in `MARKET_INTERFACE.md` is designed so a `WebSocketDataSource` could be added later as a third `MarketDataSource` implementation without touching downstream code.

## Error Handling

HTTP-level failures surface as exceptions from the client (`massive.exceptions`):

| Status | Meaning | Handling |
|---|---|---|
| 401 | Invalid/missing API key | Fatal — don't retry; surface to the operator |
| 403 | Plan doesn't include this endpoint/market | Fatal for that call — don't retry |
| 429 | Rate limit exceeded (5/min on free tier) | Transient — back off, retry on the next poll cycle; don't tighten the interval automatically |
| 5xx | Server error | Transient — the client has built-in retries with backoff; a poll-loop-level catch should still swallow-and-continue so one bad cycle doesn't kill the background task |

Pattern used in this project's poller (`backend/app/market/massive_client.py`): wrap each poll cycle in `try/except Exception`, log, and let the loop retry on the next interval rather than propagating and killing the `asyncio.Task`.

## How FinAlly Uses This API

One background `asyncio` task polls `get_snapshot_all` for the whole watchlist on a fixed interval and writes results into a shared `PriceCache` (see `MARKET_INTERFACE.md`):

```python
import asyncio
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

async def poll_massive(client: RESTClient, get_tickers, price_cache, interval: float = 15.0):
    while True:
        tickers = get_tickers()
        if tickers:
            snapshots = await asyncio.to_thread(
                client.get_snapshot_all,
                market_type=SnapshotMarketType.STOCKS,
                tickers=tickers,
            )
            for snap in snapshots:
                price_cache.update(
                    ticker=snap.ticker,
                    price=snap.last_trade.price,
                    timestamp=snap.last_trade.sip_timestamp / 1_000_000_000,  # ns -> seconds
                )
        await asyncio.sleep(interval)
```

The client is synchronous, so it's always called via `asyncio.to_thread` to avoid blocking the event loop — this matches the existing implementation.

## Corrections vs. the Archived Doc

`planning/archive/MASSIVE_API.md` (an earlier design-phase doc) described the snapshot shape as `day.previous_close`, `day.change`, `day.change_percent`, and `last_trade.timestamp` in Unix **milliseconds**. Based on the actual client source (`massive/rest/models/snapshot.py`, `massive/rest/models/quotes.py`):

1. **Previous close lives on `prev_day.close`**, a separate `Agg` object — not nested under `day`.
2. **Day change is top-level on the snapshot** (`todays_change`, `todays_change_percent`), not nested under `day`.
3. **Trade timestamps use `sip_timestamp`** (nanoseconds since epoch) by the same naming convention as the sibling `LastQuote` model, not a plain `timestamp` field. `backend/app/market/massive_client.py` currently reads `snap.last_trade.timestamp` and `snap.day.previous_close` — **these should be verified against the installed `massive` package** (the existing code defensively catches `AttributeError`/`TypeError` per snapshot and logs+skips, so a field-name mismatch degrades silently to "ticker didn't update this poll" rather than crashing — worth a direct check with the real package rather than relying on mocked tests alone).
4. Unix timestamps from `list_aggs`/`get_previous_close_agg` bars are **milliseconds** (`t` field); `sip_timestamp` on trades/quotes is **nanoseconds**. These are not the same unit — a straight `/1000` division (as used in the current code) is correct for agg bars but likely wrong for `last_trade.sip_timestamp`.

## References

- `massive-com/client-python` README, `docs/source/Getting-Started.rst`, `docs/source/Aggs.rst` (via Context7)
- `massive/rest/snapshot.py`, `massive/rest/aggs.py`, `massive/rest/models/snapshot.py`, `massive/rest/models/trades.py`, `massive/rest/models/quotes.py` (via Context7)
- `backend/app/market/massive_client.py` (this repo's current implementation, used as ground truth for what's already built)
