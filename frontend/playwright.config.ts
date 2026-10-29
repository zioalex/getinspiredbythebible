import { defineConfig, devices } from "@playwright/test";

/** Specs that run on every browser project, not just Chromium. */
const CROSS_BROWSER_SPECS = /read-aloud\.spec\.ts/;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    // Chromium (Chrome/Edge) runs every spec; it is what prod-browser-smoke.yml uses.
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    // BITB-250: the other engines only run the cross-browser read-aloud spec. The older specs
    // are Chromium-only (not verified on these engines), hence the project-level testMatch.
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
      testMatch: CROSS_BROWSER_SPECS,
    },
    {
      name: "webkit", // Safari (and every iOS browser)
      use: { ...devices["Desktop Safari"] },
      testMatch: CROSS_BROWSER_SPECS,
    },
    {
      name: "Mobile Safari",
      use: { ...devices["iPhone 13"] }, // WebKit with a touch phone viewport
      testMatch: CROSS_BROWSER_SPECS,
    },
  ],
  // Auto-start the production build only in CI (BITB-250): `next build` has to have run first.
  // Skipped when PLAYWRIGHT_BASE_URL is set (prod-browser-smoke.yml targets the deployed site)
  // and locally, where the config used to note Node version issues with auto-start; locally,
  // run `npm run build && npm start` yourself (see e2e/README.md).
  webServer:
    process.env.CI && !process.env.PLAYWRIGHT_BASE_URL
      ? {
          command: "npm run start",
          url: "http://localhost:3000",
          reuseExistingServer: false,
          timeout: 120_000,
        }
      : undefined,
});
