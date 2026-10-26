import { Page, expect } from "@playwright/test";

export const DEFAULT_TICKERS = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
];

/** Waits until at least one watchlist row shows a real (non "—") price,
 * i.e. the SSE stream has delivered at least one tick for that ticker. */
export async function waitForLivePrice(page: Page, ticker: string, timeout = 15_000) {
  const cell = page.getByTestId(`price-cell-${ticker}`);
  await expect(cell).not.toHaveText("—", { timeout });
}

/** Reads the numeric price shown in a watchlist/positions cell, stripping
 * currency formatting ("$123.45" -> 123.45). */
export async function readCurrencyText(text: string): Promise<number> {
  const cleaned = text.replace(/[^0-9.-]/g, "");
  return parseFloat(cleaned);
}
