import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import enMessages from "../../messages/en.json";

// Mock next-intl server functions used in server components
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn().mockImplementation(({ namespace }) => {
    const ns = enMessages[namespace as keyof typeof enMessages] as Record<
      string,
      string
    >;
    return Promise.resolve((key: string, params?: Record<string, string>) => {
      let value = ns?.[key] ?? key;
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          value = value.replace(`{${k}}`, v);
        });
      }
      return value;
    });
  }),
  setRequestLocale: vi.fn(),
}));

// Mock legalDocs to avoid fs/git calls in tests
vi.mock("@/lib/legalDocs", () => ({
  getLegalDocContent: vi.fn(
    (basename: string) =>
      `# ${basename === "privacy-policy" ? "Privacy Policy" : "Terms of Service"}\n\nTest content.`,
  ),
  getLegalDocDate: vi.fn(() => new Date("2026-04-20")),
}));

// Mock remark-gfm
vi.mock("remark-gfm", () => ({ default: () => {} }));

// Mock react-markdown to render children as plain text
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));

// Mock next-intl navigation
vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

// Minimal wrapper to provide intl context
function IntlWrapper({ children }: { children: React.ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("Privacy page", () => {
  it("renders the Privacy Policy heading from i18n", async () => {
    const { default: PrivacyPage } =
      await import("@/app/[locale]/privacy/page");
    const jsx = await PrivacyPage({
      params: Promise.resolve({ locale: "en" }),
    });
    render(<IntlWrapper>{jsx}</IntlWrapper>);
    expect(
      screen.getByRole("heading", { name: /privacy policy/i }),
    ).toBeTruthy();
  });
});

describe("Terms page", () => {
  it("renders the Terms of Service heading from i18n", async () => {
    const { default: TermsPage } = await import("@/app/[locale]/terms/page");
    const jsx = await TermsPage({ params: Promise.resolve({ locale: "en" }) });
    render(<IntlWrapper>{jsx}</IntlWrapper>);
    expect(
      screen.getByRole("heading", { name: /terms of service/i }),
    ).toBeTruthy();
  });
});
