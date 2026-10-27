# Requirements: FinAlly (AI Trading Workstation)

**Defined:** 2026-10-27
**Core Value:** A user runs one Docker command and immediately has a believable, live-data-driven trading terminal — a watchlist with real-time streaming prices, a simulated portfolio they can trade, and an AI copilot that can analyze and act on it.

> **Note on scope:** FinAlly's v1.0 MVP (market data simulator, portfolio/watchlist/trade REST API, LLM chat via Cerebras/OpenRouter structured output, Next.js frontend, Docker packaging, Playwright E2E suite) is already built, unit-tested, and passing a 9/9 E2E suite. Those shipped requirements are recorded in `.planning/PROJECT.md` under **Requirements → Validated** and are not re-listed here. The requirements below are scoped to the current milestone only: validating and documenting the already-implemented-but-never-live-tested Massive (Polygon.io) real-market-data path.

## v1 Requirements

Requirements for the current milestone. Each maps to a roadmap phase.

### Massive API Integration (MASSIVE)

- [ ] **MASSIVE-01**: Developer has a working Massive (Polygon.io) API key configured locally in `.env`, and the backend authenticates successfully against the live API (no 401/403 on startup or first poll)
- [ ] **MASSIVE-02**: `MassiveDataSource` correctly parses live snapshot data into `PriceCache` — the self-flagged `last_trade.timestamp`/`sip_timestamp` field-mapping risk (MARKET_DATA_DESIGN.md §8.4) is confirmed correct or fixed against the real API response shape
- [ ] **MASSIVE-03**: Real-data polling respects the documented rate-limit tiers (free tier: 15s interval / 5 req-min ceiling; paid tier: configurable faster interval) without triggering 429 responses under normal watchlist sizes during a sustained run
- [ ] **MASSIVE-04**: Price updates sourced from Massive flow through the existing SSE (`/api/stream/prices`) pipeline to the frontend with zero code changes required to `PriceCache`, `stream.py`, or frontend consumers
- [ ] **MASSIVE-05**: Auth failure behavior (401/403) is verified against the real API and confirmed as either correctly fatal/short-circuited or explicitly accepted as fail-soft-retry, resolving the ambiguity noted in MARKET_DATA_DESIGN.md §8

### Real-Data Test Coverage (TEST)

- [ ] **TEST-01**: An integration test (fixture-based on a captured real response, or opt-in live-gated) verifies the corrected field mapping against a realistic Massive snapshot shape — replacing/augmenting the fully-mocked `test_massive.py`
- [ ] **TEST-02**: The test suite catches a simulated field-mapping drift (e.g., a renamed/retyped attribute) as a visible failure rather than a silent per-ticker skip, raising `test_massive.py` coverage meaningfully above the current 56%

### Documentation & Rollout (DOCS)

- [ ] **DOCS-01**: README.md and/or `.env.example` document how to obtain a Massive/Polygon.io API key and enable real-data mode, including free-vs-paid rate-limit tier guidance and the `poll_interval` tradeoff
- [ ] **DOCS-02**: `planning/MARKET_DATA_SUMMARY.md` is updated to reflect that the Massive real-data path has been validated against a live key (status changed from "implemented, mock-tested" to "validated against live API")

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Market Data Expansion

- **EXPAND-01**: Support additional market data providers beyond Massive/Polygon.io
- **EXPAND-02**: Switch (or add) a WebSocket-based real-time feed from Massive instead of REST polling
- **EXPAND-03**: Automatic runtime failover between simulator and Massive on sustained auth/API failure
- **EXPAND-04**: Consume `prev_day.close`/`todays_change`/`todays_change_percent` from the Massive snapshot for a day-change UI feature

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| WebSocket migration for Massive | REST polling deliberately chosen for simplicity and free-tier viability (MARKET_DATA_DESIGN.md §8) |
| Additional market data providers | No current need; interface already supports it later without rework |
| Automatic simulator/Massive failover | Shipped fail-soft retry-next-poll design is accepted unless this milestone's validation proves it inadequate |
| Short selling, limit orders, order book | Eliminated by design — market orders only, no short selling (PLAN.md §3/§7) |
| Sparkline/chart history backfill on page load | Intentional — sparklines start empty and fill from the live stream |
| Trade history UI/endpoint | `trades` log exists for audit only; no UI view planned for v1 |
| Terraform/AWS App Runner deployment | Optional stretch goal, not core build (PLAN.md §11) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MASSIVE-01 | Phase 1 | Pending |
| MASSIVE-02 | Phase 2 | Pending |
| MASSIVE-03 | Phase 2 | Pending |
| MASSIVE-04 | Phase 2 | Pending |
| MASSIVE-05 | Phase 2 | Pending |
| TEST-01 | Phase 3 | Pending |
| TEST-02 | Phase 3 | Pending |
| DOCS-01 | Phase 4 | Pending |
| DOCS-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-27*
*Last updated: 2026-10-27 after initial roadmap creation*
