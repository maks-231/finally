import { test, expect } from "@playwright/test";
import { DEFAULT_TICKERS, waitForLivePrice } from "./helpers";

// PLAN.md §12 scenario 1: "Fresh start" — default 10-ticker watchlist
// appears, $10,000 cash shown, prices are visibly streaming/updating
// within a few seconds.
//
// Must run against a freshly-seeded DB (no prior trades/watchlist edits) to
// be meaningful — see test/RESULTS.md for how this suite's run order
// interacts with that requirement.

test.describe("Fresh start", () => {
  test("default watchlist, cash balance, and live prices render on load", async ({ page }) => {
    await page.goto("/");

    // All 10 default tickers from PLAN.md §7 seed data.
    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
    }

    // $10,000 starting cash (PLAN.md §2, §7).
    await expect(page.getByTestId("header-cash-balance")).toHaveText("$10,000.00");

    // Total value should resolve (not stuck on "—") once /api/portfolio loads.
    await expect(page.getByTestId("header-total-value")).not.toHaveText("—", { timeout: 10_000 });

    // Connection indicator should reach "connected" quickly.
    await expect(page.getByTestId("connection-status")).toHaveAttribute("data-state", "connected", {
      timeout: 10_000,
    });

    // Prices should visibly start streaming: pick a couple of tickers and
    // confirm they move off the initial "—" placeholder within a few seconds.
    await waitForLivePrice(page, "AAPL");
    await waitForLivePrice(page, "NVDA");

    // And genuinely "live" — capture a price, wait, and expect at least one
    // of the sampled tickers to have ticked again (simulator updates every
    // ~500ms per PLAN.md §6, so several seconds is ample).
    const before: Record<string, string> = {};
    for (const ticker of DEFAULT_TICKERS) {
      before[ticker] = (await page.getByTestId(`price-cell-${ticker}`).textContent()) ?? "";
    }
    await page.waitForTimeout(4000);
    let changed = 0;
    for (const ticker of DEFAULT_TICKERS) {
      const after = (await page.getByTestId(`price-cell-${ticker}`).textContent()) ?? "";
      if (after !== before[ticker]) changed++;
    }
    expect(changed, "expected at least one watchlist price to update within 4s").toBeGreaterThan(0);
  });
});
