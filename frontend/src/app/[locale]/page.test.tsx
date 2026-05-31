import { screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Home from "./page";
import * as api from "@/lib/api";
import * as turnstile from "@/lib/turnstile";
import { renderWithIntl } from "@/test/i18n-helpers";

// Mock scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

// Mock react-markdown to simplify rendering
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <p>{children}</p>,
}));

// Mock the API module
vi.mock("@/lib/api", () => ({
  streamMessage: vi.fn(),
  getChapter: vi.fn(),
  getTranslations: vi.fn().mockResolvedValue([]),
  submitFeedback: vi.fn(),
  generateSessionId: vi.fn().mockReturnValue("test-session-id"),
  getOrCreateSessionId: vi.fn().mockReturnValue("test-session-id"),
  ColdStartError: class ColdStartError extends Error {},
  checkBackendReady: vi.fn().mockResolvedValue(true),
  warmupBackend: vi.fn((onReady: () => void) => {
    onReady();
  }),
  searchChurches: vi.fn(),
  submitContactForm: vi.fn(),
}));

// Use real verse extraction logic for proper testing
vi.mock("@/lib/verseExtraction", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/verseExtraction")>();
  return {
    extractVerseReferences: actual.extractVerseReferences,
    isVerseReferenced: actual.isVerseReferenced,
    LOCALIZED_BOOK_TO_ENGLISH: actual.LOCALIZED_BOOK_TO_ENGLISH,
  };
});

// Hoisted mock for router.replace so individual tests can assert on it
const { mockRouterReplace } = vi.hoisted(() => ({
  mockRouterReplace: vi.fn(),
}));

// Mock i18n navigation (used by LanguageSwitcher and page.tsx)
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.PropsWithChildren) => (
    <a {...props}>{children}</a>
  ),
  redirect: vi.fn(),
  usePathname: vi.fn().mockReturnValue("/"),
  useRouter: vi.fn().mockReturnValue({ replace: mockRouterReplace }),
}));

// Mock i18n routing
vi.mock("@/i18n/routing", () => ({
  routing: { locales: ["en", "it", "de"], defaultLocale: "en" },
}));

// Mock Turnstile hook
vi.mock("@/lib/turnstile", () => ({
  useTurnstile: vi.fn(),
}));

// Helper to render Home with verses pre-loaded via the API mock
async function renderHomeWithVerses() {
  vi.mocked(api.streamMessage).mockImplementation(async function* () {
    yield {
      type: "metadata" as const,
      message_id: "msg-1",
      scripture_context: {
        query: "Tell me about love",
        verses: [
          {
            book: "John",
            chapter: 3,
            verse: 16,
            text: "For God so loved the world...",
            reference: "John 3:16",
            similarity: 0.9,
          },
          {
            book: "Romans",
            chapter: 8,
            verse: 28,
            text: "And we know that all things work together...",
            reference: "Romans 8:28",
            similarity: 0.7,
          },
        ],
        passages: [],
      },
      provider: "test",
      model: "test-model",
    };
    yield {
      type: "content" as const,
      content:
        "Here are verses for you: John 3:16 says God so loved the world, and Romans 8:28 reminds us all things work together.",
    };
  });

  const result = renderWithIntl(<Home />);

  // Type a message and submit to trigger verse loading
  const input = screen.getByPlaceholderText("Share what's on your heart...");
  await act(async () => {
    fireEvent.change(input, { target: { value: "Tell me about love" } });
  });
  const submitButton = result.container.querySelector('button[type="submit"]');
  await act(async () => {
    fireEvent.click(submitButton!);
  });

  // Wait for the API response to be processed
  await waitFor(() => {
    expect(
      screen.getByText(
        "Here are verses for you: John 3:16 says God so loved the world, and Romans 8:28 reminds us all things work together.",
      ),
    ).toBeInTheDocument();
  });

  return result;
}

