# FinAlly E2E Test Results

## Latest run (RE-TEST after frontend fix) — 2026-10-26

**Image under test:** `finally:latest`, rebuilt from scratch via `docker build -t finally .`
from the repo root (frontend source changed since the prior run — see "fix applied" below —
so the previously-built image was stale and a fresh build was required).

**Fix applied before this run** (by a frontend-engineer agent, not by this test pass):
- `frontend/src/hooks/useChat.ts`'s `send()` now returns the `ChatResponse`.
- `frontend/src/app/page.tsx` awaits `send()` and, if the response contains a successful
  `watchlist_changes` entry, calls `refetchWatchlist()` (confirmed present at lines ~21-36:
  `const hasSuccessfulWatchlistChange = response?.watchlist_changes?.some(...)` →
  `await refetchWatchlist()`).
- `frontend/src/components/ChatPanel.tsx`'s `ActionConfirmations` now branches on
  `t.success === false` / `w.success === false` (confirmed present at lines 26, 31, 44, 49)
  instead of a nonexistent `error` field, rendering a failure state with the `reason` when
  present.
- `frontend/src/lib/types.ts` updated so `ExecutedTrade`/`WatchlistChange` match the real
  backend contract (`success: boolean`, `reason?: string`), dropping the stale `error` field.

**Mode:** `LLM_MOCK=true` (no `OPENROUTER_API_KEY`/`MASSIVE_API_KEY` set — simulator + mock
LLM only).

**Approach used:** Pragmatic fallback — `docker run` for the app container + locally-run
Playwright (`npx playwright test`) against `http://localhost:8000`, same as the prior run.
`test/docker-compose.test.yml` still exists and specifies the compose orchestration but was
not exercised end-to-end in this sandboxed environment, for the same reasons as before.

**Run commands:**
```bash
docker build -t finally .
VOL=finally-e2e-data-retest-<timestamp>   # new, never-before-used volume name
docker run --rm -d --name finally-e2e -v ${VOL}:/app/db -p 8000:8000 -e LLM_MOCK=true finally:latest
cd test && BASE_URL=http://localhost:8000 APP_CONTAINER_NAME=finally-e2e npx playwright test
```

**Container/volume cleanup:** done after the run — `docker rm -f finally-e2e` and
`docker volume rm finally-e2e-data-retest-<timestamp>`; both confirmed absent from
`docker ps -a` / `docker volume ls` afterward. Nothing left running.

**Test suite:** unchanged from the prior run — no test files were rewritten for this pass,
per instructions. All 9 Playwright tests across the 6 spec files ran against one fresh
container/volume, in fixed file order (single worker, `fullyParallel: false`).

### Summary

| # | Scenario | Result |
|---|----------|--------|
| 1 | Fresh start | PASS |
| 2 | Watchlist add/remove | PASS |
| 3 | Buy | PASS |
| 4 | Sell | PASS |
| 5 | Portfolio visualization (heatmap + P&L chart) | PASS |
| 6a | AI chat — trade auto-execution | PASS |
| 6b | AI chat — watchlist auto-execution reflected in UI (no reload) | **PASS (was FAIL)** |
| 6c | AI chat — failed trade shown with failure styling in chat UI | **PASS (was FAIL)** |
| 7 | SSE resilience | PASS |

**9 passed, 0 failed.** Both previously-failing sub-cases of scenario 6 now pass against the
rebuilt image, with no regressions observed in the other 7 scenarios.

