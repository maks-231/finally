# Constraints (from SPEC documents)

Two documents classified as `SPEC`: `planning/PLAN.md` and `planning/MARKET_DATA_DESIGN.md`. Both sit at the same default precedence tier (SPEC); neither carries a per-doc `precedence` override. `MARKET_DATA_DESIGN.md` is the as-implemented design for the market data subsystem that `PLAN.md` §6 specifies at a higher level — they describe the same subsystem at different altitudes and were checked for contradiction (see `INGEST-CONFLICTS.md`). One factual discrepancy was found against a lower-precedence DOC and auto-resolved in SPEC's favor (see conflicts report); no SPEC-vs-SPEC contradictions were found.

---

## From `planning/PLAN.md`

### 1. Single-container architecture
- **source**: planning/PLAN.md §3
- **type**: nfr
- One Docker container, one port (8000). FastAPI serves `/api/*` REST, `/api/stream/*` SSE, and `/*` static files (Next.js export). SQLite volume-mounted at `db/finally.db`. Background task performs market data polling/simulation in-process.

### 2. Technology stack selection
- **source**: planning/PLAN.md §3 ("Why These Choices" table)
- **type**: nfr
- SSE over WebSockets (one-way push sufficiency, simplicity, universal browser support); static Next.js export (single origin, no CORS, one port/container); SQLite over Postgres (no auth/multi-user, zero-config); single Docker container (no docker-compose in production); `uv` for Python dependency management; market orders only (eliminates order book / limit order / partial-fill complexity).

### 3. Environment variable behavior
- **source**: planning/PLAN.md §5
- **type**: nfr
- `OPENROUTER_API_KEY` (required for chat) — if absent and `LLM_MOCK` is not `"true"`, backend still starts normally; `POST /api/chat` returns 503 with a clear error instead of crashing.
- `MASSIVE_API_KEY` (optional) — set+non-empty → Massive REST API market data; absent/empty → built-in simulator.
- `LLM_MOCK` (optional, default false) — `"true"` → deterministic mock LLM responses for testing.
- `.env` is read from the project root, gitignored, with `.env.example` committed.

### 4. Database schema
- **source**: planning/PLAN.md §7
- **type**: schema
- Tables: `users_profile` (id, cash_balance default 10000.0, created_at), `watchlist` (id, user_id, ticker, added_at, UNIQUE(user_id, ticker)), `positions` (id, user_id, ticker, quantity REAL, avg_cost, updated_at, UNIQUE(user_id, ticker)), `trades` (append-only log: id, user_id, ticker, side, quantity, price, executed_at), `portfolio_snapshots` (id, user_id, total_value, recorded_at — written every 30s by a dedicated asyncio task plus immediately after each trade), `chat_messages` (id, user_id, role, content, actions JSON, created_at). All tables carry `user_id` defaulting to `"default"` for future multi-user support. SQLite is lazily initialized (no migration step) — schema + seed created on first run if missing.
- Seed data: one user profile (`cash_balance=10000.0`); ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX.

### 5. Trade execution rules
- **source**: planning/PLAN.md §7
- **type**: protocol
- **Buy**: rejected if `quantity * price > cash_balance`. On success, `avg_cost` recalculated as weighted average: `new_avg_cost = (old_avg_cost * old_qty + price * trade_qty) / (old_qty + trade_qty)`; new position row created with `avg_cost = price` if none exists.
- **Sell**: rejected if `quantity > current position quantity` (no short selling). `avg_cost` unchanged by sells. Position row deleted (not zeroed) when quantity reaches exactly 0.
- These rules apply identically to manual trades and LLM-initiated trades.

### 6. REST + SSE API endpoints
- **source**: planning/PLAN.md §8
- **type**: api-contract
- Market data: `GET /api/stream/prices` (SSE).
- Portfolio: `GET /api/portfolio`, `POST /api/portfolio/trade` (`{ticker, quantity, side}`), `GET /api/portfolio/history`.
- Watchlist: `GET /api/watchlist`, `POST /api/watchlist` (`{ticker}`), `DELETE /api/watchlist/{ticker}`.
- Chat: `GET /api/chat` (persisted history), `POST /api/chat` (send message, complete JSON response).
- System: `GET /api/health`.

### 7. LLM integration & structured output schema
- **source**: planning/PLAN.md §9
- **type**: protocol
- Flow: load portfolio context (cash, positions+P&L, watchlist+live prices, total value) → load last 20 `chat_messages` rows (10 turns, fixed window) → build prompt (system + context + history + new message) → call LiteLLM → OpenRouter (`openrouter/openai/gpt-oss-120b` via Cerebras inference, per cerebras-inference skill) requesting structured output → parse JSON → auto-execute any `trades`/`watchlist_changes` (validated identically to manual operations, §7) → persist message + executed actions to `chat_messages` → return full JSON to frontend (no token streaming; loading indicator only).
- Schema: `{"message": str, "trades": [{"ticker","side","quantity"}]?, "watchlist_changes": [{"ticker","action": "add"|"remove"}]?}`.
- Trades auto-execute with no confirmation dialog (deliberate: simulated money, demo fluidity, demonstrates agentic capability). Validation failures are surfaced back into the chat response text, not silently dropped.
- `LLM_MOCK=true` → deterministic mock responses, no OpenRouter call.

