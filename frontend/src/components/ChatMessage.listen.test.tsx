import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import ChatMessage from "./ChatMessage";
import { renderWithIntl } from "@/test/i18n-helpers";
import { stop } from "@/lib/speech";
import {
  installSpeechMock,
  makeVoice,
  removeSpeechMock,
} from "@/test/speechMock";

vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}));

const LISTEN = /listen to this answer/i;

beforeEach(() => {
  localStorage.clear();
  installSpeechMock([makeVoice("en-US")]);
  global.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: async () => ({}) } as Response),
  ) as unknown as typeof fetch;
});

afterEach(() => {
  stop();
  removeSpeechMock();
});

describe("ChatMessage — Listen button placement (BITB-119)", () => {
  it("shows Listen on a finished assistant answer", async () => {
    renderWithIntl(
      <ChatMessage
        message={{ role: "assistant", content: "Peace be with you." }}
        messageId="m1"
        onSubmitFeedback={() => {}}
      />,
    );
    expect(await screen.findByRole("button", { name: LISTEN })).toBeVisible();
  });

  it("shows Listen on restored history that has no feedback row", async () => {
    renderWithIntl(
      <ChatMessage message={{ role: "assistant", content: "Peace." }} />,
    );
    expect(await screen.findByRole("button", { name: LISTEN })).toBeVisible();
  });

  it("hides Listen while the answer is still streaming", async () => {
    renderWithIntl(
      <ChatMessage
        message={{ role: "assistant", content: "Peace be" }}
        messageId="m1"
        onSubmitFeedback={() => {}}
        isStreaming
      />,
    );
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole("button", { name: LISTEN })).toBeNull();
  });

  it("hides Listen for an empty assistant answer", async () => {
    renderWithIntl(
      <ChatMessage message={{ role: "assistant", content: "" }} />,
    );
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole("button", { name: LISTEN })).toBeNull();
  });

  it("never shows Listen on user messages", async () => {
    renderWithIntl(<ChatMessage message={{ role: "user", content: "Hi" }} />);
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole("button", { name: LISTEN })).toBeNull();
  });

  it("appears once streaming finishes", async () => {
    const { rerender } = renderWithIntl(
      <ChatMessage
        message={{ role: "assistant", content: "Peace" }}
        isStreaming
      />,
    );
    expect(screen.queryByRole("button", { name: LISTEN })).toBeNull();
    rerender(
      <ChatMessage message={{ role: "assistant", content: "Peace." }} />,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: LISTEN })).toBeVisible(),
    );
  });
});

describe("ChatMessage — sticky action rail (BITB-205)", () => {
  const renderAnswer = () =>
    renderWithIntl(
      <ChatMessage
        message={{ role: "assistant", content: "Peace be with you." }}
        messageId="m1"
        userMessage="Greet me"
        onSubmitFeedback={() => {}}
      />,
    );

  it("renders Listen and Share in a sticky rail beside the bubble", async () => {
    renderAnswer();
    const rail = await screen.findByTestId("message-action-rail");
    expect(rail).toHaveClass("sticky", "self-start");
    expect(
      within(rail).getByRole("button", { name: LISTEN }),
    ).toBeInTheDocument();
    expect(
      within(rail).getByRole("button", { name: /share/i }),
    ).toBeInTheDocument();
    // flex sibling of the bubble, not inside it
    const root = screen.getByTestId("assistant-message");
    expect(rail.parentElement).toBe(root);
    expect(rail.previousElementSibling?.textContent).toContain(
      "Peace be with you.",
    );
  });

  it("keeps only the feedback controls in the bottom row", async () => {
    renderAnswer();
    const rail = await screen.findByTestId("message-action-rail");
    const feedback = screen.getByRole("button", {
      name: /thumbs up|this was helpful|helpful/i,
    });
    expect(rail).not.toContainElement(feedback);
    const bubble = rail.previousElementSibling as HTMLElement;
    expect(bubble).toContainElement(feedback);
    expect(within(bubble).queryByRole("button", { name: LISTEN })).toBeNull();
    expect(within(bubble).queryByRole("button", { name: /share/i })).toBeNull();
  });

  it("shows Listen alone in the rail on restored history (no feedback row)", async () => {
    renderWithIntl(
      <ChatMessage message={{ role: "assistant", content: "Peace." }} />,
    );
    const rail = await screen.findByTestId("message-action-rail");
    expect(
      within(rail).getByRole("button", { name: LISTEN }),
    ).toBeInTheDocument();
    expect(within(rail).queryByRole("button", { name: /share/i })).toBeNull();
  });

  it("has no rail while streaming or on user messages", async () => {
    const { unmount } = renderWithIntl(
      <ChatMessage
        message={{ role: "assistant", content: "Pea" }}
        isStreaming
      />,
    );
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByTestId("message-action-rail")).toBeNull();
    unmount();
    renderWithIntl(<ChatMessage message={{ role: "user", content: "Hi" }} />);
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByTestId("message-action-rail")).toBeNull();
  });
});
