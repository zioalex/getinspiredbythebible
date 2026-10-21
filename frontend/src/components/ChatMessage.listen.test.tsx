import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
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
  it("shows Listen in the feedback row of a finished assistant answer", async () => {
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