### 8. Frontend UI requirements
- **source**: planning/PLAN.md §2, §10
- **type**: nfr
- Required elements: watchlist panel (price flash green/red, sparklines accumulated client-side from SSE since page load — no backfill), main chart area (click-to-select from watchlist), portfolio heatmap/treemap (sized by weight, colored by P&L), P&L line chart (from `portfolio_snapshots`), positions table (ticker/qty/avg cost/current price/unrealized P&L/% change), trade bar (ticker, decimal-capable quantity field, buy/sell buttons, instant market-order fill, no confirmation), AI chat panel (docked/collapsible, loading indicator, inline trade/watchlist-change confirmations), header (live total value, connection status dot: green/yellow/red, cash balance).
- Dark theme (`#0d1117`/`#1a1a2e` range, no pure black), accent colors Yellow `#ecad0a`, Blue `#209dd7`, Purple `#753991` (submit buttons). Desktop-first, tablet-functional.
- `EventSource` for SSE; canvas-based charting (Lightweight Charts or Recharts preferred); all API calls same-origin (`/api/*`, no CORS); Tailwind CSS.

### 9. Docker & deployment
- **source**: planning/PLAN.md §11
- **type**: nfr
- Multi-stage Dockerfile: Stage 1 Node 20 slim builds the static Next.js export; Stage 2 Python 3.12 slim + `uv sync`, copies frontend build into `static/`, exposes port 8000, runs `uvicorn`. Named Docker volume persists `db/finally.db` (`-v finally-data:/app/db -p 8000:8000 --env-file .env`). Idempotent `start_mac.sh`/`stop_mac.sh` + PowerShell equivalents (stop does not remove the volume). Optional stretch goal: Terraform for AWS App Runner deploy.

### 10. Testing strategy
- **source**: planning/PLAN.md §12
- **type**: nfr
- Backend (pytest): market data (simulator validity/GBM math, Massive parsing, interface conformance), portfolio (trade execution, P&L, edge cases), LLM (structured output parsing, malformed-response handling, in-chat trade validation), API routes (status codes, shapes, errors).
- Frontend (RTL or similar): rendering, price-flash trigger, watchlist CRUD, portfolio display math, chat rendering/loading state.
- E2E (Playwright, in `test/`, separate `docker-compose.test.yml` to keep browser deps out of prod image, `LLM_MOCK=true` by default): fresh-start defaults, watchlist add/remove, buy/sell flows, heatmap/P&L chart rendering, mocked AI chat with inline trade execution, SSE disconnect/reconnect resilience.

---

## From `planning/MARKET_DATA_DESIGN.md`

> This document states it "consolidates and supersedes" `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md`, and `planning/archive/MARKET_DATA_DESIGN.md` — none of those four were present in this ingest batch, so no content comparison against them was possible. See `INGEST-CONFLICTS.md` for the related doc-hygiene note sourced from `REVIEW.md`.

### 1. MarketDataSource interface contract
- **source**: planning/MARKET_DATA_DESIGN.md §3
- **type**: api-contract
- Abstract base class with `async start(tickers: list[str])`, `async stop()`, `async add_ticker(ticker)`, `async remove_ticker(ticker)`, `get_tickers() -> list[str]`. Deliberately has no price-returning method — both implementations push into a shared cache on their own cadence (simulator 500ms, Massive 2-15s) and callers always read from the cache, decoupling source refresh rate from consumer read rate.

### 2. PriceCache behavior & threading model
- **source**: planning/MARKET_DATA_DESIGN.md §4
- **type**: protocol
- Thread-safe in-memory store (`threading.Lock`, not `asyncio.Lock` — required because `MassiveDataSource` writes from a worker thread via `asyncio.to_thread` as well as from the event loop). API: `update(ticker, price, timestamp=None)`, `get(ticker)`, `get_all()`, `get_price(ticker)`, `remove(ticker)`, `version` (monotonic counter bumped on every update, used by SSE for cheap change detection instead of dict diffing).

### 3. Provider selection factory
- **source**: planning/MARKET_DATA_DESIGN.md §5
- **type**: nfr
- `create_market_data_source(price_cache)` is the single switch point: `MASSIVE_API_KEY` set and non-empty (stripped) → `MassiveDataSource`; otherwise → `SimulatorDataSource`. No other code branches on this env var. Returns an unstarted source; caller must `await source.start(tickers)`.

