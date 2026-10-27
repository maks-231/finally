# Phase 1: Massive API Key Setup & Auth Verification - Context

**Gathered:** 2026-10-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Obtain a real Massive (Polygon.io) API key, configure it locally in `.env`, and verify it authenticates successfully against the live API. This phase proves the prerequisite for everything else in the milestone — it does NOT fix the field-mapping risk (Phase 2 / MASSIVE-02), does NOT build permanent test coverage (Phase 3), and does NOT resolve the fatal-vs-fail-soft auth-error design ambiguity (Phase 2 / MASSIVE-05) — it only verifies and documents current behavior against a real key and a real invalid key.

</domain>

<decisions>
## Implementation Decisions

### Key Acquisition
- **D-01:** The user does not yet have a Massive/Polygon.io API key. The plan must start with an explicit, non-autonomous checkpoint task: user signs up at polygon.io/Massive, obtains a **free-tier** key, pastes it into local `.env` as `MASSIVE_API_KEY`, then confirms before the agent proceeds.
- **D-02:** Free tier only for this milestone (5 req/min, 15s poll interval) — matches the existing hardcoded default in `factory.py` (no `poll_interval` override needed). Paid tier is explicitly out of scope; do not add tier-configuration work in this phase.
- **D-03:** Execution must pause at the key-acquisition task (mark it non-autonomous / a manual checkpoint) rather than assuming the key will materialize mid-run.

### Verification Method (Success Criterion #2 — live auth succeeds)
- **D-04:** Verify by running the real backend locally (`uv run ...` / however the backend is normally started — NOT inside Docker, and NOT a disposable script bypassing the app). Set `MASSIVE_API_KEY` in `.env`, start the app, hit `GET /api/stream/prices`, and confirm live prices actually update in `PriceCache` through the real startup + polling path. This exercises success criterion #1 ("backend starts cleanly") at the same time.
- **D-05:** Explicitly do NOT add new pytest tests or permanent test infrastructure for this verification — that overlaps with Phase 3's scope (TEST-01/TEST-02). This is a one-time manual/scripted verification, not a committed test.
- **D-06:** While the real backend is running, capture one raw example of the live `TickerSnapshot` response (e.g., a debug log line or a saved JSON snippet of `snap.last_trade` / `snap.last_quote` attribute names and values) and record it in the plan's output/verification notes. This is evidence handed to Phase 2 for the field-mapping risk (MARKET_DATA_DESIGN.md §8.4) — Phase 1 must NOT modify `massive_client.py` to fix the mapping itself, only observe and record.

### Invalid-Key Test (Success Criterion #3 — auth failure behavior)
- **D-07:** Trigger the failure by setting `MASSIVE_API_KEY` to a deliberately garbage/malformed string — do NOT use a real key and revoke it via the Polygon.io dashboard. Garbage string is faster, fully repeatable, and requires no account/dashboard round-trips.
- **D-08:** Run the real backend with the garbage key and confirm: (a) no crash, (b) no hang, (c) no tight/runaway retry loop (retries stay gated by the existing 15s `poll_interval`), and (d) the logged error clearly reflects an auth failure (e.g., a 401/403 status or "Unauthorized"-type message is visible in the log line).
- **D-09:** **Acceptance bar is explicitly lenient by design:** the current implementation's fail-soft-forever-retry behavior on auth errors (generic `except Exception` in `_poll_once`, no special 401/403 short-circuit) is an ACCEPTABLE PASS for this phase's success criterion #3. Phase 1 does not need to add fatal/short-circuit handling — that specific fatal-vs-fail-soft decision is Phase 2's explicit job (MASSIVE-05, per MARKET_DATA_DESIGN.md §8.5's documented-but-unimplemented "401/403 should be fatal" guidance). Phase 1's job is only to observe and document the current behavior clearly enough that Phase 2 has real evidence to decide.

### Claude's Discretion
- Exact mechanism for capturing the sample snapshot (log line vs. saved file) — pick whichever is lowest-friction given the verification approach chosen (D-04).
- Exact wording/location of the verification output/write-up (e.g., a short markdown note in the phase dir) — plan should produce *some* durable record of what was observed (both the live-success case and the invalid-key case), since Phase 2 and Phase 4 depend on these findings.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Market Data Design
- `planning/MARKET_DATA_DESIGN.md` §8 (Massive API section) — auth, rate limits, `get_snapshot_all` endpoint, `MassiveDataSource` as implemented, and the self-flagged field-mapping risk (§8.4)
- `planning/MARKET_DATA_DESIGN.md` §8.5 — documented error-handling table (401/403 = fatal per design doc, but NOT implemented that way in code today — this gap is explicitly Phase 2's to resolve, not Phase 1's)
- `planning/MARKET_DATA_SUMMARY.md` — summary status of the market data component

### Project Context
- `.planning/PROJECT.md` — Constraints section (env-var-only provider selection, fail-soft error handling is intentional, no `.env` secrets committed), Key Decisions table
- `.planning/REQUIREMENTS.md` — MASSIVE-01 (this phase) through MASSIVE-05 (Phase 2), to keep phase boundaries clear
- `.planning/ROADMAP.md` — Phase 1 success criteria (verbatim source of the 3 criteria referenced throughout this document)

### Source Files
- `backend/app/market/massive_client.py` — the implementation being verified (read-only for this phase; do not modify)
- `backend/app/market/factory.py` — provider-selection switch point (`MASSIVE_API_KEY` env var check)
- `.env.example` — documents `MASSIVE_API_KEY` as optional; real value stays in local `.env` only

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_market_data_source(price_cache)` in `factory.py` already auto-selects `MassiveDataSource` when `MASSIVE_API_KEY` is set and non-empty — no code changes needed to switch modes, only the env var.
- `GET /api/stream/prices` (SSE) already consumes `PriceCache` regardless of which source populated it — the existing endpoint is the verification surface for "live prices flow through."

### Established Patterns
- Fail-soft error handling is a deliberate, documented pattern in this codebase (`PROJECT.md` Constraints) — per-snapshot errors caught by `(AttributeError, TypeError)`, per-poll-cycle errors caught by generic `Exception`, both logged and retried rather than raised. This phase verifies behavior against this existing pattern; it does not change it.
- `.env` is gitignored, `.env.example` is committed without real values — any real key obtained for this phase must stay local only.

### Integration Points
- `MassiveDataSource.start(tickers)` does an immediate first poll before entering the polling loop — this is the fastest observable point for both the success case (D-04) and the failure case (D-07/D-08): a single run-and-observe cycle, no need to wait a full poll interval for the first signal.

</code_context>

<specifics>
## Specific Ideas

- Verification must happen against the real, running backend (not an isolated script against the Massive client library) — the user explicitly wants success criterion #1 ("backend starts cleanly") proven as a side effect of the same run.
- The captured sample snapshot (D-06) should be treated as a handoff artifact for Phase 2, not thrown away after Phase 1 closes.

</specifics>

<deferred>
## Deferred Ideas

- Paid-tier signup and configurable `poll_interval` — explicitly deferred; free tier only for this milestone (D-02).
- Fixing the `last_trade.timestamp`/`sip_timestamp` field-mapping risk — Phase 2 (MASSIVE-02).
- Resolving fatal-vs-fail-soft auth error handling — Phase 2 (MASSIVE-05).
- Adding permanent/committed test coverage for the real-API response shape — Phase 3 (TEST-01/TEST-02).

None — discussion stayed within phase scope beyond the above, which are already scoped to later phases in the roadmap.

</deferred>

---

*Phase: 1-massive-api-key-setup-auth-verification*
*Context gathered: 2026-10-27*
