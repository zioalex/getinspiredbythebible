/**
 * BITB-102 — offline shell / service worker Playwright spec.
 *
 * NOT wired into any CI gate (see AGENTS.md / frontend/e2e/ — only
 * prod-chat-smoke.spec.ts is invoked by name in prod-browser-smoke.yml).
 * Registration is production-only (see registerServiceWorker.ts), so this
 * spec requires a production build running locally:
 *
 *   npm run build && npm start
 *   npx playwright test e2e/offline-shell.spec.ts
 *
 * Running it against `npm run dev` will hang waiting for a controller that
 * never arrives, since dev mode actively unregisters any service worker.
 */
import { test, expect } from "@playwright/test";

async function waitForServiceWorkerController(
  page: import("@playwright/test").Page,
) {
  await page.waitForFunction(
    () => !!navigator.serviceWorker?.controller,
    undefined,
    { timeout: 15000 },
  );
}

test.describe("Offline shell (BITB-102)", () => {
  test("shows the localized offline fallback in English when offline", async ({
    page,
    context,
  }) => {
    await page.goto("/en");
    await waitForServiceWorkerController(page);

    await context.setOffline(true);
    await page.reload();

    await expect(page.locator("#vq-offline-title")).toBeVisible();
    await expect(page.locator("#vq-offline-title")).toHaveText(
      "You're offline",
    );

    await context.setOffline(false);
  });

  test("shows the Italian offline fallback string when offline on /it", async ({
    page,
    context,
  }) => {
    await page.goto("/it");
    await waitForServiceWorkerController(page);

    await context.setOffline(true);
    await page.reload();

    await expect(page.locator("#vq-offline-title")).toHaveText("Sei offline");

    await context.setOffline(false);
  });

  test("renders right-to-left on /ar when offline", async ({
    page,
    context,
  }) => {
    await page.goto("/ar");
    await waitForServiceWorkerController(page);

    await context.setOffline(true);
    await page.reload();

    await expect(page.locator("#vq-offline-title")).toBeVisible();
    const dir = await page.evaluate(() => document.documentElement.dir);
    expect(dir).toBe("rtl");

    await context.setOffline(false);
  });
});