describe("Home page responsive layout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Re-setup mocks that are needed for every render
    vi.mocked(api.warmupBackend).mockImplementation((onReady: () => void) => {
      onReady();
    });
    vi.mocked(api.getTranslations).mockResolvedValue([]);
    vi.mocked(api.generateSessionId).mockReturnValue("test-session-id");
    // Default: Turnstile is ready (doesn't block any actions)
    vi.mocked(turnstile.useTurnstile).mockReturnValue({
      isReady: true,
      isEnabled: false,
      token: null,
      configLoaded: true,
      refreshToken: vi.fn(),
      awaitToken: vi.fn().mockResolvedValue(null),
    });
  });

  describe("responsive header", () => {
    it("renders header with responsive padding", () => {
      renderWithIntl(<Home />);
      const header = document.querySelector("header");
      expect(header).not.toBeNull();
      expect(header!.className).toContain("px-3");
      expect(header!.className).toContain("py-3");
      expect(header!.className).toContain("sm:px-6");
      expect(header!.className).toContain("sm:py-4");
    });

    it("hides subtitle on mobile (hidden sm:block)", () => {
      renderWithIntl(<Home />);
      const subtitle = screen.getByText("Get inspired daily by God's Word");
      expect(subtitle.className).toContain("hidden");
      expect(subtitle.className).toContain("sm:block");
    });

    it('hides "New Chat" text on mobile (hidden md:inline)', () => {
      renderWithIntl(<Home />);
      const newChatText = screen.getByText("New Chat");
      expect(newChatText.className).toContain("hidden");
      expect(newChatText.className).toContain("md:inline");
    });

    it('translation selector defaults to the empty "Bible version" option (auto-detect)', async () => {
      vi.mocked(api.getTranslations).mockResolvedValue([
        {
          code: "kjv",
          language: "English",
          short_name: "KJV",
          full_name: "King James Version",
        },
      ]);

      renderWithIntl(<Home />);

      const select =
        await screen.findByLabelText<HTMLSelectElement>("Bible version");
      expect(select.value).toBe("");
      const placeholder = Array.from(select.options).find(
        (o) => o.value === "",
      );
      expect(placeholder?.textContent).toBe("Bible version");
    });

    it("sends translation=undefined to streamMessage when placeholder is selected", async () => {
      vi.mocked(api.getTranslations).mockResolvedValue([
        {
          code: "kjv",
          language: "English",
          short_name: "KJV",
          full_name: "King James Version",
        },
      ]);
      vi.mocked(api.streamMessage).mockImplementation(async function* () {
        yield {
          type: "metadata" as const,
          message_id: "msg-auto",
          scripture_context: { query: "", verses: [], passages: [] },
          provider: "test",
          model: "test-model",
        };
        yield { type: "content" as const, content: "ok" };
      });

      const { container } = renderWithIntl(<Home />);
      // Wait for translations to load so the select is enabled.
      await screen.findByLabelText("Bible version");

      const input = screen.getByPlaceholderText(
        "Share what's on your heart...",
      );
      await act(async () => {
        fireEvent.change(input, { target: { value: "hello" } });
      });
      const submitButton = container.querySelector('button[type="submit"]');
      await act(async () => {
        fireEvent.click(submitButton!);
      });

      await waitFor(() => {
        expect(api.streamMessage).toHaveBeenCalled();
      });
      const call = vi.mocked(api.streamMessage).mock.calls[0];
      // streamMessage(userMessageContent, apiMessages, { preferredTranslation, ... })
      expect(call[2]?.preferredTranslation).toBeUndefined();
    });
  });

  describe("responsive main container", () => {
    it("uses h-dvh for dynamic viewport height", () => {
      const { container } = renderWithIntl(<Home />);
      const main = container.querySelector("main");
      expect(main!.className).toContain("h-dvh");
    });

    it("renders messages area with responsive padding", () => {
      renderWithIntl(<Home />);
      const messagesArea = document.querySelector(
        '[class*="overflow-y-auto"][class*="px-3"]',
      );
      expect(messagesArea).not.toBeNull();
      expect(messagesArea!.className).toContain("px-3");
      expect(messagesArea!.className).toContain("py-4");
      expect(messagesArea!.className).toContain("sm:px-6");
      expect(messagesArea!.className).toContain("sm:py-6");
    });

    it("renders input area with responsive padding", () => {
      renderWithIntl(<Home />);
      const inputArea = document.querySelector(".sticky.bottom-0");
      expect(inputArea).not.toBeNull();
      expect(inputArea!.className).toContain("px-3");
      expect(inputArea!.className).toContain("py-3");
      expect(inputArea!.className).toContain("sm:px-6");
      expect(inputArea!.className).toContain("sm:py-4");
    });
  });

  describe("mobile FAB (Floating Action Button)", () => {
    it("does not show FAB when there are no verses", () => {
      renderWithIntl(<Home />);
      expect(
        screen.queryByLabelText("Show scripture references"),
      ).not.toBeInTheDocument();
    });

    it("shows FAB after API returns verses", async () => {
      await renderHomeWithVerses();

      const fab = screen.getByLabelText("Show scripture references");
      expect(fab).toBeInTheDocument();
      expect(fab.className).toContain("lg:hidden");
    });

    it("FAB displays the count of displayed verses", async () => {
      await renderHomeWithVerses();

      const fab = screen.getByLabelText("Show scripture references");
      expect(fab.textContent).toContain("2");
    });
  });

  describe("Suggested prompts", () => {
    it("submits a message when a suggested prompt is clicked", async () => {
      vi.mocked(api.streamMessage).mockImplementation(async function* () {
        yield {
          type: "metadata" as const,
          message_id: "msg-suggested",
          scripture_context: { query: "", verses: [], passages: [] },
          provider: "test",
          model: "test-model",
        };
        yield {
          type: "content" as const,
          content: "Response to suggested prompt",
        };
      });

      renderWithIntl(<Home />);

      // Find one of the suggested prompts (assuming they are rendered based on the mock translations)
      // Since we use renderWithIntl, it uses messages/en.json by default
      // In messages/en.json, Welcome.prompt1 is something like "How can I find peace?"
      // But let's look at the actual translations to be sure.

      const prompts = screen
        .getAllByRole("button")
        .filter(
          (b) => !b.querySelector("svg") && b.className.includes("text-left"),
        );

      expect(prompts.length).toBeGreaterThan(0);

      const promptText = prompts[0].textContent;

      await act(async () => {
        fireEvent.click(prompts[0]);
      });

      // Verify streamMessage was called with the prompt text and the active UI
      // locale (so the backend replies in it and can suggest a switch).
      expect(api.streamMessage).toHaveBeenCalledWith(
        promptText,
        expect.any(Array),
        expect.objectContaining({
          preferredTranslation: undefined,
          sessionId: expect.any(String),
          signal: expect.any(AbortSignal),
        }),
      );
      const opts = vi.mocked(api.streamMessage).mock.calls.at(-1)?.[2];
      expect(opts?.language).toBe("en");

      // Verify the response is displayed
      await waitFor(() => {
        expect(
          screen.getByText("Response to suggested prompt"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("mobile slide-over panel", () => {
    it("opens slide-over panel when FAB is clicked", async () => {
      await renderHomeWithVerses();

      // Before opening: desktop sidebar has "Scripture References" but mobile panel does not
      const beforeCount = screen.getAllByText("Scripture References").length;

      // Click FAB
      const fab = screen.getByLabelText("Show scripture references");
      await act(async () => {
        fireEvent.click(fab);
      });

      // Mobile panel adds another "Scripture References" heading
      const afterCount = screen.getAllByText("Scripture References").length;
      expect(afterCount).toBe(beforeCount + 1);
    });

    it("shows verse cards in the slide-over panel", async () => {
      await renderHomeWithVerses();

      // Open panel
      await act(async () => {
        fireEvent.click(screen.getByLabelText("Show scripture references"));
      });

      // Should show verse references (from VerseCard component in both sidebar and panel)
      expect(screen.getAllByText(/John 3:16/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Romans 8:28/).length).toBeGreaterThanOrEqual(
        1,
      );
    });

    it("closes panel when close button is clicked", async () => {
      await renderHomeWithVerses();

      const beforeCount = screen.getAllByText("Scripture References").length;

      // Open panel
      await act(async () => {
        fireEvent.click(screen.getByLabelText("Show scripture references"));
      });

      expect(screen.getAllByText("Scripture References").length).toBe(
        beforeCount + 1,
      );

      // Click close button (on the mobile panel)
      const closeButton = screen.getByLabelText("Close");
      await act(async () => {
        fireEvent.click(closeButton);
      });

      // Mobile panel should be gone, back to original count
      expect(screen.getAllByText("Scripture References").length).toBe(
        beforeCount,
      );
    });

    it("closes panel when backdrop is clicked", async () => {
      await renderHomeWithVerses();

      const beforeCount = screen.getAllByText("Scripture References").length;

      // Open panel
      await act(async () => {
        fireEvent.click(screen.getByLabelText("Show scripture references"));
      });

      expect(screen.getAllByText("Scripture References").length).toBe(
        beforeCount + 1,
      );

      // Click backdrop
      const backdrop = document.querySelector('[class*="bg-black/30"]');
      expect(backdrop).not.toBeNull();
      await act(async () => {
        fireEvent.click(backdrop!);
      });

      expect(screen.getAllByText("Scripture References").length).toBe(
        beforeCount,
      );
    });

    it("shows filter toggle buttons in slide-over panel", async () => {
      await renderHomeWithVerses();

      // Open panel
      await act(async () => {
        fireEvent.click(screen.getByLabelText("Show scripture references"));
      });

      // Panel filter buttons (desktop sidebar also has them)
      const referencedButtons = screen.getAllByText("Cited");
      expect(referencedButtons.length).toBeGreaterThanOrEqual(2);
    });

    it("defaults the verse filter to Cited (not All Related)", async () => {
      await renderHomeWithVerses();

      await act(async () => {
        fireEvent.click(screen.getByLabelText("Show scripture references"));
      });

      const citedButtons = screen.getAllByText("Cited");
      const allButtons = screen
        .getAllByRole("button")
        .filter((b) => /^All Related \(/.test(b.textContent ?? ""));

      // Active button uses primary background; inactive uses white.
      expect(citedButtons.length).toBeGreaterThanOrEqual(1);
      expect(allButtons.length).toBeGreaterThanOrEqual(1);
      for (const btn of citedButtons) {
        expect(btn.className).toContain("bg-primary-100");
      }
      for (const btn of allButtons) {
        expect(btn.className).toContain("bg-white");
      }
    });

    it("panel has lg:hidden class so it only shows on mobile", async () => {
      await renderHomeWithVerses();

      // Open panel
      await act(async () => {
        fireEvent.click(screen.getByLabelText("Show scripture references"));
      });

      const panel = document.querySelector(
        '[class*="lg:hidden"][class*="fixed"]',
      );
      expect(panel).not.toBeNull();
    });

    it("resets mobile panel state on New Chat", async () => {
      await renderHomeWithVerses();

      // Open panel
      await act(async () => {
        fireEvent.click(screen.getByLabelText("Show scripture references"));
      });

      // Mobile panel should be present (more than just the desktop sidebar)
      const beforeResetCount = screen.getAllByText(
        "Scripture References",
      ).length;
      expect(beforeResetCount).toBeGreaterThanOrEqual(2);

      // Click New Chat
      const newChatButton = screen.getByText("New Chat").closest("button")!;
      await act(async () => {
        fireEvent.click(newChatButton);
      });

      // Panel and FAB should be gone (no verses after reset)
      expect(screen.queryAllByText("Scripture References").length).toBe(0);
      expect(
        screen.queryByLabelText("Show scripture references"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Turnstile security checks", () => {
    beforeEach(() => {
      vi.clearAllMocks();
      // Re-setup mocks that are needed for every render
      vi.mocked(api.warmupBackend).mockImplementation((onReady: () => void) => {
        onReady();
      });
      vi.mocked(api.getTranslations).mockResolvedValue([]);
      vi.mocked(api.generateSessionId).mockReturnValue("test-session-id");
    });

    it("disables suggested prompts when Turnstile is loading", () => {
      // Mock Turnstile as enabled but not ready
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: false,
        isEnabled: true,
        token: null,
        configLoaded: true,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      renderWithIntl(<Home />);

      // Find the suggested prompt buttons
      const prompts = screen
        .getAllByRole("button")
        .filter(
          (b) => !b.querySelector("svg") && b.className.includes("text-left"),
        );

      // All suggested prompts should be disabled
      prompts.forEach((prompt) => {
        expect(prompt).toBeDisabled();
      });
    });

    it("disables suggested prompts before /config has resolved", () => {
      // Initial state: config still loading. Until we know whether Turnstile
      // is enabled, all gated POSTs would race past it without a token.
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: false,
        isEnabled: false,
        token: null,
        configLoaded: false,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      renderWithIntl(<Home />);

      const prompts = screen
        .getAllByRole("button")
        .filter(
          (b) => !b.querySelector("svg") && b.className.includes("text-left"),
        );

      prompts.forEach((prompt) => {
        expect(prompt).toBeDisabled();
      });

      expect(
        screen.getByText("Preparing secure connection..."),
      ).toBeInTheDocument();
    });

    it("enables suggested prompts when Turnstile is ready", () => {
      // Mock Turnstile as enabled and ready
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: true,
        isEnabled: true,
        token: "test-token",
        configLoaded: true,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      renderWithIntl(<Home />);

      // Find the suggested prompt buttons
      const prompts = screen
        .getAllByRole("button")
        .filter(
          (b) => !b.querySelector("svg") && b.className.includes("text-left"),
        );

      // All suggested prompts should be enabled
      prompts.forEach((prompt) => {
        expect(prompt).not.toBeDisabled();
      });
    });

    it("disables send button when Turnstile is loading", () => {
      // Mock Turnstile as enabled but not ready
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: false,
        isEnabled: true,
        token: null,
        configLoaded: true,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      const { container } = renderWithIntl(<Home />);

      // Find the send button by looking for the form submit button
      const submitButton = container.querySelector(
        'form button[type="submit"]',
      ) as HTMLButtonElement;

      expect(submitButton).toBeDisabled();
    });

    it("enables send button when Turnstile is ready", () => {
      // Mock Turnstile as enabled and ready
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: true,
        isEnabled: true,
        token: "test-token",
        configLoaded: true,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      const { container } = renderWithIntl(<Home />);

      // Find the send button by looking for the form submit button
      const submitButton = container.querySelector(
        'form button[type="submit"]',
      ) as HTMLButtonElement;

      // Button should still be disabled because input is empty
      expect(submitButton).toBeDisabled();

      // Type something in the input
      const input = screen.getByPlaceholderText(
        "Share what's on your heart...",
      );
      fireEvent.change(input, { target: { value: "Test message" } });

      // Now button should be enabled
      expect(submitButton).not.toBeDisabled();
    });

    it("shows loading message when Turnstile is loading", () => {
      // Mock Turnstile as enabled but not ready
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: false,
        isEnabled: true,
        token: null,
        configLoaded: true,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      renderWithIntl(<Home />);

      // Look for the loading message
      expect(
        screen.getByText("Preparing secure connection..."),
      ).toBeInTheDocument();
    });

    it("hides loading message when Turnstile is ready", () => {
      // Mock Turnstile as enabled and ready
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: true,
        isEnabled: true,
        token: "test-token",
        configLoaded: true,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      renderWithIntl(<Home />);

      // Loading message should not be present
      expect(
        screen.queryByText("Preparing secure connection..."),
      ).not.toBeInTheDocument();
    });

    it("works correctly when Turnstile is disabled", () => {
      // Mock Turnstile as disabled
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: true,
        isEnabled: false,
        token: null,
        configLoaded: true,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      const { container } = renderWithIntl(<Home />);

      // Suggested prompts should be enabled
      const prompts = screen
        .getAllByRole("button")
        .filter(
          (b) => !b.querySelector("svg") && b.className.includes("text-left"),
        );
      prompts.forEach((prompt) => {
        expect(prompt).not.toBeDisabled();
      });

      // Loading message should not be present
      expect(
        screen.queryByText("Preparing secure connection..."),
      ).not.toBeInTheDocument();

      // Send button should only be disabled because input is empty
      const submitButton = container.querySelector(
        'form button[type="submit"]',
      ) as HTMLButtonElement;
      expect(submitButton).toBeDisabled();

      // Type something in the input
      const input = screen.getByPlaceholderText(
        "Share what's on your heart...",
      );
      fireEvent.change(input, { target: { value: "Test message" } });

      // Now button should be enabled (not blocked by Turnstile)
      expect(submitButton).not.toBeDisabled();
    });

    it("prevents message submission via suggested prompts when Turnstile is not ready", async () => {
      // Mock Turnstile as enabled but not ready
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: false,
        isEnabled: true,
        token: null,
        configLoaded: true,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      vi.mocked(api.streamMessage).mockImplementation(async function* () {
        yield {
          type: "metadata" as const,
          message_id: "msg-1",
          scripture_context: { query: "", verses: [], passages: [] },
          provider: "test",
          model: "test-model",
        };
        yield {
          type: "content" as const,
          content: "This should not be called",
        };
      });

      renderWithIntl(<Home />);

      // Find and click a suggested prompt
      const prompts = screen
        .getAllByRole("button")
        .filter(
          (b) => !b.querySelector("svg") && b.className.includes("text-left"),
        );

      await act(async () => {
        fireEvent.click(prompts[0]);
      });

      // streamMessage should not have been called because button is disabled
      expect(api.streamMessage).not.toHaveBeenCalled();
    });

    it("allows message submission via suggested prompts when Turnstile is ready", async () => {
      // Mock Turnstile as enabled and ready
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: true,
        isEnabled: true,
        token: "test-token",
        configLoaded: true,
        refreshToken: vi.fn(),
        awaitToken: vi.fn().mockResolvedValue(null),
      });

      vi.mocked(api.streamMessage).mockImplementation(async function* () {
        yield {
          type: "metadata" as const,
          message_id: "msg-1",
          scripture_context: { query: "", verses: [], passages: [] },
          provider: "test",
          model: "test-model",
        };
        yield {
          type: "content" as const,
          content: "Response to suggested prompt",
        };
      });

      renderWithIntl(<Home />);

      // Find and click a suggested prompt
      const prompts = screen
        .getAllByRole("button")
        .filter(
          (b) => !b.querySelector("svg") && b.className.includes("text-left"),
        );

      const promptText = prompts[0].textContent;

      await act(async () => {
        fireEvent.click(prompts[0]);
      });

      // streamMessage should be called with the active UI locale so the backend
      // replies in it and can detect mismatches.
      expect(api.streamMessage).toHaveBeenCalledWith(
        promptText,
        expect.any(Array),
        expect.objectContaining({
          preferredTranslation: undefined,
          sessionId: expect.any(String),
          signal: expect.any(AbortSignal),
        }),
      );
      const opts = vi.mocked(api.streamMessage).mock.calls.at(-1)?.[2];
      expect(opts?.language).toBe("en");

      // Verify the response is displayed
      await waitFor(() => {
        expect(
          screen.getByText("Response to suggested prompt"),
        ).toBeInTheDocument();
      });
    });
  });
});

describe("smart auto-scroll", () => {
  const mockStreamResponse = () => {
    vi.mocked(api.streamMessage).mockImplementation(async function* () {
      yield {
        type: "metadata" as const,
        message_id: "scroll-test-id",
        scripture_context: { query: "", verses: [], passages: [] },
        provider: "test",
        model: "test-model",
      };
      yield { type: "content" as const, content: "Test response" };
    });
  };

  const getMessagesContainer = () =>
    document.querySelector(
      '[class*="overflow-y-auto"][class*="px-3"]',
    ) as HTMLElement;

  const simulateScrolledUp = (container: HTMLElement) => {
    Object.defineProperty(container, "scrollHeight", {
      configurable: true,
      value: 2000,
    });
    Object.defineProperty(container, "clientHeight", {
      configurable: true,
      value: 500,
    });
    Object.defineProperty(container, "scrollTop", {
      configurable: true,
      value: 0,
    });
    fireEvent.scroll(container);
  };

  const simulateScrolledToBottom = (container: HTMLElement) => {
    Object.defineProperty(container, "scrollHeight", {
      configurable: true,
      value: 2000,
    });
    Object.defineProperty(container, "clientHeight", {
      configurable: true,
      value: 500,
    });
    Object.defineProperty(container, "scrollTop", {
      configurable: true,
      value: 1950,
    });
    fireEvent.scroll(container);
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.warmupBackend).mockImplementation((onReady: () => void) => {
      onReady();
    });
    vi.mocked(api.getTranslations).mockResolvedValue([]);
    vi.mocked(api.generateSessionId).mockReturnValue("test-session-id");
    vi.mocked(turnstile.useTurnstile).mockReturnValue({
      isReady: true,
      isEnabled: false,
      token: null,
      configLoaded: true,
      refreshToken: vi.fn(),
      awaitToken: vi.fn().mockResolvedValue(null),
    });
  });

  it("calls scrollIntoView when a message is submitted", async () => {
    mockStreamResponse();
    const scrollSpy = vi.mocked(Element.prototype.scrollIntoView);
    scrollSpy.mockClear();

    const { container } = renderWithIntl(<Home />);
    const input = screen.getByPlaceholderText("Share what's on your heart...");
    const submitButton = container.querySelector('button[type="submit"]');

    await act(async () => {
      fireEvent.change(input, { target: { value: "Hello" } });
    });
    await act(async () => {
      fireEvent.click(submitButton!);
    });
    await waitFor(() =>
      expect(screen.getByText("Test response")).toBeInTheDocument(),
    );

    expect(scrollSpy).toHaveBeenCalled();
  });

  it("shows scroll-to-bottom button when user scrolls up with messages present", async () => {
    mockStreamResponse();
    renderWithIntl(<Home />);

    const input = screen.getByPlaceholderText("Share what's on your heart...");
    const submitButton = document.querySelector('button[type="submit"]');
    await act(async () => {
      fireEvent.change(input, { target: { value: "Hello" } });
    });
    await act(async () => {
      fireEvent.click(submitButton!);
    });
    await waitFor(() =>
      expect(screen.getByText("Test response")).toBeInTheDocument(),
    );

    await act(async () => {
      simulateScrolledUp(getMessagesContainer());
    });

    expect(screen.getByLabelText("Scroll to bottom")).toBeInTheDocument();
  });

  it("sending a new message resets auto-scroll to follow new content", async () => {
    mockStreamResponse();
    const scrollSpy = vi.mocked(Element.prototype.scrollIntoView);

    renderWithIntl(<Home />);
    const input = screen.getByPlaceholderText("Share what's on your heart...");
    const submitButton = document.querySelector('button[type="submit"]');

    // Send first message
    await act(async () => {
      fireEvent.change(input, { target: { value: "First message" } });
    });
    await act(async () => {
      fireEvent.click(submitButton!);
    });
    await waitFor(() =>
      expect(screen.getByText("Test response")).toBeInTheDocument(),
    );

    // Simulate scrolling up — auto-scroll pauses, button appears
    await act(async () => {
      simulateScrolledUp(getMessagesContainer());
    });
    expect(screen.getByLabelText("Scroll to bottom")).toBeInTheDocument();

    scrollSpy.mockClear();
    mockStreamResponse();

    // Send second message — should reset isUserNearBottom to true
    await act(async () => {
      fireEvent.change(input, { target: { value: "Second message" } });
    });
    await act(async () => {
      fireEvent.click(submitButton!);
    });
    await waitFor(() =>
      expect(screen.getAllByText("Test response").length).toBeGreaterThan(1),
    );

    // scrollIntoView must have been called (auto-scroll resumed)
    expect(scrollSpy).toHaveBeenCalled();
    // Scroll-to-bottom button must be gone
    expect(screen.queryByLabelText("Scroll to bottom")).not.toBeInTheDocument();
  });

  it("resumes auto-scroll when user manually scrolls back to bottom", async () => {
    mockStreamResponse();
    renderWithIntl(<Home />);

    const input = screen.getByPlaceholderText("Share what's on your heart...");
    const submitButton = document.querySelector('button[type="submit"]');

    await act(async () => {
      fireEvent.change(input, { target: { value: "Hello" } });
    });
    await act(async () => {
      fireEvent.click(submitButton!);
    });
    await waitFor(() =>
      expect(screen.getByText("Test response")).toBeInTheDocument(),
    );

    const container = getMessagesContainer();

    // Scroll up — button appears
    await act(async () => {
      simulateScrolledUp(container);
    });
    expect(screen.getByLabelText("Scroll to bottom")).toBeInTheDocument();

    // Scroll back to bottom — button disappears
    await act(async () => {
      simulateScrolledToBottom(container);
    });
    expect(screen.queryByLabelText("Scroll to bottom")).not.toBeInTheDocument();
  });
});

describe("language-switch suggestion", () => {
  beforeEach(() => {
    vi.mocked(turnstile.useTurnstile).mockReturnValue({
      isReady: true,
      isEnabled: false,
      configLoaded: true,
    });
    sessionStorage.clear();
    mockRouterReplace.mockClear();
  });

  const mockStreamWithSuggestion = (languageSuggestion: string | null) => {
    vi.mocked(api.streamMessage).mockImplementation(async function* () {
      yield {
        type: "metadata" as const,
        message_id: "lang-test-id",
        scripture_context: { query: "", verses: [], passages: [] },
        provider: "test",
        model: "test-model",
        language_suggestion: languageSuggestion,
      };
      yield { type: "content" as const, content: "A response" };
      yield { type: "completion" as const, verses_cited: [] };
    });
  };

  const submitMessage = (container: HTMLElement, message: string) => {
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: message },
    });
    const sendBtn = container.querySelector(
      'form button[type="submit"]',
    ) as HTMLButtonElement;
    fireEvent.click(sendBtn);
  };

  it("shows the switch banner when a confident language mismatch is detected", async () => {
    mockStreamWithSuggestion("it");
    const { container } = renderWithIntl(<Home />);

    await act(async () => {
      submitMessage(container, "Ciao come stai");
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Switch" }),
      ).toBeInTheDocument();
    });
  });

  it("does not show the banner when language_suggestion is null", async () => {
    mockStreamWithSuggestion(null);
    const { container } = renderWithIntl(<Home />);

    await act(async () => {
      submitMessage(container, "Hello world");
    });

    await waitFor(() =>
      expect(screen.getByText("A response")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Switch" }),
    ).not.toBeInTheDocument();
  });

  it("hides the banner after dismiss is clicked", async () => {
    mockStreamWithSuggestion("it");
    const { container } = renderWithIntl(<Home />);

    await act(async () => {
      submitMessage(container, "Ciao come stai");
    });

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Switch" }),
      ).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByLabelText("Dismiss"));
    expect(
      screen.queryByRole("button", { name: "Switch" }),
    ).not.toBeInTheDocument();
  });

  it("persists conversation and navigates on Switch click", async () => {
    mockStreamWithSuggestion("it");
    const { container } = renderWithIntl(<Home />);

    await act(async () => {
      submitMessage(container, "Ciao come stai");
    });

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Switch" }),
      ).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Switch" }));

    const stored = sessionStorage.getItem("preservedConversation");
    expect(stored).not.toBeNull();
    const parsed = JSON.parse(stored!);
    expect(Array.isArray(parsed.messages)).toBe(true);
    expect(mockRouterReplace).toHaveBeenCalledWith("/", { locale: "it" });
  });
});

// On the live site the backend sends a `completion` event carrying the verses
// it actually cited (`verses_cited`), and those can be RANGES like
// "John 3:16-17". Once that event arrives the "Cited" filter switches from
// content-extraction to these server citations. This path was previously
// untested — and a range citation used to reveal only its first verse, making
// the panel look broken/empty. These tests lock in the corrected behaviour.
describe("verse citation panel — server completion event", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.warmupBackend).mockImplementation((onReady: () => void) => {
      onReady();
    });
    vi.mocked(api.getTranslations).mockResolvedValue([]);
    vi.mocked(api.generateSessionId).mockReturnValue("test-session-id");
    vi.mocked(turnstile.useTurnstile).mockReturnValue({
      isReady: true,
      isEnabled: false,
      token: null,
      configLoaded: true,
      refreshToken: vi.fn(),
      awaitToken: vi.fn().mockResolvedValue(null),
    });
  });

  async function renderHomeWithCitedRange() {
    vi.mocked(api.streamMessage).mockImplementation(async function* () {
      yield {
        type: "metadata" as const,
        message_id: "msg-range",
        scripture_context: {
          query: "love",
          // Semantic sidebar results: two verses inside the cited range plus
          // one neighbour the assistant did NOT cite.
          verses: [
            {
              book: "John",
              chapter: 3,
              verse: 16,
              text: "For God so loved the world...",
              reference: "John 3:16",
              similarity: 0.9,
            },
            {
              book: "John",
              chapter: 3,
              verse: 17,
              text: "For God did not send his Son to condemn...",
              reference: "John 3:17",
              similarity: 0.85,
            },
            {
              book: "Romans",
              chapter: 8,
              verse: 28,
              text: "And we know that all things work together...",
              reference: "Romans 8:28",
              similarity: 0.6,
            },
          ],
          passages: [],
        },
        provider: "test",
        model: "test-model",
      };
      yield {
        type: "content" as const,
        content: "God's love is shown in John 3:16-17.",
      };
      // Backend cites a RANGE; Romans 8:28 was a semantic neighbour, not cited.
      yield {
        type: "completion" as const,
        verses_cited: ["John 3:16-17"],
      };
    });

    const result = renderWithIntl(<Home />);
    const input = screen.getByPlaceholderText("Share what's on your heart...");
    await act(async () => {
      fireEvent.change(input, { target: { value: "Tell me about love" } });
    });
    const submitButton = result.container.querySelector(
      'button[type="submit"]',
    );
    await act(async () => {
      fireEvent.click(submitButton!);
    });
    await waitFor(() => {
      expect(
        screen.getByText("God's love is shown in John 3:16-17."),
      ).toBeInTheDocument();
    });
    return result;
  }

  it("shows EVERY verse inside a cited range in the Cited filter", async () => {
    await renderHomeWithCitedRange();

    // Both ends of the range must appear (desktop sidebar). Before the fix,
    // John 3:17 was hidden because only the range's start verse matched.
    expect(screen.getAllByText(/John 3:16/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/John 3:17/).length).toBeGreaterThanOrEqual(1);
  });

  it("hides a semantic neighbour the assistant did not cite", async () => {
    await renderHomeWithCitedRange();

    // Romans 8:28 was returned by semantic search but never cited, so the
    // default "Cited" filter must not show it.
    expect(screen.queryByText(/Romans 8:28/)).not.toBeInTheDocument();
  });

  it("reveals the uncited neighbour once 'All Related' is selected", async () => {
    await renderHomeWithCitedRange();

    // The full semantic set is still reachable via the All Related toggle.
    const allRelated = screen
      .getAllByRole("button")
      .filter((b) => /^All Related \(/.test(b.textContent ?? ""));
    expect(allRelated.length).toBeGreaterThanOrEqual(1);
    await act(async () => {
      fireEvent.click(allRelated[0]);
    });

    expect(screen.getAllByText(/Romans 8:28/).length).toBeGreaterThanOrEqual(1);
  });

  it("renders a cited_verses card that was absent from semantic search results", async () => {
    // Simulates the core architectural fix: the backend now resolves cited verse
    // references and emits them as `cited_verses`. A verse the semantic search
    // never returned must still appear as a card in the default "Cited" view.
    vi.mocked(api.streamMessage).mockImplementation(async function* () {
      yield {
        type: "metadata" as const,
        message_id: "msg-cited-absent",
        scripture_context: {
          query: "love",
          // Semantic search returned only Romans 8:28 — NOT the cited verse.
          verses: [
            {
              book: "Romans",
              chapter: 8,
              verse: 28,
              text: "And we know that all things work together...",
              reference: "Romans 8:28",
              similarity: 0.6,
            },
          ],
          passages: [],
        },
        provider: "test",
        model: "test-model",
      };
      yield {
        type: "content" as const,
        content: "As John 3:16 says, God so loved the world.",
      };
      // Backend resolved the citation to a full verse object.
      yield {
        type: "completion" as const,
        verses_cited: ["John 3:16"],
        cited_verses: [
          {
            book: "John",
            chapter: 3,
            verse: 16,
            text: "For God so loved the world...",
            reference: "John 3:16",
            translation: "kjv",
          },
        ],
      };
    });

    const result = renderWithIntl(<Home />);
    const input = screen.getByPlaceholderText("Share what's on your heart...");
    await act(async () => {
      fireEvent.change(input, { target: { value: "Tell me about love" } });
    });
    const submitButton = result.container.querySelector(
      'button[type="submit"]',
    );
    await act(async () => {
      fireEvent.click(submitButton!);
    });
    await waitFor(() => {
      expect(
        screen.getByText("As John 3:16 says, God so loved the world."),
      ).toBeInTheDocument();
    });

    // The cited verse (absent from semantic results) must appear as a card.
    expect(screen.getAllByText(/John 3:16/).length).toBeGreaterThanOrEqual(1);
    // The uncited semantic neighbour should be hidden in the default "Cited" view.
    expect(screen.queryByText(/Romans 8:28/)).not.toBeInTheDocument();
  });
});
