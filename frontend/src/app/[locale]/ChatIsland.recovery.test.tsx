import "fake-indexeddb/auto";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import Home from "./ChatIsland";
import enMessages from "../../../messages/en.json";
import {
  streamMessage,
  finalizeMessage,
  getCrisisResources,
  StreamTimeoutError,
  ContentBlockedError,
} from "@/lib/api";
import { clearAll, __resetDbCache } from "@/lib/conversationStore";

// BITB-320: stream ended without `completion` -> finalize recovery.
Element.prototype.scrollIntoView = vi.fn();

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
    getCrisisResources: vi.fn(),
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

const META = { type: "metadata", message_id: "m1", provider: "p", model: "m" };
const TRAILER = '\n<!-- FOLLOWUPS: ["Why?"] -->';

function renderChat() {
  return render(
    <NextIntlClientProvider locale="en" messages={enMessages}>
      <Home />
    </NextIntlClientProvider>,
  );
}

async function send(text: string) {
  const box = await screen.findByPlaceholderText(
    enMessages.Chat.inputPlaceholder,
  );
  fireEvent.change(box, { target: { value: text } });
  fireEvent.submit(box.closest("form")!);
}

const FINALIZED = {
  verses_cited: ["John 3:16"],
  resolved_verses: [],
  follow_ups: ["Tell me more about grace"],
  truncated: false,
};

