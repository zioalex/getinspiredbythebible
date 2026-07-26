import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import type { ReactElement } from "react";
import enMessages from "../../../messages/en.json";
import deMessages from "../../../messages/de.json";
import itMessages from "../../../messages/it.json";
import arMessages from "../../../messages/ar.json";
import zhMessages from "../../../messages/zh.json";

// Message catalogs keyed by locale, used to back the mocked server translator.
const catalogs: Record<string, typeof enMessages> = {
  en: enMessages,
  de: deMessages,
  it: itMessages,
  ar: arMessages,
  zh: zhMessages,
};

// Importing the server `page.tsx` transitively pulls in the "use client"
// ChatIsland island and its dependencies. We never render the island here,
// but its module graph must still resolve — mock the same client-only edges
// that page.test.tsx mocks so the import doesn't reach next/navigation, etc.
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <p>{children}</p>,
}));
vi.mock("@/lib/api", () => ({
  streamMessage: vi.fn(),
  getChapter: vi.fn(),
  getTranslations: vi.fn().mockResolvedValue([]),
  getBookNames: vi.fn().mockResolvedValue({}),
  submitFeedback: vi.fn(),
  generateSessionId: vi.fn().mockReturnValue("test-session-id"),
  getOrCreateSessionId: vi.fn().mockReturnValue("test-session-id"),
  resetSessionId: vi.fn(),
  ColdStartError: class ColdStartError extends Error {},
  ContentBlockedError: class ContentBlockedError extends Error {},
  SessionLimitError: class SessionLimitError extends Error {},
  checkBackendReady: vi.fn().mockResolvedValue(true),
  warmupBackend: vi.fn(),
  searchChurches: vi.fn(),
  submitContactForm: vi.fn(),
  InvalidContactEmailError: class InvalidContactEmailError extends Error {},
}));
vi.mock("@/lib/turnstile", () => ({
  useTurnstile: vi.fn(),
}));
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.PropsWithChildren) => (
    <a {...props}>{children}</a>
  ),
  redirect: vi.fn(),
  usePathname: vi.fn().mockReturnValue("/"),
  useRouter: vi.fn().mockReturnValue({ replace: vi.fn() }),
}));
vi.mock("@/i18n/routing", () => ({
  routing: { locales: ["en", "it", "de"], defaultLocale: "en" },
}));

// Mock next-intl/server so the server component resolves real per-locale
// strings without needing a running request context.
vi.mock("next-intl/server", () => ({
  setRequestLocale: vi.fn(),
  getTranslations: vi.fn(
    async ({
      locale,
      namespace,
    }: {
      locale: string;
      namespace: keyof typeof enMessages;
    }) => {
      const ns = catalogs[locale][namespace] as Record<string, string>;
      return (key: string) => ns[key];
    },
  ),
}));

// Import after the mock is registered. Home transitively imports the
// "use client" ChatIsland island, but we never render the island here — we
// only inspect the hero node the server component builds and hands to it.
import Home from "./page";

describe("server-rendered homepage hero (SEO)", () => {
  it("passes a heroContent node to the client island", async () => {
    const element = (await Home({
      params: Promise.resolve({ locale: "en" }),
    })) as ReactElement<{ heroContent?: React.ReactNode }>;

    expect(element.props.heroContent).toBeTruthy();
  });

  // The hero text must be present in the server output for every locale so
  // crawlers (and AI bots) get real, localized content instead of a thin
  // client shell — this is the core BITB-037 fix.
  it.each(["en", "de", "it", "ar", "zh"])(
    "renders the localized welcome heading and description for /%s",
    async (locale) => {
      const element = (await Home({
        params: Promise.resolve({ locale }),
      })) as ReactElement<{ heroContent: ReactElement }>;

      render(element.props.heroContent);

      const { heading, description } = catalogs[locale].Welcome as {
        heading: string;
        description: string;
      };
      expect(screen.getByText(heading)).toBeInTheDocument();
      expect(screen.getByText(description)).toBeInTheDocument();
    },
  );

  it("does not leak another locale's text into the hero", async () => {
    const element = (await Home({
      params: Promise.resolve({ locale: "de" }),
    })) as ReactElement<{ heroContent: ReactElement }>;

    render(element.props.heroContent);

    // German hero must not contain the English heading.
    expect(
      screen.queryByText(enMessages.Welcome.heading),
    ).not.toBeInTheDocument();
    expect(screen.getByText(deMessages.Welcome.heading)).toBeInTheDocument();
  });
});