Actual Playwright output:
```
Running 9 tests using 1 worker

  ✓  1 [chromium] › tests/01-fresh-start.spec.ts:13:7 › Fresh start › default watchlist, cash balance, and live prices render on load (4.8s)
  ✓  2 [chromium] › tests/02-watchlist.spec.ts:8:7 › Watchlist add/remove › adding a ticker makes it appear and start streaming; removing it removes it (1.5s)
  ✓  3 [chromium] › tests/03-trading.spec.ts:11:7 › Buy › submitting a buy order decreases cash, adds a position, updates total (580ms)
  ✓  4 [chromium] › tests/03-trading.spec.ts:61:7 › Sell › selling the full quantity increases cash and removes the position (703ms)
  ✓  5 [chromium] › tests/04-portfolio-viz.spec.ts:18:7 › Portfolio visualization › heatmap renders a colored cell and the P&L chart gets data points after trades (599ms)
  ✓  6 [chromium] › tests/05-chat.spec.ts:14:7 › AI chat (mocked, LLM_MOCK=true) › a chat trade message auto-executes a real trade and shows inline confirmation (15.4s)
  ✓  7 [chromium] › tests/05-chat.spec.ts:59:7 › AI chat (mocked, LLM_MOCK=true) › a chat watchlist-add message auto-executes and shows inline confirmation (608ms)
  ✓  8 [chromium] › tests/05-chat.spec.ts:110:7 › AI chat (mocked, LLM_MOCK=true) › an oversized chat trade fails validation and does not change cash (570ms)
  ✓  9 [chromium] › tests/06-sse-resilience.spec.ts:45:7 › SSE resilience › connection-status reflects disconnect and recovers on reconnect (8.6s)

  9 passed (34.1s)
```

### Notes on the two newly-passing cases

- **6b** (`test/tests/05-chat.spec.ts`, "a chat watchlist-add message auto-executes...",
  line ~107): the assertion `expect(page.getByTestId('watchlist-row-DIS')).toBeVisible({
  timeout: 5_000 })` — unchanged from the prior failing run — now passes within the 5s
  window because `page.tsx` refetches the watchlist as soon as `useChat().send()` resolves
  with a successful `watchlist_changes` entry, instead of waiting for a manual reload.
