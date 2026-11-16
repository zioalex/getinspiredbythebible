import "fake-indexeddb/auto";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import Home from "./ChatIsland";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { resetSessionId } from "@/lib/api";
import {
  clearAll,
  __resetDbCache,
  listConversations,
  saveFullConversation,
  saveConversation,
  latestConversationForLanguage,
  markFreshChat,
  consumeFreshChat,
  FRESH_CHAT_FLAG,
} from "@/lib/conversationStore";

// BITB-331: changing the UI language starts a new chat; reload resumes only
// the latest chat held in the active language.
Element.prototype.scrollIntoView = vi.fn();

const LOCALES = [
  "en",
  "it",
  "de",
  "es",
  "fr",
  "pt",
  "ar",
  "ru",
  "zh",
  "hi",
  "ko",
] as const;

const { mockReplace } = vi.hoisted(() => ({ mockReplace: vi.fn() }));

vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <p>{children}</p>,
  defaultUrlTransform: (url: string) => url,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    streamMessage: vi.fn(),
    finalizeMessage: vi.fn(),
    getChapter: vi.fn(),
    getTranslations: vi.fn().mockResolvedValue([]),
    submitFeedback: vi.fn(),
    getOrCreateSessionId: vi.fn().mockReturnValue("test-session-id"),
    resetSessionId: vi.fn().mockReturnValue("rotated-session-id"),
    checkBackendReady: vi.fn().mockResolvedValue(true),
    warmupBackend: vi.fn((onReady: () => void) => {
      onReady();
    }),
    getBookNames: vi.fn().mockResolvedValue({
      localized_to_english: {},
      multi_word_names: [],
    }),
  };
});

vi.mock("@/lib/featureFlags", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/featureFlags")>()),
  followUpsEnabled: () => true,
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.PropsWithChildren) => (
    <a {...props}>{children}</a>
  ),
  redirect: vi.fn(),
  usePathname: vi.fn().mockReturnValue("/"),
  useRouter: vi.fn().mockReturnValue({ replace: mockReplace }),
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

async function renderIn(locale: string) {
  const messages = (await import(`../../../messages/${locale}.json`)).default;
  return render(
    <NextIntlClientProvider locale={locale} messages={messages}>
      <Home />
    </NextIntlClientProvider>,
  );
}

const MSGS = (q: string) => [
  { role: "user" as const, content: q },
  { role: "assistant" as const, content: `Reply to ${q}` },
];

describe.each(LOCALES)("ChatIsland language-scoped chat [%s]", (locale) => {
  beforeEach(async () => {
    window.localStorage.clear();
    sessionStorage.clear();
    vi.mocked(resetSessionId).mockClear();
    mockReplace.mockClear();
    __resetDbCache();
    await clearAll();
  });

  it("reload resumes the latest chat in the active language only", async () => {
    const other = locale === "en" ? "it" : "en";
    await saveFullConversation("same-old", "t", MSGS("same-old"), locale);
    await new Promise((r) => setTimeout(r, 5));
    await saveFullConversation("same-new", "t", MSGS("same-new"), locale);
    await new Promise((r) => setTimeout(r, 5));
    // Newest overall, but in a different language: must NOT be resumed.
    await saveFullConversation("other-lang", "t", MSGS("other-lang"), other);

    await renderIn(locale);
    await screen.findByText("same-new");
    expect(screen.queryByText("other-lang")).toBeNull();
    expect(screen.queryByText("same-old")).toBeNull();
  });

  it("never auto-resumes legacy rows without a language", async () => {
    await saveFullConversation("legacy", "t", MSGS("legacy-chat")); // no language
    await renderIn(locale);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("legacy-chat")).toBeNull();
    // ...but the legacy chat is still stored (reachable from history).
    expect((await listConversations()).map((c) => c.id)).toContain("legacy");
  });

  it("language switch opens an empty chat with a rotated session id", async () => {
    await saveFullConversation("prev", "t", MSGS("prev-chat"), locale);
    markFreshChat(); // what LanguageSwitcher / suggestion banner do
    await renderIn(locale);
    await waitFor(() => expect(resetSessionId).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("prev-chat")).toBeNull();
    // One-shot: flag consumed, old chat remains in the list.
    expect(sessionStorage.getItem(FRESH_CHAT_FLAG)).toBeNull();
    expect((await listConversations()).map((c) => c.id)).toEqual(["prev"]);
  });

  it("LanguageSwitcher marks a fresh chat when the locale changes", async () => {
    const target = locale === "en" ? "it" : "en";
    const messages = (await import(`../../../messages/${locale}.json`)).default;
    render(
      <NextIntlClientProvider locale={locale} messages={messages}>
        <LanguageSwitcher />
      </NextIntlClientProvider>,
    );
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: target },
    });
    expect(mockReplace).toHaveBeenCalledWith("/", { locale: target });
    expect(sessionStorage.getItem(FRESH_CHAT_FLAG)).toBe("1");
  });
});

describe("conversationStore language helpers (BITB-331)", () => {
  beforeEach(async () => {
    sessionStorage.clear();
    __resetDbCache();
    await clearAll();
  });

  it("latestConversationForLanguage ignores legacy and other-language rows", async () => {
    await saveConversation({
      id: "legacy",
      title: "x",
      createdAt: 1,
      updatedAt: 900,
    });
    await saveConversation({
      id: "fr1",
      title: "x",
      createdAt: 1,
      updatedAt: 100,
      language: "fr",
    });
    await saveConversation({
      id: "de1",
      title: "x",
      createdAt: 1,
      updatedAt: 800,
      language: "de",
    });
    expect((await latestConversationForLanguage("fr"))?.id).toBe("fr1");
    expect(await latestConversationForLanguage("ko")).toBeNull();
  });

  it("consumeFreshChat is one-shot", () => {
    expect(consumeFreshChat()).toBe(false);
    markFreshChat();
    expect(consumeFreshChat()).toBe(true);
    expect(consumeFreshChat()).toBe(false);
  });

  it("a later save without a language keeps the stored language", async () => {
    await saveFullConversation("c", "t", MSGS("a"), "ko");
    await saveFullConversation("c", "t", MSGS("b"));
    expect((await listConversations())[0].language).toBe("ko");
  });
});
