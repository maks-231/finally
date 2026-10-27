# Phase 2: Real-Data Polling Validation & Field-Mapping Fix - Context

**Gathered:** 2026-10-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Confirm `MassiveDataSource` correctly parses live snapshot data into `PriceCache` with accurate prices and timestamps, respects documented rate limits, and requires zero changes to downstream consumers (`PriceCache`, `stream.py`, frontend). This phase also resolves the fatal-vs-fail-soft auth-error ambiguity explicitly deferred from Phase 1 (MASSIVE-05). It does NOT build permanent test coverage (Phase 3) and does NOT update rollout documentation (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Auth Failure Resolution (MASSIVE-05)
- **D-01:** Implement a **circuit breaker**, not a fully fatal short-circuit and not the current fail-soft-forever-retry. This is a deliberate middle ground between MARKET_DATA_DESIGN.md §8.5's documented "401/403 = fatal" and today's generic `except Exception` behavior.
- **D-02:** Trip threshold is **1** — a single 401/403 response immediately stops the poll loop's auto-retry. Auth errors are deterministic (same bad key → same result every time), so there's no value in tolerating repeats before acting.
- **D-03:** Surface the tripped state via a **CRITICAL-level log line only** (e.g. "Massive auth failed — polling stopped, check MASSIVE_API_KEY"). No new `/api/health` field or other API surface — stays consistent with the zero-config, single-user philosophy (`.planning/PROJECT.md` Constraints).
- **D-04:** Once tripped, the breaker **stays stopped for the life of the process** — no auto-retry/cooldown. An invalid key requires the operator to fix `.env` and restart; this matches the existing env-var-only, no-runtime-toggle provider-selection design.
- **D-05:** This directly resolves MASSIVE-05's ambiguity. Implementation touches `_poll_once`'s exception handling in `massive_client.py` — needs to distinguish a 401/403 response from other exception types (network errors, 429, 5xx) rather than catching everything identically. Research/planning should confirm how the `massive` package surfaces HTTP status on error (exception type or attribute) before writing the distinguishing logic.

### Field-Mapping Fix Scope (MASSIVE-02)
- **D-06:** Apply a **minimal, targeted patch** — fix exactly the field/unit confirmed wrong against the real response (e.g. correct attribute name and/or ms→s vs ns→s conversion for the timestamp). Do NOT build a defensive multi-field fallback chain (`last_trade.timestamp` OR `sip_timestamp` OR ...) — smallest diff, matches the project's no-speculative-abstraction convention, and is fully verifiable against the one real sample this phase captures.
- **D-07:** In the same live-verification pass, **also confirm `snap.last_trade.price`'s real attribute name/type** — not just the self-flagged timestamp risk. Near-zero extra cost since the real snapshot is already being inspected; closes out MASSIVE-02's full stated scope ("correctly parses live snapshot data," not just the timestamp half).
- **D-08:** Keep the existing per-snapshot `except (AttributeError, TypeError)` safety net exactly as-is after the fix. It remains useful defense against a genuinely malformed individual snapshot (e.g., a halted/delisted ticker with missing fields) — a different failure mode than the field-mapping bug being fixed here. Do not narrow or remove it.

### Dependency on Phase 1's Evidence
- **D-09:** Phase 2 must **independently re-verify** the live response shape at the start of its own execution — do NOT hard-depend on Phase 1's captured sample snapshot artifact existing, being fresh, or parsing in a specific format. Phase 2 does its own live poll + shape inspection as the first step of fixing the field mapping. If Phase 1's artifact happens to exist, it may be read as a cross-check, but it is not a blocking input.
- **D-10:** Rationale: time may pass between phases, and every live API call returns fresh market data anyway — independent re-verification is strictly safer than trusting a potentially stale or differently-shaped prior artifact, and avoids Phase 2 planning/execution being blocked on Phase 1's exact output format.

### Claude's Discretion
- Exact mechanism for detecting 401/403 specifically (exception type inspection, status code attribute, or string-matching the massive client's raised exception) — to be confirmed during Phase 2 research against the actual `massive` package's error surface.
- Exact wording of the CRITICAL log line.
- Whether the circuit-breaker state lives as an instance flag on `MassiveDataSource` or some other minimal mechanism — implementation detail, not a user-facing decision.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Market Data Design
- `planning/MARKET_DATA_DESIGN.md` §8.4 — self-flagged field-mapping risk (the bug this phase fixes)
- `planning/MARKET_DATA_DESIGN.md` §8.5 — documented error-handling table (401/403 = fatal per design doc; this phase's circuit-breaker decision (D-01–D-05) is the actual resolution, not a literal implementation of "fatal")
- `planning/MARKET_DATA_SUMMARY.md` — summary status of the market data component

### Project Context
- `.planning/PROJECT.md` — Constraints (fail-soft error handling, threading model, rate-limit tiers), Key Decisions table (notes fail-soft handling as "⚠️ Revisit")
- `.planning/REQUIREMENTS.md` — MASSIVE-02 through MASSIVE-05 (this phase), MASSIVE-01 (Phase 1 prerequisite)
- `.planning/ROADMAP.md` — Phase 2 success criteria (verbatim source of the 5 criteria referenced throughout this document)
- `.planning/phases/01-massive-api-key-setup-auth-verification/01-CONTEXT.md` — Phase 1's decisions; D-09/D-10 above explain why Phase 2 does not hard-depend on Phase 1's captured artifact despite this reference

### Source Files
- `backend/app/market/massive_client.py` — primary file being modified (auth-error classification + field-mapping fix)
- `backend/app/market/cache.py` — `PriceCache` — must receive zero changes (constraint, not a file to modify)
- `backend/app/market/stream.py` — SSE stream — must receive zero changes (constraint, not a file to modify)
- `backend/tests/market/test_massive.py` — current mocked test suite (56% coverage); Phase 2 may need to update mocks to match the corrected field names, but building out broader real-response-shape coverage is explicitly Phase 3's job

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MassiveDataSource._poll_once()` in `massive_client.py` already isolates both the per-snapshot try/except and the outer per-poll-cycle try/except — the circuit-breaker logic (D-01–D-05) and the field-mapping fix (D-06–D-08) both land inside this one method's existing structure, no new files needed.
- `PriceCache.update()` already accepts arbitrary `price`/`timestamp` floats — once the correct real values are extracted, no changes needed downstream (confirms MASSIVE-04's zero-code-change constraint structurally).

### Established Patterns
- `test_massive.py`'s `_make_snapshot()` helper mocks `last_trade.timestamp` as milliseconds — if the real shape fix changes the field name/unit, this mock helper and its dependent assertions (e.g. `test_timestamp_conversion`) will need updating to match, even though broader test coverage work is Phase 3's.
- Per-poll-cycle failures are currently caught by a single generic `except Exception` in `_poll_once` (confirmed via direct read) — the circuit-breaker fix needs to add a more specific check *before* or *within* that broad catch, without accidentally catching the auth-specific logic in the same generic handler it's meant to override.

### Integration Points
- `create_market_data_source()` in `factory.py` is the only call site that constructs `MassiveDataSource` — no changes needed there; the circuit breaker is internal to the class.

</code_context>

<specifics>
## Specific Ideas

- The circuit breaker should feel like "this key is definitely bad, stop wasting API calls on it" rather than "shut the whole app down" — a single clear log line is enough signal for a single-user local dev tool.
- The field-mapping fix must be provably correct against one real captured response, not theorized from documentation alone (this is the entire point of the milestone, per `.planning/PROJECT.md`'s core value statement).

</specifics>

<deferred>
## Deferred Ideas

- Sustained rate-limit run duration/definition (MASSIVE-03) — this gray area was raised but not selected for discussion in this session; left to planning/research to propose a reasonable default (e.g. N poll cycles over M minutes) unless revisited.
- Exposing market-data-source health via `/api/health` — considered and explicitly rejected for this milestone (D-03); revisit only if a future milestone needs programmatic health visibility.
- Auto-retry-after-cooldown for the circuit breaker — considered and explicitly rejected (D-04); revisit only if real-world use shows restart-to-recover is too disruptive.
- Defensive multi-field fallback parsing — considered and explicitly rejected (D-06); revisit only if the Massive SDK's response shape proves unstable across calls/versions.

</deferred>

---

*Phase: 2-real-data-polling-validation-field-mapping-fix*
*Context gathered: 2026-10-27*
