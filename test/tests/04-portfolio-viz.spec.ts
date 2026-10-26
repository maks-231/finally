import { test, expect } from "@playwright/test";

// PLAN.md §12 scenario 5: "Portfolio visualization" — heatmap renders with
// at least one position and plausible coloring (green profit / red loss),
// P&L chart has at least one data point after a trade (a trade triggers an
// immediate snapshot per PLAN.md §7).

// Mirrors frontend/src/components/PortfolioHeatmap.tsx's pnlColor() so we
// can assert the rendered fill matches the same green/red/gray rule,
// whichever direction the (randomly-moving) simulator happens to produce.
function expectedFill(pnlPercent: number): RegExp {
  if (pnlPercent > 0) return /rgba\(46, 204, 113,/;
  if (pnlPercent < 0) return /rgba\(239, 68, 68,/;
  return /rgba\(139, 148, 158,/;
}

test.describe("Portfolio visualization", () => {
  test("heatmap renders a colored cell and the P&L chart gets data points after trades", async ({
    page,
  }) => {
    const ticker = "GOOGL";

    await page.goto("/");

    // Two trades -> two immediate portfolio_snapshots rows (PLAN.md §7),
    // which is enough for PnlChart to render a line (it requires >= 2
    // points) without waiting on the 30s periodic snapshot task.
    const buy1 = await page.request.post("/api/portfolio/trade", {
      data: { ticker, quantity: 1, side: "buy" },
    });
    expect(buy1.ok()).toBeTruthy();
    const buy2 = await page.request.post("/api/portfolio/trade", {
      data: { ticker, quantity: 1, side: "buy" },
    });
    expect(buy2.ok()).toBeTruthy();

    const historyResp = await page.request.get("/api/portfolio/history");
    expect(historyResp.ok()).toBeTruthy();
    const history = (await historyResp.json()) as Array<{ total_value: number }>;
    expect(
      history.length,
      "expected >=2 portfolio_snapshots rows after two trades",
    ).toBeGreaterThanOrEqual(2);

    await page.reload();

    // Heatmap: at least one cell for our position, with plausible coloring.
    const cell = page.getByTestId(`heatmap-cell-${ticker}`);
    await expect(cell).toBeVisible({ timeout: 10_000 });

    const portfolio = await (await page.request.get("/api/portfolio")).json();
    const pos = portfolio.positions.find((p: { ticker: string }) => p.ticker === ticker);
    expect(pos).toBeTruthy();

    const rectFill = await cell.locator("rect").first().getAttribute("fill");
    expect(rectFill).toMatch(expectedFill(pos.unrealized_pnl_percent));

    // P&L chart: should have moved past the "Not enough history yet" empty
    // state and rendered an actual line chart.
    const pnlChart = page.getByTestId("pnl-chart");
    await expect(pnlChart.getByText("Not enough history yet.")).toHaveCount(0);
    await expect(pnlChart.locator(".recharts-line-curve")).toBeVisible({ timeout: 10_000 });
  });
});