- **6c** (`test/tests/05-chat.spec.ts`, "an oversized chat trade fails validation...", line
  ~150): the assertion `expect(text).toContain('✕')` — unchanged from the prior failing run
  — now passes because `ChatPanel.tsx` branches on `t.success === false` (matching the
  backend's real `{success, reason}` contract) and renders the failure mark with the
  rejection reason, instead of always taking the success branch due to checking a
  nonexistent `error` field.

No new issues were observed in scenarios 1-5 or 7; their underlying test logic is unchanged
from the prior run (see below for full per-scenario detail carried over from that run, still
accurate).

---

## Prior run (pre-fix) — 2026-10-26

**Image under test:** `finally:latest` (local build, no changes made to app source)
**Mode:** `LLM_MOCK=true` (no `OPENROUTER_API_KEY`/`MASSIVE_API_KEY` set — simulator + mock LLM only)
**Approach used:** Pragmatic fallback — `docker run` for the app container +
locally-run Playwright (`npx playwright test`) against `http://localhost:8000`.
`test/docker-compose.test.yml` is included and implements the spec'd
app+Playwright-container orchestration, but pulling the
`mcr.microsoft.com/playwright` image was not exercised end-to-end in this
sandboxed run (no cached image, and a full pull plus install cycle was
deemed not worth the time given the fallback is explicitly sanctioned by
the task brief). Both the compose file and the fallback target the same
app image and the same `LLM_MOCK=true` environment, so results should be
identical either way.
**Run command:**
```bash
docker run --rm -d --name finally-e2e -v finally-e2e-data:/app/db -p 8000:8000 -e LLM_MOCK=true finally:latest
cd test && BASE_URL=http://localhost:8000 APP_CONTAINER_NAME=finally-e2e npx playwright test
```
**Container/volume cleanup:** done after each run (`docker rm -f finally-e2e`, `docker volume rm finally-e2e-data`); nothing was left running.

**Note on test ordering/isolation:** all 9 tests ran against one fresh
container/DB per full suite run, in the fixed file order below (single
worker, `fullyParallel: false`). Each test either reads the current API
state before acting (rather than assuming a pristine `$10,000`/empty
portfolio) or sets up its own fixture data via direct REST calls, so they
don't depend on each other's side effects — but scenario 1 ("Fresh start")
must still be the first test run against a given container/volume, since
it specifically asserts the pristine seed state.

### Summary

| # | Scenario | Result |
|---|----------|--------|
| 1 | Fresh start | PASS |
| 2 | Watchlist add/remove | PASS |
| 3 | Buy | PASS |
| 4 | Sell | PASS |
| 5 | Portfolio visualization (heatmap + P&L chart) | PASS |
| 6 | AI chat (mocked) — trade auto-execution | PASS |
| 6 | AI chat (mocked) — watchlist auto-execution reflected in UI | **FAIL** |
| 6 | AI chat (mocked) — failed trade shown correctly in chat UI | **FAIL** |
| 7 | SSE resilience | PASS |

**7 passed, 2 failed** (both failures are sub-cases of scenario 6). Both were fixed and
verified passing in the re-test above.

---

### 1. Fresh start — PASS

`test/tests/01-fresh-start.spec.ts`

- All 10 default tickers (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX) render as watchlist rows.
- Header cash balance shows `$10,000.00`.
- Header total value resolves from the `/api/portfolio` response (not stuck on `—`).
- `connection-status` reaches `data-state="connected"` within 10s.
- Prices move off the initial `—` placeholder within a few seconds for AAPL and NVDA, and at least one of the 10 watchlist prices visibly changes within a 4s sampling window.

### 2. Watchlist add/remove — PASS

`test/tests/02-watchlist.spec.ts`

- Adding `PYPL` via the watchlist input/button makes the row appear, and its price resolves from the live SSE stream within 15s.
- `GET /api/watchlist` confirms the backend state matches.
- Removing it via the row's remove button makes the row disappear from the UI and from `GET /api/watchlist`.

### 3. Buy — PASS

`test/tests/03-trading.spec.ts` ("Buy" block)

- Buying 2 shares of MSFT via the trade bar: the `POST /api/portfolio/trade` response's `cash_balance` is less than the pre-trade balance, the `position-row-MSFT` appears in the positions table, the header cash figure updates to match the trade response, and `GET /api/portfolio` afterward shows `cash_balance == cashBefore - quantity * price` (to 2 decimal places) and a matching position.

### 4. Sell — PASS

`test/tests/03-trading.spec.ts` ("Sell" block)

- Set up via `POST /api/portfolio/trade` (buy 1 NFLX), then sold the full quantity through the UI trade bar: cash increases, and — per PLAN.md §7 ("position row is deleted rather than kept at zero") — the `position-row-NFLX` disappears entirely from both the UI and `GET /api/portfolio`.

### 5. Portfolio visualization — PASS

`test/tests/04-portfolio-viz.spec.ts`

- Two back-to-back buys of GOOGL produce two `portfolio_snapshots` rows immediately (confirmed via `GET /api/portfolio/history`, length ≥ 2) — exercising the "trade triggers an immediate snapshot" rule from PLAN.md §7 without waiting on the 30s periodic task.
- Heatmap renders a cell for GOOGL; its SVG `rect` `fill` matches the sign of `unrealized_pnl_percent` from `GET /api/portfolio` (green `rgba(46, 204, 113, ...)` for profit, red `rgba(239, 68, 68, ...)` for loss, gray for exactly flat) — i.e., coloring is plausible and directionally correct, whichever way the simulator moved the price.
- The P&L chart moves past its "Not enough history yet." empty state and renders an actual `recharts-line-curve` once ≥2 snapshots exist.

### 6a. AI chat — trade auto-execution — PASS

`test/tests/05-chat.spec.ts` ("a chat trade message auto-executes...")

- Sending `"buy 1 shares of JPM"` to `/api/chat` (mock mode) returns a `trades` array with `success: true`; the assistant's reply ("Mock mode: executing a buy order for 1 shares of JPM.") renders in the chat history; the inline confirmation (`chat-action-confirmations`) shows and mentions JPM; `GET /api/portfolio` afterward shows a new JPM position and reduced cash; and the positions table (`position-row-JPM`) picks this up live within `usePortfolio`'s 15s poll interval, with no page reload needed.

### 6b. AI chat — watchlist action not reflected in UI without reload — FIXED, now PASS

`test/tests/05-chat.spec.ts` ("a chat watchlist-add message auto-executes...")

Original repro (pre-fix), kept for reference:

1. Start the app fresh (`LLM_MOCK=true`), open `http://localhost:8000/`.
2. In the chat panel, send: `add DIS to the watchlist`.
3. Wait for the assistant's reply (mock mode responds immediately: `"Mock mode: adding DIS to your watchlist."`) and the inline confirmation (`✓ Watchlist: added DIS`) to render.
4. Without reloading the page, watch the Watchlist panel.

Originally: `GET /api/watchlist` confirmed the backend *did* add `DIS`, and the chat confirmation rendered correctly, but the Watchlist panel never showed the `DIS` row without a manual reload (root cause: `useChat`'s `send()` never triggered a `useWatchlist` refetch, and `useWatchlist` had no polling loop at all).

**Now:** `frontend/src/app/page.tsx` awaits `send()`'s returned `ChatResponse` and calls `refetchWatchlist()` whenever it contains a successful `watchlist_changes` entry. Verified in this re-test run: `watchlist-row-DIS` becomes visible within the test's 5s timeout, no reload needed.

### 6c. AI chat — failed trade rendered as a success in chat UI — FIXED, now PASS

`test/tests/05-chat.spec.ts` ("an oversized chat trade fails validation...")

Original repro (pre-fix), kept for reference:

1. Start the app fresh (`LLM_MOCK=true`), open `http://localhost:8000/`.
2. In the chat panel, send: `buy 999999 shares of AAPL` (deterministically triggers an insufficient-cash rejection per the mock trigger rules).
3. Observe the inline action confirmation rendered under the assistant's reply.

Originally: the confirmation rendered with success styling (`"✓ BUY 999999 AAPL"`) even though the backend correctly reported `trades[0] = {success: false, reason: "Insufficient cash balance for this trade."}` and cash was unchanged (root cause: `ChatPanel.tsx` checked a nonexistent `error` field instead of `success`).

**Now:** `ChatPanel.tsx`'s `ActionConfirmations` branches on `t.success === false` / `w.success === false` and `frontend/src/lib/types.ts` matches the real `{success, reason}` backend contract. Verified in this re-test run: the confirmation text contains `✕` and the rejection reason for the oversized trade.

### 7. SSE resilience — PASS

`test/tests/06-sse-resilience.spec.ts`

**Methodology note:** `context.setOffline(true)` (Playwright's standard browser-level network simulation) was tried first and does **not** reliably interrupt an already-open `EventSource`/SSE stream in Chromium — empirically verified: with `setOffline(true)` active for 3+ seconds, `AAPL`'s watchlist price kept ticking and `connection-status` stayed `"connected"` throughout. This is consistent with Chrome DevTools Protocol's offline emulation primarily blocking new request dispatch rather than bytes already flowing on an established streaming response. Per the task brief's own suggested fallback, the final test instead disrupts the **container's** network directly (`docker network disconnect/connect bridge <container>`), which severs the actual TCP connection carrying the SSE stream and reliably reproduces a real disconnect.

- Starting state: `connection-status` is `data-state="connected"`.
- After `docker network disconnect bridge finally-e2e`: `connection-status` transitions to `data-state="reconnecting"` within 20s (EventSource's native auto-retry puts `readyState` into `CONNECTING`, not `CLOSED`, while the server is unreachable — `usePriceStream.ts` maps that to `"reconnecting"`), and the AAPL price cell visibly freezes (no updates) while disconnected.
- After `docker network connect bridge finally-e2e`: `connection-status` returns to `data-state="connected"` within 20s, and the AAPL price cell resumes updating.

This test requires docker CLI access from wherever `playwright test` runs and an `APP_CONTAINER_NAME` matching the running app container (defaults to `finally-e2e`); it self-skips if the container isn't inspectable, so it won't false-fail inside a sandboxed Playwright container in the compose setup that lacks a docker socket.

---

## Files

- `test/package.json`, `test/playwright.config.ts` — Playwright (TypeScript) project config.
- `test/docker-compose.test.yml` — spec'd app + Playwright container orchestration (see note above on what was actually exercised).
- `test/tests/01-fresh-start.spec.ts` … `test/tests/06-sse-resilience.spec.ts` — one file per scenario group.
- `test/tests/helpers.ts` — shared test utilities.
