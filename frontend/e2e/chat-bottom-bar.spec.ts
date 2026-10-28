import { test, expect } from "@playwright/test";

// BITB-079: the chat page's footer links were rendered after a full-viewport
// (h-dvh) chat shell, so they were unreachable; a compact in-shell link row
// fixed that. #1224 then moved that row and "Get in Touch" into the main menu
// below the lg breakpoint (1024px), because they sat right where the thumb
// rests under the composer. Desktop keeps the in-shell row; on mobile/tablet
// the composer is the last thing on screen.

const DESKTOP_VIEWPORTS = [{ width: 1440, height: 900, label: "desktop" }];
const MOBILE_VIEWPORTS = [
  { width: 360, height: 640, label: "small mobile" },
  { width: 390, height: 844, label: "large mobile" },
  { width: 768, height: 1024, label: "tablet" },
];
const VIEWPORTS = [...MOBILE_VIEWPORTS, ...DESKTOP_VIEWPORTS];

test.describe("chat page bottom bar", () => {
  for (const vp of DESKTOP_VIEWPORTS) {
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
  }

  for (const vp of MOBILE_VIEWPORTS) {
    test(`composer is the last thing on screen at ${vp.label} (${vp.width}x${vp.height})`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/en");
      await page.waitForLoadState("networkidle");

      await expect(page.getByTestId("chat-footer-links")).toBeHidden();
      await expect(
        page.getByRole("button", { name: "Get in Touch" }),
      ).toBeHidden();

      const box = await page.getByRole("textbox").boundingBox();
      expect(box).not.toBeNull();
      // Only the input area's own bottom padding sits below the textarea.
      expect(vp.height - (box!.y + box!.height)).toBeLessThan(40);
    });

    test(`footer links and Get in Touch are in the main menu at ${vp.label}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/en");
      await page.waitForLoadState("networkidle");

      await page.getByRole("button", { name: "Menu" }).click();
      const panel = page.getByTestId("main-menu-panel");
      for (const name of ["Privacy", "Terms", "Changelog", "Get the app"]) {
        await expect(panel.getByRole("link", { name })).toBeVisible();
      }
      await panel.getByRole("button", { name: "Get in Touch" }).click();
      await expect(
        page.getByRole("dialog", { name: "Get in Touch" }),
      ).toBeVisible();
    });
  }

  for (const vp of VIEWPORTS) {
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

  test("Bible version and language selects fit inside the menu on small phones (#1223)", async ({
    page,
  }) => {
    for (const width of [320, 375, 430]) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto("/en");
      await page.waitForLoadState("networkidle");
      await page.getByRole("button", { name: "Menu" }).click();
      const panel = page.getByTestId("main-menu-panel");
      const panelBox = (await panel.boundingBox())!;
      for (const id of [
        "translation-switcher-control",
        "language-switcher-control",
      ]) {
        const box = (await panel.getByTestId(id).boundingBox())!;
        expect(box.x + box.width).toBeLessThanOrEqual(
          panelBox.x + panelBox.width + 0.5,
        );
        expect(box.x + box.width).toBeLessThanOrEqual(width);
      }
      const fontSize = await panel
        .locator("select")
        .first()
        .evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
      expect(fontSize).toBeGreaterThanOrEqual(16);
    }
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

  test("chat page renders without overflow in RTL (Arabic)", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/ar");
    await page.waitForLoadState("networkidle");

    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    // Below lg the links live in the main menu (#1224).
    await expect(page.getByTestId("chat-footer-links")).toBeHidden();

    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    expect(hasOverflow).toBe(false);
  });
});
