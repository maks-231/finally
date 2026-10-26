import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the FinAlly E2E suite (PLAN.md §12).
 *
 * The suite targets a single already-running app container (see
 * docker-compose.test.yml / README in this directory for how to start it).
 * BASE_URL defaults to the app's exposed port on localhost.
 */
const BASE_URL = process.env.BASE_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./tests",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
