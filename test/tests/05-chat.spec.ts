import { test, expect } from "@playwright/test";

// PLAN.md §12 scenario 6: "AI chat (mocked)" — send a message that mock
// mode turns into a trade or watchlist action; confirm the assistant's
// reply renders, the executed action appears inline as a confirmation, and
// it's actually reflected in portfolio/watchlist state.
//
// Trigger rules are from backend/app/llm/mock.py (LLM_MOCK=true):
//   - "buy <QTY> shares of <TICKER>" / "sell <QTY> <TICKER>" -> real trade
//   - "add <TICKER> to the watchlist" / "remove <TICKER> from the watchlist"
//   - oversized quantity -> deterministic insufficient-cash failure

test.describe("AI chat (mocked, LLM_MOCK=true)", () => {
  test("a chat trade message auto-executes a real trade and shows inline confirmation", async ({
    page,
  }) => {
    const ticker = "JPM"; // default watchlist ticker, already has a cached price
    const quantity = 1;

    await page.goto("/");

    const before = await (await page.request.get("/api/portfolio")).json();
    const cashBefore: number = before.cash_balance;

    await page.getByTestId("chat-input").fill(`buy ${quantity} shares of ${ticker}`);

    const [chatResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/chat") && r.request().method() === "POST",
      ),
      page.getByTestId("chat-send-button").click(),
    ]);

    expect(chatResponse.ok()).toBeTruthy();
    const body = await chatResponse.json();
    expect(body.trades?.length ?? 0).toBeGreaterThan(0);
    expect(body.trades[0].success, "mock trade should succeed with ample cash").toBe(true);

    // Assistant's reply renders in the chat history.
    await expect(page.getByTestId("chat-message-assistant").last()).toContainText("Mock mode");

    // Executed action appears inline as a confirmation.
    const confirmations = page.getByTestId("chat-action-confirmations").last();
    await expect(confirmations).toBeVisible();
    await expect(confirmations).toContainText(ticker);

    // Actually reflected in backend portfolio state (ground truth, independent
    // of any UI polling delay).
    const after = await (await page.request.get("/api/portfolio")).json();
    const pos = after.positions.find((p: { ticker: string }) => p.ticker === ticker);
    expect(pos, `expected a ${ticker} position after the chat-triggered buy`).toBeTruthy();
    expect(after.cash_balance).toBeLessThan(cashBefore);

    // Also check it surfaces in the UI without a manual page reload, within
    // usePortfolio's 15s poll interval (frontend/src/hooks/usePortfolio.ts).
    await expect(page.getByTestId(`position-row-${ticker}`)).toBeVisible({ timeout: 17_000 });
  });

  test("a chat watchlist-add message auto-executes and shows inline confirmation", async ({
    page,
  }) => {
    const ticker = "DIS";

    await page.goto("/");

    // Backend starting state.
    const beforeList = (await (await page.request.get("/api/watchlist")).json()) as Array<{
      ticker: string;
    }>;
    expect(beforeList.map((w) => w.ticker)).not.toContain(ticker);

    await page.getByTestId("chat-input").fill(`add ${ticker} to the watchlist`);
    const [chatResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/chat") && r.request().method() === "POST",
      ),
      page.getByTestId("chat-send-button").click(),
    ]);
    expect(chatResponse.ok()).toBeTruthy();
    const body = await chatResponse.json();
    expect(body.watchlist_changes?.length ?? 0).toBeGreaterThan(0);
    expect(body.watchlist_changes[0].success).toBe(true);

    await expect(page.getByTestId("chat-message-assistant").last()).toContainText("Mock mode");
    const confirmations = page.getByTestId("chat-action-confirmations").last();
    await expect(confirmations).toContainText(ticker);

    // Ground truth: backend watchlist actually updated.
    const afterList = (await (await page.request.get("/api/watchlist")).json()) as Array<{
      ticker: string;
    }>;
    expect(afterList.map((w) => w.ticker)).toContain(ticker);

    // UI reflection check: useWatchlist (frontend/src/hooks/useWatchlist.ts)
    // only refetches on mount or on a manual add/remove call from its own
    // hook instance. useChat (frontend/src/hooks/useChat.ts) never calls
    // useWatchlist's refetch, and useWatchlist has no poll loop at all
    // (unlike usePortfolio's 15s interval), so a chat-triggered watchlist
    // change never reaches the UI without a manual page reload. This is a
    // real bug, not a timing flake — see RESULTS.md for the full repro.
    await expect(
      page.getByTestId(`watchlist-row-${ticker}`),
      `BUG: watchlist row for ${ticker} should appear live after a chat-triggered ` +
        `"add" action (backend confirmed it succeeded), without needing a page reload. ` +
        `frontend/src/app/page.tsx wires useChat() independently of useWatchlist() with ` +
        `no cross-refetch.`,
    ).toBeVisible({ timeout: 5_000 });
  });

  test("an oversized chat trade fails validation and does not change cash", async ({ page }) => {
    const ticker = "AAPL";

    await page.goto("/");
    const before = await (await page.request.get("/api/portfolio")).json();
    const cashBefore: number = before.cash_balance;

    await page.getByTestId("chat-input").fill(`buy 999999 shares of ${ticker}`);
    const [chatResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/chat") && r.request().method() === "POST",
      ),
      page.getByTestId("chat-send-button").click(),
    ]);
    expect(chatResponse.ok()).toBeTruthy();
    const body = await chatResponse.json();
    expect(body.trades?.length ?? 0).toBeGreaterThan(0);
    expect(body.trades[0].success, "oversized buy should fail validation").toBe(false);
    expect(body.trades[0].reason).toBeTruthy();

    // Ground truth: cash must be unchanged.
    const after = await (await page.request.get("/api/portfolio")).json();
    expect(after.cash_balance).toBeCloseTo(cashBefore, 6);

    // Inline confirmation should indicate failure. The frontend's
    // ActionConfirmations component (ChatPanel.tsx) branches on `t.error`,
    // but the backend's ExecutedTrade shape is `{success, reason}` (no
    // `error` field — see app/api/chat.py's `_execute_trades` and
    // app/llm/schema.py's TradeAction). `t.error` is therefore always
    // `undefined`, so the UI renders the "✓ success" branch even for a
    // trade the backend rejected. Confirmed by the raw rendered markup below.
    const confirmations = page.getByTestId("chat-action-confirmations").last();
    await expect(confirmations).toBeVisible();
    const text = (await confirmations.textContent()) ?? "";
    expect(
      text,
      `BUG: rejected trade (insufficient cash, backend reason: "${body.trades[0].reason}") ` +
        `rendered with success styling instead of a failure mark. Rendered text: "${text}". ` +
        `Root cause: frontend/src/components/ChatPanel.tsx checks "t.error" which the backend ` +
        `never sends (it sends "success"/"reason" per app/api/chat.py).`,
    ).toContain("✕");
  });
});