describe("ChatIsland stream recovery (BITB-320)", () => {
  beforeEach(async () => {
    vi.mocked(streamMessage).mockReset();
    vi.mocked(finalizeMessage).mockReset();
    window.localStorage.clear();
    __resetDbCache();
    await clearAll();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("EOF without completion calls finalize and merges chips", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield META as never;
      yield { type: "content", content: "God so loved the world." };
    });
    vi.mocked(finalizeMessage).mockResolvedValue(FINALIZED);
    renderChat();
    await send("Tell me about love");

    await screen.findByRole("button", { name: "Tell me more about grace" });
    expect(finalizeMessage).toHaveBeenCalledTimes(1);
    const args = vi.mocked(finalizeMessage).mock.calls[0][0];
    expect(args.message).toBe("Tell me about love");
    expect(args.assistantText).toBe("God so loved the world.");
    expect(args.reason).toBe("eof");
    expect(args.messageId).toBe("m1");
    expect(screen.queryByTestId("interrupted-note")).toBeNull();
  });

  it("applies corrected_message from finalize", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield META as never;
      yield { type: "content", content: "Wrong quote." + TRAILER };
    });
    vi.mocked(finalizeMessage).mockResolvedValue({
      ...FINALIZED,
      corrected_message: "Right quote.",
    });
    renderChat();
    await send("q");
    await screen.findByText("Right quote.");
  });

  it("error event after content triggers finalize without an error bubble", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield META as never;
      yield { type: "content", content: "Partial answer." };
      yield { type: "error", error: "boom", partial: true } as never;
    });
    vi.mocked(finalizeMessage).mockResolvedValue(FINALIZED);
    renderChat();
    await send("q");
    await screen.findByRole("button", { name: "Tell me more about grace" });
    expect(vi.mocked(finalizeMessage).mock.calls[0][0].reason).toBe(
      "error_event",
    );
    expect(screen.getByText("Partial answer.")).toBeInTheDocument();
    expect(screen.queryByText(enMessages.Chat.errorConnection)).toBeNull();
  });

  it("network error after content keeps the text and finalizes", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield META as never;
      yield { type: "content", content: "Half of it." };
      throw new TypeError("network error");
    });
    vi.mocked(finalizeMessage).mockResolvedValue(FINALIZED);
    renderChat();
    await send("q");
    await screen.findByRole("button", { name: "Tell me more about grace" });
    expect(vi.mocked(finalizeMessage).mock.calls[0][0].reason).toBe(
      "network_error",
    );
    expect(screen.getByText("Half of it.")).toBeInTheDocument();
    expect(screen.queryByText(enMessages.Chat.errorConnection)).toBeNull();
  });

  it("timeout after content finalizes with reason=timeout and no timeout bubble", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield { type: "content", content: "Stalled." };
      throw new StreamTimeoutError();
    });
    vi.mocked(finalizeMessage).mockResolvedValue(FINALIZED);
    renderChat();
    await send("q");
    await screen.findByRole("button", { name: "Tell me more about grace" });
    expect(vi.mocked(finalizeMessage).mock.calls[0][0].reason).toBe("timeout");
    expect(screen.queryByText(enMessages.Chat.errorTimeout)).toBeNull();
  });

  it("finalize failure keeps text, strips trailer, shows the interrupted note", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield { type: "content", content: "Answer text." + TRAILER };
    });
    vi.mocked(finalizeMessage).mockRejectedValue(new Error("down"));
    renderChat();
    await send("q");
    await screen.findByTestId("interrupted-note", {}, { timeout: 4000 });
    // one attempt + one retry
    expect(finalizeMessage).toHaveBeenCalledTimes(2);
    expect(screen.getByText("Answer text.")).toBeInTheDocument();
    expect(screen.queryByText(/FOLLOWUPS/)).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent(
      enMessages.Chat.interruptedNote,
    );
  });

  it("truncated:true shows the note and Continue sends the localized prompt", async () => {
    vi.mocked(streamMessage).mockImplementationOnce(async function* () {
      yield { type: "content", content: "The Lord is my" };
    });
    vi.mocked(finalizeMessage).mockResolvedValue({
      ...FINALIZED,
      truncated: true,
    });
    renderChat();
    await send("psalm 23");
    const button = await screen.findByRole("button", {
      name: enMessages.Chat.continueButton,
    });
    expect(button.className).toContain("min-h-[44px]");

    vi.mocked(streamMessage).mockImplementationOnce(async function* () {
      yield { type: "content", content: " shepherd." };
      yield { type: "completion", verses_cited: [] };
    });
    fireEvent.click(button);
    await screen.findByText(" shepherd.".trim());
    expect(vi.mocked(streamMessage).mock.calls[1][0]).toBe(
      enMessages.Chat.continuePrompt,
    );
  });

  it("while loading the note stays visible and only Continue is hidden", async () => {
    vi.mocked(streamMessage).mockImplementationOnce(async function* () {
      yield { type: "content", content: "The Lord is my" };
    });
    vi.mocked(finalizeMessage).mockResolvedValue({
      ...FINALIZED,
      truncated: true,
    });
    renderChat();
    await send("psalm 23");
    const button = await screen.findByRole("button", {
      name: enMessages.Chat.continueButton,
    });

    // The next turn never finishes: isLoading stays true.
    vi.mocked(streamMessage).mockImplementationOnce(async function* () {
      await new Promise<void>(() => {});
      yield { type: "completion", verses_cited: [] };
    });
    fireEvent.click(button);
    await waitFor(() =>
      expect(vi.mocked(streamMessage).mock.calls.length).toBe(2),
    );
    expect(screen.getByTestId("interrupted-note")).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: enMessages.Chat.continueButton }),
    ).toBeNull();
  });

  it("user Stop never finalizes", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* (_m, _h, opts) {
      yield { type: "content", content: "Partial." };
      await new Promise<void>((resolve) =>
        opts?.signal?.addEventListener("abort", () => resolve()),
      );
    });
    renderChat();
    await send("q");
    await screen.findByText("Partial.");
    fireEvent.click(
      await screen.findByLabelText(enMessages.Chat.stopGenerating),
    );
    await waitFor(() =>
      expect(
        screen.queryByLabelText(enMessages.Chat.stopGenerating),
      ).toBeNull(),
    );
    expect(finalizeMessage).not.toHaveBeenCalled();
    expect(screen.getByText("Partial.")).toBeInTheDocument();
    expect(screen.queryByTestId("interrupted-note")).toBeNull();
  });

  it("no content keeps the existing error path (no finalize)", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield META as never;
      throw new TypeError("network error");
    });
    renderChat();
    await send("q");
    await screen.findByText(enMessages.Chat.errorConnection);
    expect(finalizeMessage).not.toHaveBeenCalled();
  });

  it("blocked content after text is not recovered", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield { type: "content", content: "Some text." };
      throw new ContentBlockedError();
    });
    renderChat();
    await send("q");
    await screen.findByText(enMessages.Chat.contentBlockedMessage);
    expect(finalizeMessage).not.toHaveBeenCalled();
  });

  it("a normal completion never calls finalize", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield { type: "content", content: "All good." };
      yield { type: "completion", verses_cited: [] };
    });
    renderChat();
    await send("q");
    await screen.findByText("All good.");
    expect(finalizeMessage).not.toHaveBeenCalled();
  });
});
