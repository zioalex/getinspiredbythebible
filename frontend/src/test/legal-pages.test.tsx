import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { existsSync, readFileSync } from "fs";
import { join } from "path";
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

// Verify that a localized file exists for every non-English locale so the
// legal pages never silently fall back to English for a translated locale.
const legalDir = join(process.cwd(), "public", "legal");
const nonEnglishLocales = [
  "ar",
  "de",
  "es",
  "fr",
  "hi",
  "it",
  "ko",
  "pt",
  "ru",
  "zh",
];

describe("Localized legal documents", () => {
  for (const locale of nonEnglishLocales) {
    it(`privacy-policy.${locale}.md exists`, () => {
      expect(existsSync(join(legalDir, `privacy-policy.${locale}.md`))).toBe(
        true,
      );
    });

    it(`terms-of-service.${locale}.md exists`, () => {
      expect(existsSync(join(legalDir, `terms-of-service.${locale}.md`))).toBe(
        true,
      );
    });
  }
});

// BITB-309: the policy must name OpenAI (moderation fallback) and state its
// 30-day abuse-monitoring retention honestly, in every language.
describe("privacy policy discloses OpenAI moderation (BITB-309)", () => {
  const allLocales = ["en", ...nonEnglishLocales];
  const OPENAI_URL = "https://openai.com/enterprise-privacy/";

  for (const locale of allLocales) {
    const file =
      locale === "en" ? "privacy-policy.md" : `privacy-policy.${locale}.md`;
    const raw = readFileSync(join(legalDir, file), "utf8");

    describe(locale, () => {
      it("has lastUpdated >= 2026-11-11", () => {
        const m = raw.match(/^lastUpdated:\s*(\d{4}-\d{2}-\d{2})\s*$/m);
        expect(m).not.toBeNull();
        expect(m![1] >= "2026-11-11").toBe(true);
      });

      it("links OpenAI privacy page in prose and table", () => {
        expect(raw.split(OPENAI_URL).length - 1).toBeGreaterThanOrEqual(2);
      });

      it("still links OpenRouter and Microsoft", () => {
        expect(raw).toContain("https://openrouter.ai/privacy");
        expect(raw).toContain("https://privacy.microsoft.com");
      });

      it("states the 30-day retention in the paragraph with the OpenAI link", () => {
        const paragraph = raw
          .split(/\n\s*\n/)
          .find((p) => p.includes(OPENAI_URL) && !p.startsWith("|"));
        expect(paragraph).toBeDefined();
        expect(paragraph).toContain("30");
      });

      it("has an OpenAI row in the third-party table", () => {
        expect(raw).toMatch(/^\|\s*OpenAI\s*\|/m);
      });
    });
  }

  it("en: the old blanket no-retention claim is gone", () => {
    const raw = readFileSync(join(legalDir, "privacy-policy.md"), "utf8");
    expect(raw).not.toContain("not retained by the provider beyond");
  });
});
