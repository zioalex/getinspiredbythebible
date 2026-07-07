import { test, expect } from "@playwright/test";

/**
 * Production browser smoke test (BITB-064).
 *
 * The full real user journey nothing else covers: a real Chromium browser loads
 * the deployed frontend, submits a chat message, and asserts a streamed
 * assistant reply renders — which exercises the rendered frontend → real
 * cross-origin CORS preflight → instrumented backend → SSE streaming, together.
 *
 * Run against production with:
 *   PLAYWRIGHT_BASE_URL=https://voxquieta.org \
 *   SMOKE_PROBE_SECRET=<secret> npm run test:e2e -- prod-chat-smoke.spec.ts
 *
 * Turnstile: a headless CI browser can't solve the invisible challenge, so the
 * test injects the smoke secret (window.__VOXQUIETA_SMOKE_SECRET__) via
 * addInitScript before navigation. api.ts then attaches it as
 * X-Monitor-Probe-Secret (backend bypasses Turnstile + rate limits) and the UI
 * relaxes the send gate. The secret exists only in this browser session — never
 * in the shipped bundle. Skipped unless SMOKE_PROBE_SECRET is set, so local
 * `npm run test:e2e` never hits production.
 */

const SMOKE_SECRET = process.env.SMOKE_PROBE_SECRET;

test.describe("production chat smoke", () => {
  test.skip(
    !SMOKE_SECRET,
    "SMOKE_PROBE_SECRET not set — skipping prod smoke test",
  );

  test("submitting a message streams an assistant reply", async ({ page }) => {
    // Inject the smoke secret before any app code runs.
    await page.addInitScript((secret) => {
      (
        window as unknown as { __VOXQUIETA_SMOKE_SECRET__?: string }
      ).__VOXQUIETA_SMOKE_SECRET__ = secret;
    }, SMOKE_SECRET);

    await page.goto("/en");

    const input = page.getByPlaceholder(/Share what's on your heart/i);
    await expect(input).toBeVisible({ timeout: 30_000 });
    await input.fill("What does John 3:16 say?");

    const submit = page.locator('form button[type="submit"]');
    await expect(submit).toBeEnabled({ timeout: 30_000 });
    await submit.click();

    // The streamed assistant reply must render with non-empty text. Generous
    // timeout to tolerate backend cold start.
    const assistant = page.getByTestId("assistant-message").last();
    await expect(assistant).toBeVisible({ timeout: 60_000 });
    await expect
      .poll(async () => (await assistant.innerText()).trim().length, {
        timeout: 60_000,
        message: "assistant reply never accrued streamed text",
      })
      .toBeGreaterThan(0);
  });
});
