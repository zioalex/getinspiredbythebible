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

// Mock i18n navigation (used by LanguageSwitcher)
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.PropsWithChildren) => (
    <a {...props}>{children}</a>
  ),
  redirect: vi.fn(),
  usePathname: vi.fn().mockReturnValue("/"),
  useRouter: vi.fn().mockReturnValue({ replace: vi.fn() }),
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
      refreshToken: vi.fn(),
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
      const subtitle = screen.getByText("Find encouragement through Scripture");
      expect(subtitle.className).toContain("hidden");
      expect(subtitle.className).toContain("sm:block");
    });

    it('hides "New Chat" text on mobile (hidden md:inline)', () => {
      renderWithIntl(<Home />);
      const newChatText = screen.getByText("New Chat");
      expect(newChatText.className).toContain("hidden");
      expect(newChatText.className).toContain("md:inline");
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

      // Verify streamMessage was called with the prompt text
      expect(api.streamMessage).toHaveBeenCalledWith(
        promptText,
        expect.any(Array),
        undefined,
        expect.any(String),
      );

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
      const referencedButtons = screen.getAllByText("Referenced");
      expect(referencedButtons.length).toBeGreaterThanOrEqual(2);
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
        refreshToken: vi.fn(),
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

    it("enables suggested prompts when Turnstile is ready", () => {
      // Mock Turnstile as enabled and ready
      vi.mocked(turnstile.useTurnstile).mockReturnValue({
        isReady: true,
        isEnabled: true,
        token: "test-token",
        refreshToken: vi.fn(),
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
        refreshToken: vi.fn(),
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
        refreshToken: vi.fn(),
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
        refreshToken: vi.fn(),
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
        refreshToken: vi.fn(),
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
        refreshToken: vi.fn(),
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
        refreshToken: vi.fn(),
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
        refreshToken: vi.fn(),
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

      // streamMessage should have been called
      expect(api.streamMessage).toHaveBeenCalledWith(
        promptText,
        expect.any(Array),
        undefined,
        expect.any(String),
      );

      // Verify the response is displayed
      await waitFor(() => {
        expect(
          screen.getByText("Response to suggested prompt"),
        ).toBeInTheDocument();
      });
    });
  });
});
