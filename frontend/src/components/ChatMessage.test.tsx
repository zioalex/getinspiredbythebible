import { screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ChatMessage from "./ChatMessage";
import { renderWithIntl } from "@/test/i18n-helpers";

// Mock react-markdown to avoid complex rendering
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}));

describe("ChatMessage responsive classes", () => {
  it("renders user message with responsive gap and avatar sizes", () => {
    const { container } = renderWithIntl(
      <ChatMessage message={{ role: "user", content: "Hello" }} />,
    );

    // Outer flex container should have responsive gap
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("gap-2");
    expect(wrapper.className).toContain("sm:gap-4");
  });

  it("renders user avatar with responsive size", () => {
    renderWithIntl(
      <ChatMessage message={{ role: "user", content: "Hello" }} />,
    );
    const avatars = document.querySelectorAll('[class*="rounded-full"]');
    const userAvatar = avatars[0];
    expect(userAvatar.className).toContain("w-8");
    expect(userAvatar.className).toContain("h-8");
    expect(userAvatar.className).toContain("sm:w-10");
    expect(userAvatar.className).toContain("sm:h-10");
  });

  it("renders assistant avatar with responsive size", () => {
    renderWithIntl(
      <ChatMessage
        message={{ role: "assistant", content: "Peace be with you" }}
      />,
    );
    const avatars = document.querySelectorAll('[class*="rounded-full"]');
    const assistantAvatar = avatars[0];
    expect(assistantAvatar.className).toContain("w-8");
    expect(assistantAvatar.className).toContain("h-8");
    expect(assistantAvatar.className).toContain("sm:w-10");
    expect(assistantAvatar.className).toContain("sm:h-10");
  });

  it("renders message bubble with responsive max-width and padding", () => {
    const { container } = renderWithIntl(
      <ChatMessage message={{ role: "user", content: "Hello" }} />,
    );
    const bubble = container.querySelector('[class*="rounded-2xl"]');
    expect(bubble).not.toBeNull();
    expect(bubble!.className).toContain("max-w-[90%]");
    expect(bubble!.className).toContain("sm:max-w-[80%]");
    expect(bubble!.className).toContain("px-4");
    expect(bubble!.className).toContain("py-3");
    expect(bubble!.className).toContain("sm:px-5");
    expect(bubble!.className).toContain("sm:py-4");
  });
});

// Regression for the reported "thumbs up/down not visible" bug. The feedback
// row has no screen-size gate, so a missing render is driven entirely by the
// `messageId`/`onSubmitFeedback` props (e.g. a backend response that omits
// `message_id`). These tests pin that render condition on the same component
// used for both desktop and mobile.
describe("ChatMessage feedback controls visibility", () => {
  it("shows thumbs up/down when an assistant message has a messageId and handler", () => {
    renderWithIntl(
      <ChatMessage
        message={{ role: "assistant", content: "Peace be with you" }}
        messageId="msg-1"
        onSubmitFeedback={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Thumbs up")).toBeDefined();
    expect(screen.getByLabelText("Thumbs down")).toBeDefined();
  });

  it("does not render thumbs when messageId is missing", () => {
    renderWithIntl(
      <ChatMessage
        message={{ role: "assistant", content: "Peace be with you" }}
        onSubmitFeedback={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText("Thumbs up")).toBeNull();
    expect(screen.queryByLabelText("Thumbs down")).toBeNull();
  });

  it("does not render thumbs on user messages", () => {
    renderWithIntl(
      <ChatMessage
        message={{ role: "user", content: "Hello" }}
        messageId="msg-1"
        onSubmitFeedback={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText("Thumbs up")).toBeNull();
  });
});

describe("ChatMessage copy user prompt (BITB-047)", () => {
  const writeText = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    writeText.mockReset();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
  });

  it("renders copy button on user messages", () => {
    renderWithIntl(
      <ChatMessage message={{ role: "user", content: "My question" }} />,
    );
    expect(screen.getByLabelText("Copy message")).toBeDefined();
  });

  it("does not render copy button on assistant messages", () => {
    renderWithIntl(
      <ChatMessage message={{ role: "assistant", content: "An answer" }} />,
    );
    expect(screen.queryByLabelText("Copy message")).toBeNull();
  });

  it("copies question text to clipboard on click", async () => {
    renderWithIntl(
      <ChatMessage message={{ role: "user", content: "My question" }} />,
    );
    await act(async () => {
      fireEvent.click(screen.getByLabelText("Copy message"));
    });
    expect(writeText).toHaveBeenCalledWith("My question");
  });

  it("shows checkmark after copy and reverts after 2s", async () => {
    vi.useFakeTimers();
    renderWithIntl(
      <ChatMessage message={{ role: "user", content: "My question" }} />,
    );
    await act(async () => {
      fireEvent.click(screen.getByLabelText("Copy message"));
    });
    // waitFor polls via setInterval which is faked — assert directly after act flushes microtasks
    expect(screen.getByLabelText("Copied")).toBeDefined();
    await act(async () => {
      vi.advanceTimersByTime(2100);
    });
    expect(screen.getByLabelText("Copy message")).toBeDefined();
    vi.useRealTimers();
  });
});
