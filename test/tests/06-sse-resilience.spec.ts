import { test, expect } from "@playwright/test";
import { execSync } from "node:child_process";

// PLAN.md §12 scenario 7: "SSE resilience" — disconnect and verify the
// client reconnects, and the connection-status indicator reflects state
// changes.
//
// We first tried Playwright's `context.setOffline(true)` (the natural
// browser-level way to simulate a dropped connection), but empirically it
// does NOT interrupt an already-open EventSource/SSE stream in Chromium:
// the existing HTTP response keeps delivering chunks and the UI stays
// "connected" throughout (verified directly — AAPL's price cell kept
// ticking with offline=true). This matches a documented CDP limitation:
// `Network.emulateNetworkConditions`/offline primarily blocks *new*
// request dispatch, not bytes already flowing on an established streaming
// response.
//
// So, per the task brief's suggested fallback, we disrupt the *container's*
// network instead: `docker network disconnect/connect` on the running app
// container severs the actual TCP connection carrying the SSE stream,
// which reliably drives EventSource's onerror -> auto-retry -> onopen
// lifecycle that the connection-status dot is derived from
// (frontend/src/hooks/usePriceStream.ts).
//
// Requires CONTAINER_NAME (the running app container's name) and docker
// access from wherever `playwright test` runs. Skips gracefully if either
// is unavailable (e.g. when run via the docker-compose.test.yml path, where
// the Playwright test runner is itself inside a container without a docker
// socket mounted — see test/README in this directory).

const CONTAINER_NAME = process.env.APP_CONTAINER_NAME ?? "finally-e2e";

function dockerAvailable(): boolean {
  try {
    execSync(`docker inspect ${CONTAINER_NAME}`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

test.describe("SSE resilience", () => {
  test.skip(!dockerAvailable(), `docker/${CONTAINER_NAME} not reachable from the test runner`);

  test("connection-status reflects disconnect and recovers on reconnect", async ({ page }) => {
    await page.goto("/");

    const status = page.getByTestId("connection-status");
    await expect(status).toHaveAttribute("data-state", "connected", { timeout: 10_000 });

    // Sever the container's network, forcing the open SSE TCP connection to
    // actually drop (verified: context.setOffline alone does not do this).
    execSync(`docker network disconnect bridge ${CONTAINER_NAME}`);
    try {
      // EventSource's native auto-retry puts readyState into CONNECTING (not
      // CLOSED) while it can't reach the server; usePriceStream maps that to
      // "reconnecting".
      await expect(status).toHaveAttribute("data-state", "reconnecting", { timeout: 20_000 });

      // Prices should stop advancing while the connection is down.
      const frozen = await page.getByTestId("price-cell-AAPL").textContent();
      await page.waitForTimeout(3000);
      const stillFrozen = await page.getByTestId("price-cell-AAPL").textContent();
      expect(stillFrozen).toBe(frozen);
    } finally {
      // Always restore the network, even if an assertion above failed.
      execSync(`docker network connect bridge ${CONTAINER_NAME}`);
    }

    // EventSource should reconnect on its own once the network is back.
    await expect(status).toHaveAttribute("data-state", "connected", { timeout: 20_000 });

    // And prices should resume streaming.
    const resumed1 = await page.getByTestId("price-cell-AAPL").textContent();
    await page.waitForTimeout(4000);
    const resumed2 = await page.getByTestId("price-cell-AAPL").textContent();
    expect(resumed2).not.toBe(resumed1);
  });
});
