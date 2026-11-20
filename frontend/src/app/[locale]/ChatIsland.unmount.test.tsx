import "fake-indexeddb/auto";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import Home from "./ChatIsland";
import enMessages from "../../../messages/en.json";
import { streamMessage } from "@/lib/api";
import { saveFullConversation } from "@/lib/conversationStore";

// BITB-340: the auto-save effect's IndexedDB write can settle after the island
// unmounts (navigation, or jsdom teardown in CI). Its `.then` must not call
// setState then: React reads `window.event` in requestUpdateLane, so after
// teardown the update throws "window is not defined" as an unhandled rejection.
Element.prototype.scrollIntoView = vi.fn();

vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <p>{children}</p>,
  defaultUrlTransform: (url: string) => url,
}));

vi.mock("@/lib/conversationStore", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/conversationStore")>();
  return {
    ...actual,
    listConversations: vi.fn().mockResolvedValue([]),
    saveFullConversation: vi.fn(),
  };
});

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    streamMessage: vi.fn(),
    getChapter: vi.fn(),
    getTranslations: vi.fn().mockResolvedValue([]),
    submitFeedback: vi.fn(),
    getOrCreateSessionId: vi.fn().mockReturnValue("test-session-id"),
    resetSessionId: vi.fn().mockReturnValue("test-session-id-2"),
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

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.PropsWithChildren) => (
    <a {...props}>{children}</a>
  ),
  redirect: vi.fn(),
  usePathname: vi.fn().mockReturnValue("/"),
  useRouter: vi.fn().mockReturnValue({ replace: vi.fn() }),
}));

vi.mock("@/i18n/routing", () => ({
  routing: { locales: ["en"], defaultLocale: "en" },
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

describe("ChatIsland auto-save after unmount (BITB-340)", () => {
  beforeEach(() => {
    vi.mocked(streamMessage).mockReset();
    vi.mocked(saveFullConversation).mockReset();
  });

  it("does not update state when a pending history save settles after unmount", async () => {
    // Every save stays pending until the test releases it.
    const releases: Array<() => void> = [];
    vi.mocked(saveFullConversation).mockImplementation(
      () => new Promise<void>((resolve) => releases.push(resolve)),
    );
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield { type: "metadata", message_id: "m1", provider: "p", model: "m" };
      yield { type: "content", content: "Peace be with you." };
      yield { type: "completion", verses_cited: [] };
    });

    const { unmount } = render(
      <NextIntlClientProvider locale="en" messages={enMessages}>
        <Home />
      </NextIntlClientProvider>,
    );
    const box = await screen.findByPlaceholderText(
      enMessages.Chat.inputPlaceholder,
    );
    fireEvent.change(box, { target: { value: "hello" } });
    fireEvent.submit(box.closest("form")!);
    await screen.findByText("Peace be with you.");
    await waitFor(() => expect(saveFullConversation).toHaveBeenCalled());

    unmount();
    // Let React's scheduler finish any unmount work before `window` goes away.
    await new Promise((r) => setTimeout(r, 20));

    // Simulate jsdom teardown: `window` is gone when the save settles, as in
    // the CI failure. Any setState now throws inside the `.then`. `window` is
    // removed only across microtasks so no scheduler macrotask sees it gone.
    const unhandled: unknown[] = [];
    const onUnhandled = (e: unknown) => unhandled.push(e);
    process.on("unhandledRejection", onUnhandled);
    const g = globalThis as { window?: unknown };
    const savedWindow = g.window;
    try {
      delete g.window;
      releases.forEach((release) => release());
      for (let i = 0; i < 10; i++) await Promise.resolve();
    } finally {
      g.window = savedWindow;
    }
    try {
      await new Promise((r) => setTimeout(r, 20));
    } finally {
      process.off("unhandledRejection", onUnhandled);
    }

    expect(unhandled).toEqual([]);
  });
});
