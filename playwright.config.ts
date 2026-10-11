import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Allow environments without downloaded Playwright browsers to point
        // at a system Chromium, e.g. PLAYWRIGHT_CHROMIUM_PATH=/usr/bin/chromium
        launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH
          ? {
              executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH,
              // System Chromium builds may enforce Local Network Access checks
              // that block navigation to a local dev server; disable them for
              // local e2e runs only.
              args: ["--disable-features=LocalNetworkAccessChecks"],
            }
          : undefined,
      },
    },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run start -- --port 3100",
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
