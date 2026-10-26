import { test, expect } from "@playwright/test";
import { waitForLivePrice } from "./helpers";

// PLAN.md §12 scenario 2: "Watchlist add/remove" — add a ticker, confirm it
// appears and starts streaming; remove a ticker, confirm it disappears.

test.describe("Watchlist add/remove", () => {
  test("adding a ticker makes it appear and start streaming; removing it removes it", async ({
    page,
  }) => {
    const ticker = "PYPL"; // not in the default 10-ticker seed list (PLAN.md §7)

    await page.goto("/");

    // Sanity: not present before we add it.
    await expect(page.getByTestId(`watchlist-row-${ticker}`)).toHaveCount(0);

    await page.getByTestId("watchlist-add-input").fill(ticker);
    await page.getByTestId("watchlist-add-button").click();

    await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible({ timeout: 10_000 });

    // Confirm it actually starts streaming (price resolves from "—").
    await waitForLivePrice(page, ticker, 15_000);

    // Confirm the backend watchlist also reflects the add (REST contract
    // check, independent of UI state).
    const listResp = await page.request.get("/api/watchlist");
    expect(listResp.ok()).toBeTruthy();
    const list = (await listResp.json()) as Array<{ ticker: string }>;
    expect(list.map((w) => w.ticker)).toContain(ticker);

    // Now remove it via the UI.
    await page.getByTestId(`remove-${ticker}`).click();
    await expect(page.getByTestId(`watchlist-row-${ticker}`)).toHaveCount(0, { timeout: 10_000 });

    const listResp2 = await page.request.get("/api/watchlist");
    const list2 = (await listResp2.json()) as Array<{ ticker: string }>;
    expect(list2.map((w) => w.ticker)).not.toContain(ticker);
  });
});
