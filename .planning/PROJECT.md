# FinAlly (AI Trading Workstation)

## What This Is

FinAlly is an AI-powered trading workstation that looks and feels like a modern Bloomberg terminal: it streams live market data, lets a user trade a simulated $10,000 portfolio, and includes an LLM chat copilot that can analyze positions and execute trades on the user's behalf. It ships as a single Docker container (FastAPI + Next.js static export + SQLite) and is the capstone project for an agentic AI coding course.

## Core Value

A user runs one Docker command and immediately has a believable, live-data-driven trading terminal — a watchlist with real-time streaming prices, a simulated portfolio they can trade, and an AI copilot that can analyze and act on it. If the market data isn't both live and credible, nothing else about the "trading terminal" illusion holds.

## Requirements

### Validated

<!-- Shipped and confirmed working — the full MVP described in planning/PLAN.md, verified by a 9/9 Playwright E2E suite against the built Docker image. -->

- ✓ Single Docker container (port 8000): FastAPI serves `/api/*` REST, `/api/stream/*` SSE, and `/*` static files (Next.js export) — v1.0 MVP
- ✓ SQLite database with lazy schema init + seed data (10 default tickers, $10,000 starting cash, no migration step) — v1.0 MVP
- ✓ Live-updating watchlist via SSE (`GET /api/stream/prices`), price-flash animations, client-accumulated sparklines — v1.0 MVP
- ✓ Simulated market data via GBM simulator (correlated sector moves via Cholesky decomposition, random shock events, seed prices/params per ticker) — v1.0 MVP
- ✓ `MarketDataSource` abstract interface, thread-safe `PriceCache`, and provider-selection factory (`create_market_data_source`) implemented for both Simulator and Massive code paths — v1.0 MVP
- ✓ `MassiveDataSource` (Polygon.io REST polling) implemented against the same interface, auto-selected when `MASSIVE_API_KEY` is set and non-empty — v1.0 MVP (code-complete and unit-tested with mocks; never exercised against a live key — see Active)
- ✓ Market data test suite: 73 tests passing, 84% overall coverage across 6 test modules — v1.0 MVP
- ✓ Portfolio REST API: positions, cash balance, unrealized P&L, trade execution (buy/sell, weighted-average cost basis, no short selling, position deleted at zero qty) — v1.0 MVP
- ✓ Watchlist REST API: add/remove tickers (`POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`) — v1.0 MVP
- ✓ Portfolio visualizations: P&L-colored heatmap/treemap, P&L line chart from 30s `portfolio_snapshots`, positions table — v1.0 MVP
- ✓ Trade bar: market orders only, fractional shares, instant fill, no confirmation dialog — v1.0 MVP
- ✓ LLM chat copilot via LiteLLM → OpenRouter (Cerebras inference, `openrouter/openai/gpt-oss-120b`) with structured-output trade/watchlist auto-execution — v1.0 MVP
- ✓ `LLM_MOCK=true` deterministic test mode; graceful `503` from `POST /api/chat` when `OPENROUTER_API_KEY` is unset (app still starts, other features unaffected) — v1.0 MVP
- ✓ Dark terminal-style UI (Next.js + Tailwind), header connection-status dot, docked AI chat panel — v1.0 MVP
- ✓ Multi-stage Dockerfile (Node build → Python/uv runtime), volume-mounted SQLite, idempotent start/stop scripts (macOS/Linux + Windows PowerShell) — v1.0 MVP
- ✓ Playwright E2E suite: 9/9 passing against the built Docker image (fresh start, watchlist CRUD, buy/sell, visualizations, mocked chat, SSE disconnect/reconnect) — v1.0 MVP, **simulator path only**

### Active

<!-- Current milestone: take the already-implemented MassiveDataSource from code-complete to production-verified real market data. -->

