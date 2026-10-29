import "fake-indexeddb/auto";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import Home from "./ChatIsland";
import enMessages from "../../../messages/en.json";
import { streamMessage } from "@/lib/api";
import {
  listConversations,
  getMessages,
  clearAll,
  __resetDbCache,
} from "@/lib/conversationStore";
import { crisisFixture } from "@/test/crisisFixtures";

// BITB-251: the crisis card renders above the reply and survives stop/error.
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

const CRISIS_CHUNK = { type: "crisis_resources", resources: crisisFixture };

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
  const form = box.closest("form")!;
  fireEvent.submit(form);
}

describe("ChatIsland crisis card (BITB-251)", () => {
  beforeEach(async () => {
    vi.mocked(streamMessage).mockReset();
    window.localStorage.clear();
    __resetDbCache();
    await clearAll();
  });

  it("renders the card ABOVE the assistant reply and persists it", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield CRISIS_CHUNK as never;
      yield { type: "metadata", message_id: "m1", provider: "p", model: "m" };
      yield { type: "content", content: "I am here with you." };
      yield { type: "completion", verses_cited: [] };
    });
    renderChat();
    await send("I want to end it all");

    const card = await screen.findByTestId("crisis-resources-card");
    const reply = await screen.findByText("I am here with you.");
    expect(
      card.compareDocumentPosition(reply) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Call Telefono Amico" }),
    ).toHaveAttribute("href", "tel:+390223272327");

    // Saved turn keeps the card.
    await waitFor(async () => {
      const [conv] = await listConversations();
      expect(conv).toBeDefined();
      const msgs = await getMessages(conv.id);
      expect(msgs.find((m) => m.role === "assistant")?.crisisResources).toEqual(
        crisisFixture,
      );
    });
  });

  it("keeps the card when the stream errors after it arrived", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield CRISIS_CHUNK as never;
      throw new Error("LLM exploded");
    });
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderChat();
    await send("I want to end it all");

    await screen.findByText(enMessages.Chat.errorConnection);
    expect(screen.getByTestId("crisis-resources-card")).toBeInTheDocument();
  });

  it("keeps the card when the user stops streaming", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* (_m, _h, opts) {
      yield CRISIS_CHUNK as never;
      await new Promise<void>((resolve) =>
        opts?.signal?.addEventListener("abort", () => resolve()),
      );
    });
    renderChat();
    await send("I want to end it all");

    await screen.findByTestId("crisis-resources-card");
    fireEvent.click(
      await screen.findByLabelText(enMessages.Chat.stopGenerating),
    );
    await waitFor(() =>
      expect(
        screen.queryByLabelText(enMessages.Chat.stopGenerating),
      ).toBeNull(),
    );
    expect(screen.getByTestId("crisis-resources-card")).toBeInTheDocument();
  });

  it("shows no card on a normal turn", async () => {
    vi.mocked(streamMessage).mockImplementation(async function* () {
      yield { type: "metadata", message_id: "m1", provider: "p", model: "m" };
      yield { type: "content", content: "David killed Goliath." };
      yield { type: "completion", verses_cited: [] };
    });
    renderChat();
    await send("Who killed Goliath?");
    await screen.findByText("David killed Goliath.");
    expect(screen.queryByTestId("crisis-resources-card")).toBeNull();
  });
});
