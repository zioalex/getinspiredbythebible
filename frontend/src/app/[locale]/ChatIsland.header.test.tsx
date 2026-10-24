import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import Home from "./ChatIsland";
import enMessages from "../../../messages/en.json";
import itMessages from "../../../messages/it.json";
import deMessages from "../../../messages/de.json";
import esMessages from "../../../messages/es.json";
import frMessages from "../../../messages/fr.json";
import ptMessages from "../../../messages/pt.json";
import arMessages from "../../../messages/ar.json";
import ruMessages from "../../../messages/ru.json";
import zhMessages from "../../../messages/zh.json";
import hiMessages from "../../../messages/hi.json";
import koMessages from "../../../messages/ko.json";

// BITB-219: the sticky header must not overflow on ~360-412px phones.
Element.prototype.scrollIntoView = vi.fn();

vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <p>{children}</p>,
  defaultUrlTransform: (url: string) => url,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    streamMessage: vi.fn(),
    getChapter: vi.fn(),
    getTranslations: vi.fn().mockResolvedValue([]),
    submitFeedback: vi.fn(),
    generateSessionId: vi.fn().mockReturnValue("test-session-id"),
    getOrCreateSessionId: vi.fn().mockReturnValue("test-session-id"),
    resetSessionId: vi.fn().mockReturnValue("test-session-id-2"),
    ColdStartError: class ColdStartError extends Error {},
    SessionLimitError: actual.SessionLimitError,
    MAX_MESSAGE_LENGTH: 500,
    MAX_SESSION_REQUESTS: 10,
    checkBackendReady: vi.fn().mockResolvedValue(true),
    warmupBackend: vi.fn((onReady: () => void) => {
      onReady();
    }),
    searchChurches: vi.fn(),
    submitContactForm: vi.fn(),
    InvalidContactEmailError: class InvalidContactEmailError extends Error {},
    getBookNames: vi.fn().mockResolvedValue({
      localized_to_english: {},
      multi_word_names: [],
    }),
  };
});

vi.mock("@/lib/verseExtraction", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/verseExtraction")>();
  return {
    extractVerseReferences: actual.extractVerseReferences,
    isVerseReferenced: actual.isVerseReferenced,
    LOCALIZED_BOOK_TO_ENGLISH: actual.LOCALIZED_BOOK_TO_ENGLISH,
    isKnownBook: actual.isKnownBook,
    normalizeDigits: actual.normalizeDigits,
    updateBookNames: actual.updateBookNames,
  };
});

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

vi.mock("@/lib/turnstile", () => ({
  useTurnstile: vi.fn(() => ({
    isReady: true,
    isEnabled: false,
    token: null,
    configLoaded: true,
    refreshToken: vi.fn(),
    awaitToken: vi.fn().mockResolvedValue(null),
  })),
}));

const LOCALES: Record<string, typeof enMessages> = {
  en: enMessages,
  it: itMessages,
  de: deMessages,
  es: esMessages,
  fr: frMessages,
  pt: ptMessages,
  ar: arMessages,
  ru: ruMessages,
  zh: zhMessages,
  hi: hiMessages,
  ko: koMessages,
};

describe("ChatIsland header responsive layout (BITB-219)", () => {
  it.each(Object.keys(LOCALES))(
    "keeps Bible chip and New chat reachable on mobile (%s)",
    async (locale) => {
      const messages = LOCALES[locale];
      render(
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Home />
        </NextIntlClientProvider>,
      );

      // Header language switcher hidden below sm, flex from sm up
      const switcher = screen.getByTestId("header-language-switcher");
      expect(switcher).toHaveClass("hidden", "sm:flex");

      // New chat has an accessible name even though its text label is hidden
      const newChat = screen.getByRole("button", {
        name: messages.Header.newChat,
      });
      expect(newChat).toBeInTheDocument();
      expect(newChat).toHaveClass("px-2", "sm:px-3");

      // Bible version select is rendered
      expect(
        screen.getByLabelText(messages.Header.bibleVersion),
      ).toBeInTheDocument();

      // Right control group never shrinks
      expect(newChat.parentElement).toHaveClass("shrink-0");

      // Title stays on one line
      const h1 = screen.getByRole("heading", { level: 1 });
      expect(h1).toHaveClass("truncate");
      // Latin brand truncates from its end even in RTL locales (ar)
      expect(h1).toHaveAttribute("dir", "ltr");

      await waitFor(() => expect(screen.getByRole("main")).toBeInTheDocument());
    },
  );
});
