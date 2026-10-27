# Roadmap: FinAlly (AI Trading Workstation)

## Overview

The core trading workstation already ships end-to-end and passes a 9/9 Playwright E2E suite against the built Docker image — live simulated prices, portfolio trading, visualizations, and AI chat all work today using the GBM market simulator. This roadmap scopes the next milestone only: taking the already-implemented but never-live-tested `MassiveDataSource` (Polygon.io real market data) from code-complete to production-verified. The journey runs from obtaining and authenticating a real API key, through validating the data actually flowing correctly (and closing the self-flagged timestamp field-mapping risk), to hardening automated test coverage for that path, to documenting it as a supported, user-selectable mode.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Massive API Key Setup & Auth Verification** - Obtain a real Massive/Polygon.io API key and confirm the backend authenticates successfully against the live API
- [ ] **Phase 2: Real-Data Polling Validation & Field-Mapping Fix** - Confirm live snapshot data flows correctly into PriceCache/SSE, close the self-flagged timestamp mapping risk, and verify rate-limit behavior
- [ ] **Phase 3: Real-Data Test Coverage** - Replace/augment the fully-mocked Massive test suite so real-response-shape regressions are caught automatically
- [ ] **Phase 4: Documentation & Rollout** - Document real-data mode as a supported, user-selectable option

## Phase Details

### Phase 1: Massive API Key Setup & Auth Verification
**Goal**: A real Massive (Polygon.io) API key is obtained, configured, and verified to authenticate successfully against the live API — the prerequisite for everything else in this milestone.
**Depends on**: Nothing (first phase)
**Requirements**: MASSIVE-01
**Success Criteria** (what must be TRUE):
  1. A valid `MASSIVE_API_KEY` is present in a local `.env` (not committed) and the backend starts cleanly with it set
  2. A real, unmocked call to the Massive API (e.g. `get_snapshot_all` for the default watchlist) succeeds and returns live data — satisfying MARKET_DATA_DESIGN.md §8.4's explicit recommendation to run one real poll before enabling in production
  3. An intentionally invalid/revoked key produces a clear, logged auth error rather than a silent hang, infinite retry storm, or crash
**Plans**: TBD

### Phase 2: Real-Data Polling Validation & Field-Mapping Fix
**Goal**: `MassiveDataSource` correctly parses live snapshot data into `PriceCache` with accurate prices and timestamps, respects documented rate limits, and requires zero changes to downstream consumers.
**Depends on**: Phase 1
**Requirements**: MASSIVE-02, MASSIVE-03, MASSIVE-04, MASSIVE-05
**Success Criteria** (what must be TRUE):
  1. With `MASSIVE_API_KEY` set, running the backend updates `PriceCache` with live prices for the default watchlist, observable via `GET /api/stream/prices`
  2. The price/timestamp field-mapping bug flagged in MARKET_DATA_DESIGN.md §8.4 (`last_trade.timestamp` ms vs. `sip_timestamp` ns) is confirmed correct or fixed against the real response shape — tickers no longer silently stop updating due to a swallowed `AttributeError`/`TypeError`
  3. A sustained run at the configured poll interval (15s default/free tier) completes without triggering 429 responses
  4. SSE clients receive correctly-updated prices sourced from Massive with no code changes to `PriceCache`, `stream.py`, or the frontend
  5. Auth failure (401/403) behavior is verified against the real API and the ambiguity in MARKET_DATA_DESIGN.md §8 (fatal vs. fail-soft) is explicitly resolved
**Plans**: TBD

### Phase 3: Real-Data Test Coverage
**Goal**: Automated tests catch regressions in the real Massive integration — not just a mocked happy path that already failed to surface the field-mapping risk.
**Depends on**: Phase 2
**Requirements**: TEST-01, TEST-02
**Success Criteria** (what must be TRUE):
  1. A test (fixture-based on a captured real response, or opt-in live-gated) verifies the corrected field mapping against a realistic Massive snapshot shape
  2. Running the test suite with a simulated field-mapping drift (e.g., a renamed/retyped attribute) produces a visible test failure rather than a silent per-ticker skip
  3. `test_massive.py` coverage increases meaningfully above the current 56%, driven by representative real response data rather than loosely mocked methods
**Plans**: TBD

### Phase 4: Documentation & Rollout
**Goal**: A developer can enable real market data mode confidently by reading documentation alone, without inspecting source code.
**Depends on**: Phase 3
**Requirements**: DOCS-01, DOCS-02
**Success Criteria** (what must be TRUE):
  1. README.md and/or `.env.example` explain how to obtain a Massive/Polygon.io API key, and what free-vs-paid rate-limit tradeoffs to expect
  2. `planning/MARKET_DATA_SUMMARY.md` reflects that the real-data path has been validated against a live key (status updated from "implemented, mock-tested" to "validated against live API")
  3. Setting `MASSIVE_API_KEY` in `.env` is documented and confirmed as the only step needed to switch modes — no other configuration required
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Massive API Key Setup & Auth Verification | 0/TBD | Not started | - |
| 2. Real-Data Polling Validation & Field-Mapping Fix | 0/TBD | Not started | - |
| 3. Real-Data Test Coverage | 0/TBD | Not started | - |
| 4. Documentation & Rollout | 0/TBD | Not started | - |
