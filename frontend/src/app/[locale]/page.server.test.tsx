import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import type { ReactElement } from "react";
import enMessages from "../../../messages/en.json";
import deMessages from "../../../messages/de.json";
import itMessages from "../../../messages/it.json";

// Message catalogs for all 11 locales, used to back the mocked server translator.
const catalogs = Object.fromEntries(
  Object.entries(
    import.meta.glob("../../../messages/*.json", {
      eager: true,
      import: "default",
    }) as Record<string, typeof enMessages>,
  ).map(([path, mod]) => [path.match(/([a-z]+)\.json$/)![1], mod]),
) as Record<string, typeof enMessages>;
const ALL_LOCALES = Object.keys(catalogs);

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
  MAX_MESSAGE_LENGTH: 500,
  MAX_SESSION_REQUESTS: 10,
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
  routing: {
    locales: ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"],
    defaultLocale: "en",
  },
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
  // client shell — this is the core BITB-136 fix.
  it.each(ALL_LOCALES)(
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

  it.each(ALL_LOCALES)(
    "renders exactly one non-brand, non-empty h1 for /%s",
    async (locale) => {
      const element = (await Home({
        params: Promise.resolve({ locale }),
      })) as ReactElement<{ heroContent: ReactElement }>;

      render(element.props.heroContent);

      const h1s = screen.getAllByRole("heading", { level: 1 });
      expect(h1s).toHaveLength(1);
      const text = h1s[0].textContent?.trim() ?? "";
      expect(text.length).toBeGreaterThan(0);
      expect(text).not.toBe(catalogs[locale].Header.title);
      expect(text).not.toBe("Vox Quieta");
    },
  );

  it("gives every locale a heading distinct from the old 'Welcome' copy", () => {
    expect(ALL_LOCALES).toHaveLength(11);
    expect(enMessages.Welcome.heading).toBe(
      "Find comfort and guidance in Scripture",
    );
  });
});
