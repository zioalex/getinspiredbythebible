import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import enMessages from "../../../../messages/en.json";

const mockHeaders = vi.fn();

vi.mock("next/headers", () => ({
  headers: () => mockHeaders(),
}));

vi.mock("next-intl/server", () => ({
  setRequestLocale: vi.fn(),
  getTranslations: vi.fn(async ({ namespace }: { namespace: "App" }) => {
    const ns = enMessages[namespace] as Record<string, string>;
    return (key: string) => ns[key];
  }),
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.PropsWithChildren) => (
    <a {...props}>{children}</a>
  ),
}));

vi.mock("@/i18n/routing", () => ({
  routing: { locales: ["en"] },
}));

vi.mock("@/lib/testerLinks", () => ({
  PLAY_STORE_URL: "https://play.google.com/store/apps/details?id=test",
}));

import AppStoryPage from "./page";

function createMockHeaders(userAgent: string | null) {
  return {
    get: (name: string) => (name === "user-agent" ? userAgent : null),
  };
}

const IPHONE_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";

const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36";

describe("AppStoryPage", () => {
  it("shows the iOS Add to Home Screen instructions and no Play Store link for an iPhone user agent", async () => {
    mockHeaders.mockResolvedValue(createMockHeaders(IPHONE_UA));

    const jsx = await AppStoryPage({
      params: Promise.resolve({ locale: "en" }),
    });
    render(jsx);

    expect(screen.getByText(enMessages.App.iosCtaTitle)).toBeInTheDocument();
    expect(screen.getByText(enMessages.App.iosCtaBody)).toBeInTheDocument();
    expect(screen.getByText(enMessages.App.iosCtaSub)).toBeInTheDocument();

    expect(
      screen.queryByText(enMessages.App.ctaButton),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /google play/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/app store/i)).not.toBeInTheDocument();
  });

  it("shows the Play Store CTA for a non-iOS (Android) user agent", async () => {
    mockHeaders.mockResolvedValue(createMockHeaders(ANDROID_UA));

    const jsx = await AppStoryPage({
      params: Promise.resolve({ locale: "en" }),
    });
    render(jsx);

    const link = screen.getByText(enMessages.App.ctaButton);
    expect(link.closest("a")).toHaveAttribute(
      "href",
      "https://play.google.com/store/apps/details?id=test",
    );

    expect(
      screen.queryByText(enMessages.App.iosCtaTitle),
    ).not.toBeInTheDocument();
  });

  it("falls back to the Play Store CTA when there is no user-agent header", async () => {
    mockHeaders.mockResolvedValue(createMockHeaders(null));

    const jsx = await AppStoryPage({
      params: Promise.resolve({ locale: "en" }),
    });
    render(jsx);

    expect(screen.getByText(enMessages.App.ctaButton)).toBeInTheDocument();
    expect(
      screen.queryByText(enMessages.App.iosCtaTitle),
    ).not.toBeInTheDocument();
  });
});
