import { test, expect } from "@playwright/test";

// BITB-079: the chat page's footer links were rendered after a full-viewport
// (h-dvh) chat shell, so they existed in the DOM but were never reachable
// without a document-level scroll the chat page's own internal scrolling
// swallows. These specs assert the compact in-shell link row is on screen
// without any scrolling, at representative mobile and desktop viewports.

const VIEWPORTS = [
  { width: 360, height: 640, label: "small mobile" },
  { width: 390, height: 844, label: "large mobile" },
  { width: 768, height: 1024, label: "tablet" },
  { width: 1440, height: 900, label: "desktop" },
];

test.describe("chat page bottom bar", () => {
  for (const vp of VIEWPORTS) {
    test(`footer links are on screen at ${vp.label} (${vp.width}x${vp.height}) without scrolling`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/en");
      await page.waitForLoadState("networkidle");

      const privacyLink = page
        .getByTestId("chat-footer-links")
        .getByRole("link", { name: "Privacy" });
      await expect(privacyLink).toBeVisible();

      const box = await privacyLink.boundingBox();
      expect(box).not.toBeNull();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.y).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(vp.width + 1);
      expect(box!.y + box!.height).toBeLessThanOrEqual(vp.height + 1);
    });

    test(`no horizontal overflow at ${vp.label} (${vp.width}x${vp.height})`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/en");
      await page.waitForLoadState("networkidle");

      const hasOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth + 1,
      );
      expect(hasOverflow).toBe(false);
    });
  }

  test("composer and footer links are both fully visible on a small phone", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await page.goto("/en");
    await page.waitForLoadState("networkidle");

    const textarea = page.getByRole("textbox");
    const textareaBox = await textarea.boundingBox();
    expect(textareaBox).not.toBeNull();
    expect(textareaBox!.y + textareaBox!.height).toBeLessThanOrEqual(641);

    const linksBox = await page
      .getByTestId("chat-footer-links")
      .boundingBox();
    expect(linksBox).not.toBeNull();
    expect(linksBox!.y + linksBox!.height).toBeLessThanOrEqual(641);
  });

  test("composer stays visible when the viewport shrinks (mobile keyboard proxy)", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await page.goto("/en");
    await page.waitForLoadState("networkidle");

    // A real on-screen keyboard shrinks the visual viewport; approximate it
    // by shrinking the viewport itself. Real iOS Safari / Android Chrome
    // keyboard behavior still needs manual verification per the story.
    await page.setViewportSize({ width: 360, height: 360 });

    const textarea = page.getByRole("textbox");
    await expect(textarea).toBeVisible();
    const box = await textarea.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.y + box!.height).toBeLessThanOrEqual(361);
  });

  test("no duplicate footer is rendered on the chat page, and the page footer still renders elsewhere", async ({
    page,
  }) => {
    await page.goto("/en");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("footer")).toHaveCount(0);

    await page.goto("/en/privacy");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("footer")).toHaveCount(1);
  });

  test("footer links render correctly in RTL (Arabic)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/ar");
    await page.waitForLoadState("networkidle");

    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByTestId("chat-footer-links")).toBeVisible();

    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    expect(hasOverflow).toBe(false);
  });
});
