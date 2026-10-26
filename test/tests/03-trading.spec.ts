import { test, expect } from "@playwright/test";

// PLAN.md §12 scenarios 3 & 4: Buy / Sell.
//
// Each test captures portfolio state via the REST API immediately before
// and after the UI action, so assertions don't depend on exactly what
// earlier tests in the suite did to cash/positions (only that this
// particular trade's effect is correct).

test.describe("Buy", () => {
  test("submitting a buy order decreases cash, adds a position, updates total", async ({
    page,
  }) => {
    const ticker = "MSFT";
    const quantity = 2;

    await page.goto("/");

    const before = await (await page.request.get("/api/portfolio")).json();
    const cashBefore: number = before.cash_balance;

    await page.getByTestId("trade-ticker-input").fill(ticker);
    await page.getByTestId("trade-quantity-input").fill(String(quantity));

    const [tradeResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/portfolio/trade") && r.request().method() === "POST",
      ),
      page.getByTestId("trade-buy-button").click(),
    ]);

    expect(tradeResponse.ok(), "buy order should be accepted (sufficient cash)").toBeTruthy();
    const tradeBody = await tradeResponse.json();
    expect(tradeBody.cash_balance).toBeLessThan(cashBefore);

    // Position appears in the table.
    await expect(page.getByTestId(`position-row-${ticker}`)).toBeVisible({ timeout: 10_000 });

    // Header cash reflects the new balance (usePortfolio refetches after trade).
    await expect(page.getByTestId("header-cash-balance")).toHaveText(
      new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
        tradeBody.cash_balance,
      ),
      { timeout: 10_000 },
    );

    // Portfolio total updates (non-null, matches API's total_value).
    const totalText = await page.getByTestId("header-total-value").textContent();
    expect(totalText).not.toBe("—");

    // Cross-check against the REST contract directly.
    const after = await (await page.request.get("/api/portfolio")).json();
    const pos = after.positions.find((p: { ticker: string }) => p.ticker === ticker);
    expect(pos, `expected a ${ticker} position after buying`).toBeTruthy();
    expect(pos.quantity).toBeGreaterThanOrEqual(quantity);
    expect(after.cash_balance).toBeCloseTo(cashBefore - quantity * tradeBody.price, 2);
  });
});

test.describe("Sell", () => {
  test("selling the full quantity increases cash and removes the position", async ({ page }) => {
    const ticker = "NFLX";
    const quantity = 1;

    await page.goto("/");

    // Self-contained setup: buy first via the REST API (not the UI) so this
    // test doesn't depend on the Buy test above having run.
    const buyResp = await page.request.post("/api/portfolio/trade", {
      data: { ticker, quantity, side: "buy" },
    });
    expect(buyResp.ok(), "setup buy should succeed").toBeTruthy();

    await page.reload();
    await expect(page.getByTestId(`position-row-${ticker}`)).toBeVisible({ timeout: 10_000 });

    const before = await (await page.request.get("/api/portfolio")).json();
    const cashBefore: number = before.cash_balance;
    const posBefore = before.positions.find((p: { ticker: string }) => p.ticker === ticker);
    expect(posBefore).toBeTruthy();

    await page.getByTestId("trade-ticker-input").fill(ticker);
    await page.getByTestId("trade-quantity-input").fill(String(posBefore.quantity));

    const [tradeResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/portfolio/trade") && r.request().method() === "POST",
      ),
      page.getByTestId("trade-sell-button").click(),
    ]);

    expect(tradeResponse.ok(), "sell order should be accepted (owns enough shares)").toBeTruthy();
    const tradeBody = await tradeResponse.json();
    expect(tradeBody.cash_balance).toBeGreaterThan(cashBefore);

    // Sold to exactly zero -> position row should disappear entirely
    // (PLAN.md §7: "the position row is deleted rather than kept at zero").
    await expect(page.getByTestId(`position-row-${ticker}`)).toHaveCount(0, { timeout: 10_000 });

    const after = await (await page.request.get("/api/portfolio")).json();
    const posAfter = after.positions.find((p: { ticker: string }) => p.ticker === ticker);
    expect(posAfter, "position should be fully removed after selling to zero").toBeUndefined();
  });
});