### 4. GBM simulator math & tuning parameters
- **source**: planning/MARKET_DATA_DESIGN.md §6
- **type**: protocol
- Geometric Brownian Motion: `S(t+dt) = S(t) * exp((mu - sigma^2/2)*dt + sigma*sqrt(dt)*Z)`. `DEFAULT_DT = 0.5 / (252*6.5*3600) ≈ 8.48e-8` (500ms ticks over a 252-day/6.5hr trading year). Correlated moves via Cholesky decomposition of a sector-based correlation matrix: tech group (`AAPL,GOOGL,MSFT,AMZN,META,NVDA,NFLX`) intra-correlation 0.6, finance group (`JPM,V`) intra-correlation 0.5, cross-group/unknown-ticker baseline 0.3, TSLA fixed at 0.3 against any other ticker (checked first, even though TSLA has no explicit group). Seed prices and per-ticker `(sigma, mu)` in `seed_prices.py` (e.g. AAPL $190/σ0.22/μ0.05, TSLA $250/σ0.50/μ0.03, NVDA $800/σ0.40/μ0.08). Runtime-added tickers not in `SEED_PRICES` start at a random price in `$50-$300` with default params `(sigma=0.25, mu=0.05)`. Random shock events: ~0.1% probability per ticker per tick of a 2-5% jump (sign random), independent of the correlated diffusion term. Prices cannot go negative (multiplicative `exp()` update). Rounding to 2 decimals happens only on the externally-returned value, not fed back into internal state (prevents compounding rounding error).

### 5. SSE streaming implementation
- **source**: planning/MARKET_DATA_DESIGN.md §7
- **type**: api-contract
- `GET /api/stream/prices`, `StreamingResponse` with `text/event-stream`, headers `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`. Emits `retry: 1000\n\n` first (tells `EventSource` to auto-reconnect after 1s on drop). Each connected client's generator polls `price_cache.version` every 0.5s and only serializes+sends `price_cache.get_all()` (as `{ticker: update.to_dict()}`) when the version changed since last check — keeps the idle hot path to an integer comparison. Generator exits cleanly on `request.is_disconnected()` or `asyncio.CancelledError`.

### 6. Massive API integration & known field-mapping risk
- **source**: planning/MARKET_DATA_DESIGN.md §8
- **type**: protocol
- Uses `massive` package's synchronous `RESTClient.get_snapshot_all(market_type=SnapshotMarketType.STOCKS, tickers=[...])` — one HTTP call for the whole watchlist (what makes free-tier polling viable: 5 req/min limit, default poll interval 15.0s, always exactly one request per poll regardless of watchlist size). Calls offloaded via `asyncio.to_thread`. Fail-soft per-snapshot (`AttributeError`/`TypeError` on a single ticker logged and skipped) and fail-soft per poll cycle (outer `except Exception` logs and retries next interval; 429/5xx are treated as transient this way; 401/403 are documented as fatal but not specially short-circuited in the shown code). `add_ticker`/`remove_ticker` are eventually consistent — new tickers get no price until the next scheduled poll (up to `poll_interval` seconds later), unlike the simulator which seeds immediately.
- **Flagged risk (self-reported by the source document, §8.4):** the code reads `snap.last_trade.timestamp` as Unix milliseconds, but the sibling `LastQuote` model in the installed `massive` package uses `sip_timestamp` in nanoseconds — the field name and/or unit on `LastTrade` may not match the real API response. Because mismatches are swallowed by the per-snapshot `except (AttributeError, TypeError)`, a drift would fail silently (affected ticker just stops updating) and the existing test suite (mocked `RESTClient`) would not catch it. Document explicitly recommends running one real unmocked poll against the live API before enabling `MASSIVE_API_KEY` in production to verify attribute names/units. Also notes `prev_day.close`/`todays_change`/`todays_change_percent` are documented for a future day-change feature but not currently consumed.

### 7. Market data lifecycle sequence
- **source**: planning/MARKET_DATA_DESIGN.md §9
- **type**: protocol
- Startup: `price_cache = PriceCache()` → `source = create_market_data_source(price_cache)` → `await source.start(initial_tickers)` → `app.include_router(create_stream_router(price_cache))`. Watchlist changes: `await source.add_ticker(...)` / `await source.remove_ticker(...)`. Shutdown: `await source.stop()`.

### 8. Market data test suite coverage
- **source**: planning/MARKET_DATA_DESIGN.md §10
- **type**: nfr
- 73 tests, all passing, 84% overall coverage across 6 test modules: `test_models.py` (11, models.py 100%), `test_cache.py` (13, cache.py 100%), `test_simulator.py` (17, simulator.py 98%), `test_simulator_source.py` (10, integration), `test_factory.py` (7, factory.py 100%), `test_massive.py` (13, massive_client.py 56% — API methods mocked, which the document identifies as the direct cause of the field-mapping risk in constraint 6 above never being caught by tests).
