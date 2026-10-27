# Phase 1: Massive API Key Setup & Auth Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-27
**Phase:** 1-massive-api-key-setup-auth-verification
**Areas discussed:** Key acquisition status, Verification method, Invalid-key test approach

---

## Key Acquisition Status

| Option | Description | Selected |
|--------|-------------|----------|
| I already have a key | Skip straight to verification | |
| I need to get one | Plan includes a manual signup checkpoint | ✓ |
| Not sure / explain tiers | Rundown of tier tradeoffs before deciding | |

**User's choice:** I need to get one.
**Notes:** Followed by tier choice and pause-point questions.

| Option | Description | Selected |
|--------|-------------|----------|
| Free tier | 5 req/min, 15s poll, matches hardcoded factory.py default | ✓ |
| Paid tier | Faster polling, needs billing setup | |

**User's choice:** Free tier.

| Option | Description | Selected |
|--------|-------------|----------|
| Plan should pause | Non-autonomous checkpoint task for signup + .env paste | ✓ |
| I'll get it now, continue planning | No formal checkpoint | |

**User's choice:** Plan should pause.

---

## Verification Method

| Option | Description | Selected |
|--------|-------------|----------|
| Run the real backend | Start the actual FastAPI app locally with the key set, hit GET /api/stream/prices | ✓ |
| Disposable script | Call MassiveDataSource/RESTClient directly, skip the app | |
| Opt-in pytest (live-gated) | Permanent test infra gated on a real key | |

**User's choice:** Run the real backend.
**Notes:** Chosen explicitly to also exercise success criterion #1 (clean startup), and to avoid overlapping with Phase 3's test-coverage scope.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, log/save a sample response | Capture real TickerSnapshot shape for Phase 2's benefit | ✓ |
| No, just confirm prices update | Stay minimal | |

**User's choice:** Yes, log/save a sample response.

---

## Invalid-Key Test Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Garbage string key | Malformed MASSIVE_API_KEY value, no account action needed | ✓ |
| Revoke the real key temporarily | Use real key, revoke via dashboard, test, re-enable | |

**User's choice:** Garbage string key.

| Option | Description | Selected |
|--------|-------------|----------|
| Current fail-soft-retry behavior is a PASS | No crash/hang/runaway retries + clear 401 in logs = acceptable; fatal-vs-fail-soft decision is explicitly Phase 2's (MASSIVE-05) | ✓ |
| Flag it as a gap even if it "passes" | Call out fail-soft-forever-retry explicitly as a known gap | |

**User's choice:** Current fail-soft-retry behavior is a PASS.
**Notes:** User confirmed Phase 1 should document observed behavior for Phase 2 to act on, not judge or fix it.

---

## Claude's Discretion

- Exact mechanism for capturing the sample snapshot (log line vs. saved file).
- Exact format/location of the verification write-up documenting both the live-success and invalid-key observations.

## Deferred Ideas

- Paid-tier signup and configurable `poll_interval` (deferred — free tier only this milestone).
- Fixing the `last_trade.timestamp`/`sip_timestamp` field-mapping risk (Phase 2, MASSIVE-02).
- Resolving fatal-vs-fail-soft auth error handling (Phase 2, MASSIVE-05).
- Permanent/committed test coverage for the real-API response shape (Phase 3, TEST-01/TEST-02).