- [ ] Obtain and configure a real Massive (Polygon.io) API key; verify authentication succeeds against the live API
- [ ] Validate `MassiveDataSource` correctly parses live snapshot data into `PriceCache` — resolve the self-flagged timestamp field-mapping risk (`last_trade.timestamp` ms vs. `sip_timestamp` ns) against the real response shape, with zero changes required to downstream consumers (`PriceCache`, SSE stream, frontend)
- [ ] Confirm real-data polling respects documented rate-limit tiers (free: 15s/5 req-min; paid: faster) without triggering errors
- [ ] Extend automated test coverage so the real-API response shape is exercised, not just mocked methods (today's `test_massive.py` is 56% coverage, fully mocked, and would not catch field-mapping drift)
- [ ] Document real-data mode as a supported, user-selectable option (README, `.env.example`, `MARKET_DATA_SUMMARY.md` updated to reflect live-key validation)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Switching the Massive integration from REST polling to WebSocket streaming — REST polling was deliberately chosen for simplicity and free-tier viability (MARKET_DATA_DESIGN.md §8); revisit only if polling proves insufficient
- Adding market data providers beyond Massive/Polygon.io — no current need; the `MarketDataSource` interface already supports it later without rework
- Automatic runtime failover between simulator and Massive on auth failure — the shipped design is fail-soft retry-next-poll; only revisit if real-key validation (this milestone) proves that inadequate
- Short selling, limit orders, order book — eliminated by design; market orders only, no short selling (PLAN.md §3/§7)
- Backfilling sparkline/chart history on page load — intentional; sparklines start empty and fill in from the live stream (PLAN.md review notes)
- Trade history UI/endpoint — the `trades` log exists for audit but no UI view is planned for v1 (PLAN.md review notes)
- Terraform/AWS App Runner deployment — optional stretch goal, not core build (PLAN.md §11)

## Context

- Codebase layout: `backend/app/market/` (8 modules: `models.py`, `interface.py`, `cache.py`, `seed_prices.py`, `simulator.py`, `massive_client.py`, `factory.py`, `stream.py`); `backend/tests/market/` (6 test modules, 73 tests); `test/` (Playwright E2E + `docker-compose.test.yml`, currently only exercises the simulator path with `LLM_MOCK=true` and no `MASSIVE_API_KEY`).
- Full market-data design detail lives in `planning/MARKET_DATA_DESIGN.md` (superseded `MARKET_INTERFACE.md`/`MARKET_SIMULATOR.md`/`MASSIVE_API.md`); summary in `planning/MARKET_DATA_SUMMARY.md`.
- Self-flagged risk (MARKET_DATA_DESIGN.md §8.4): `massive_client.py` reads `snap.last_trade.timestamp` as Unix milliseconds, but the installed `massive` package's sibling `LastQuote` model uses `sip_timestamp` in nanoseconds on a different field — the attribute name and/or unit on `LastTrade` may not match the real API. Mismatches are currently swallowed by a per-snapshot `except (AttributeError, TypeError)`, so a drift fails silently (ticker just stops updating) and the fully-mocked test suite does not catch it. The design doc itself recommends one real unmocked poll before enabling in production — this is the central risk this milestone exists to close.
- Known issues noted during intel ingest, not in scope for this milestone but worth tracking: (1) three uncoordinated automations (`Stop` hook, `PostToolUse` plugin hook, `change-reviewer` subagent) all write `planning/REVIEW.md` with no locking/dedupe, risking clobbered output or a self-triggering loop; (2) `planning/MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md` exist as untracked root-level rewrites duplicating files already in `planning/archive/`, with no cross-reference describing which is canonical; (3) stray root-level `package.json`/`package-lock.json` (empty, looks like an accidental `npm install` outside any project) and `README_OLD.md` (likely an intentional pre-commit backup) should be cleaned up or gitignored.
- `prev_day.close`/`todays_change`/`todays_change_percent` fields are available from the Massive snapshot response and documented for a future day-change feature, but not currently consumed — noted for awareness, not in this milestone's scope.

## Constraints

- **Tech stack (locked)**: Single Docker container, FastAPI + `uv` backend, Next.js static-export frontend, SQLite on a mounted volume. Changing this architecture requires explicit discussion — it's the foundation the whole MVP (and this milestone) builds on.
- **Provider selection is env-var-only**: `create_market_data_source(price_cache)` is the single switch point — `MASSIVE_API_KEY` set and non-empty (stripped) → `MassiveDataSource`, otherwise → `SimulatorDataSource`. No other code should branch on this env var; this milestone must not introduce a second switch point.
- **Interface contract must not change**: `MarketDataSource` ABC (`start`/`stop`/`add_ticker`/`remove_ticker`/`get_tickers`) and `PriceCache` are the only coupling points between market data and the rest of the app (SSE stream, frontend). Any fix made while validating the real-data path must preserve this — downstream code should require zero changes.
- **Rate-limit tiers (documented, not yet live-verified)**: Free tier = 5 req/min → 15.0s poll interval default, one request per poll regardless of watchlist size (`get_snapshot_all`). Paid tiers support faster polling (2-15s) via the existing `poll_interval` constructor param.
- **Threading model**: `PriceCache` uses `threading.Lock` (not `asyncio.Lock`) specifically because `MassiveDataSource` writes from a worker thread via `asyncio.to_thread` as well as from the event loop — do not "simplify" this to an asyncio lock.
- **Fail-soft error handling is intentional**: per-snapshot (`AttributeError`/`TypeError`) and per-poll-cycle (`Exception`) failures are logged and skipped/retried, not raised. Any fix to the field-mapping bug should correct the mapping, not remove this resilience pattern — 401/403 are documented as fatal but today are not specially short-circuited from transient errors like 429/5xx; this milestone should clarify whether that's acceptable.
- **No `.env` secrets committed**: `.env` is gitignored; `.env.example` is committed and documents variables without real values. Any real `MASSIVE_API_KEY` obtained for validation stays local/out of version control.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| REST polling (not WebSocket) for Massive | Works on Polygon.io's free tier; simpler than managing a persistent WS connection | ✓ Good |
| Provider selection via env var alone, no runtime toggle | Zero-config simplicity matches the single-user, no-auth philosophy | ✓ Good |
| Fail-soft per-snapshot/per-poll error handling | Avoid crashing the app on transient API issues (429, network blips) | ⚠️ Revisit — may be masking the field-mapping bug this milestone needs to surface |
| `threading.Lock` (not `asyncio.Lock`) in `PriceCache` | `MassiveDataSource` writes from a worker thread via `asyncio.to_thread` | ✓ Good |
| Mocked `RESTClient` in `test_massive.py` (56% coverage) | Kept the v1.0 test suite fast/free/offline | ⚠️ Revisit — this milestone exists specifically because mocking hid a real-shape risk |

---
*Last updated: 2026-10-27 after initial roadmap creation (brownfield ingest, real-market-data milestone)*
