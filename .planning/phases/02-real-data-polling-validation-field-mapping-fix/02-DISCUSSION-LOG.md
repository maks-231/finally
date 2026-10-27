# Phase 2: Real-Data Polling Validation & Field-Mapping Fix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-27
**Phase:** 2-real-data-polling-validation-field-mapping-fix
**Areas discussed:** Auth failure resolution (MASSIVE-05), Field-mapping fix scope, Dependency on Phase 1's evidence

---

## Auth Failure Resolution (MASSIVE-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Make it fatal (matches design doc) | Detect 401/403, stop retrying, surface a clear error | |
| Circuit breaker (middle ground) | Stop auto-retry on auth failure, but don't crash the app | ✓ |
| Formally keep fail-soft, just classify it | No behavior change, just clearer log classification | |

**User's choice:** Circuit breaker (middle ground).

| Option | Description | Selected |
|--------|-------------|----------|
| 1 (immediate) | Trip on the first 401/403 | ✓ |
| 3 consecutive | Tolerate a possible transient misclassification first | |

**User's choice:** 1 (immediate).

| Option | Description | Selected |
|--------|-------------|----------|
| CRITICAL log line only | Log-only surfacing, no new API surface | ✓ |
| Also expose via /api/health | Add a health-check field too | |

**User's choice:** CRITICAL log line only.

| Option | Description | Selected |
|--------|-------------|----------|
| Stay stopped until restart | No auto-retry after tripping | ✓ |
| Auto-retry after a cooldown | Periodic retry even after tripping | |

**User's choice:** Stay stopped until restart.

---

## Field-Mapping Fix Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal targeted patch | Fix exactly the confirmed-wrong field/unit | ✓ |
| Defensive multi-field fallback | Try multiple candidate fields with graceful fallback | |

**User's choice:** Minimal targeted patch.

| Option | Description | Selected |
|--------|-------------|----------|
| Verify price too, same live run | Also confirm last_trade.price's real shape | ✓ |
| Timestamp only — price is out of scope | Stick strictly to the self-flagged risk | |

**User's choice:** Verify price too, same live run.

| Option | Description | Selected |
|--------|-------------|----------|
| Keep it as-is | Leave the except (AttributeError, TypeError) safety net unchanged | ✓ |
| Narrow or remove it | Tighten exception handling now that root cause is known | |

**User's choice:** Keep it as-is.

---

## Dependency on Phase 1's Evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Re-verify independently | Phase 2 does its own live poll + shape check, regardless of Phase 1's artifact | ✓ |
| Reuse Phase 1's artifact directly | Fix based on Phase 1's single captured sample only | |

**User's choice:** Re-verify independently.
**Notes:** Rationale given: time may pass between phases, every live call returns fresh data anyway, and this avoids a hard dependency on Phase 1's exact output format/freshness.

---

## Claude's Discretion

- Exact mechanism for detecting 401/403 specifically (exception type vs. status attribute vs. string match) — deferred to Phase 2 research against the real `massive` package error surface.
- Exact CRITICAL log line wording.
- Where circuit-breaker state lives internally (instance flag, etc.).

## Deferred Ideas

- Sustained rate-limit run duration/definition (MASSIVE-03) — raised but not selected for discussion this session; left to planning/research.
- Exposing market-data health via `/api/health` — explicitly rejected for this milestone.
- Auto-retry-after-cooldown for the circuit breaker — explicitly rejected.
- Defensive multi-field fallback parsing — explicitly rejected.
