import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import enMessages from "../../../../messages/en.json";

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

// The page no longer branches on the User-Agent itself (that moved
// client-side into AppInstallCta, see AppInstallCta.test.tsx for the
// iOS-vs-non-iOS behavioral coverage) — this page just needs to render the
// component with the right translated strings, as a fully static server
// component (no `headers()` call, so it can stay prerendered).
vi.mock("@/components/AppInstallCta", () => ({
  default: (props: Record<string, string>) => (
    <div data-testid="app-install-cta">{JSON.stringify(props)}</div>
  ),
}));

import AppStoryPage from "./page";

describe("AppStoryPage", () => {
  it("renders as a static page and passes the translated CTA strings to AppInstallCta", async () => {
    const jsx = await AppStoryPage({
      params: Promise.resolve({ locale: "en" }),
    });
    render(jsx);

    expect(screen.getByText(enMessages.App.title)).toBeInTheDocument();

    const cta = screen.getByTestId("app-install-cta");
    const props = JSON.parse(cta.textContent ?? "{}");
    expect(props).toEqual({
      iconAlt: enMessages.App.iconAlt,
      ctaSub: enMessages.App.ctaSub,
      ctaButton: enMessages.App.ctaButton,
      iosCtaTitle: enMessages.App.iosCtaTitle,
      iosCtaBody: enMessages.App.iosCtaBody,
      iosCtaSub: enMessages.App.iosCtaSub,
      playStoreUrl: "https://play.google.com/store/apps/details?id=test",
    });
  });
});
