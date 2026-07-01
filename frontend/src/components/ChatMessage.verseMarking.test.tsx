import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChatMessage from "./ChatMessage";
import { renderWithIntl } from "@/test/i18n-helpers";
import type { Message } from "@/lib/api";

// NOTE: unlike ChatMessage.test.tsx, this suite uses the REAL react-markdown so
// the custom `p` / `a` renderers (which produce the inline verse marking) run.

function renderAssistant(content: string, onVerseClick = vi.fn()) {
  const message: Message = { role: "assistant", content };
  const utils = renderWithIntl(
    <ChatMessage message={message} onVerseClick={onVerseClick} />,
  );
  return { ...utils, onVerseClick };
}

describe("ChatMessage inline verse marking — real references", () => {
  it("marks a plain-text reference as an amber clickable span", () => {
    renderAssistant("Wie es in Hiob 7:3 heißt, finden wir Trost.");
    const span = screen.getByText("Hiob 7:3");
    expect(span.tagName).toBe("SPAN");
    expect(span.className).toContain("text-amber-800");
    expect(span.className).toContain("cursor-pointer");
  });

  it("calls onVerseClick with the parsed book/chapter/verse", () => {
    const { onVerseClick } = renderAssistant("Lies Hiob 7:3 heute.");
    fireEvent.click(screen.getByText("Hiob 7:3"));
    expect(onVerseClick).toHaveBeenCalledWith("Hiob", 7, 3);
  });

  it("marks multiple references in the same paragraph", () => {
    renderAssistant("Siehe Hiob 7:3 und auch Psalm 70:3 heute.");
    expect(screen.getByText("Hiob 7:3").className).toContain("text-amber-800");
    expect(screen.getByText("Psalm 70:3").className).toContain(
      "text-amber-800",
    );
  });
});

describe("ChatMessage inline verse marking — connector-word regression", () => {
  // A connector word ("of", "de", …) before a real book name used to let a
  // greedy alternative swallow the preceding prose ("you of Psalm"), which
  // failed the known-book check and left the real reference unlinked.
  it("marks a reference preceded by the English connector 'of'", () => {
    renderAssistant("I also want to remind you of Psalm 56:9, which says.");
    const span = screen.getByText("Psalm 56:9");
    expect(span.tagName).toBe("SPAN");
    expect(span.className).toContain("text-amber-800");
  });

  it("calls onVerseClick for a connector-preceded reference", () => {
    const { onVerseClick } = renderAssistant("the promise of Isaiah 41:10 is sure.");
    fireEvent.click(screen.getByText("Isaiah 41:10"));
    expect(onVerseClick).toHaveBeenCalledWith("Isaiah", 41, 10);
  });

  it("marks a reference preceded by the Spanish connector 'de'", () => {
    renderAssistant("Recuerda la palabra de Isaías 41:10 hoy.");
    expect(screen.getByText("Isaías 41:10").className).toContain(
      "text-amber-800",
    );
  });

  it("still marks a legitimate multi-word book (Song of Solomon)", () => {
    renderAssistant("Read Song of Solomon 2:1 for beauty.");
    expect(screen.getByText("Song of Solomon 2:1").className).toContain(
      "text-amber-800",
    );
  });
});

describe("ChatMessage inline verse marking — no longer cuts text", () => {
  it("does not mark German prose that merely contains numbers", () => {
    const text = "Gott schenkt uns Trost der Hoffnung 5:5 jeden Tag.";
    const { container } = renderAssistant(text);
    // The full sentence is preserved …
    expect(container.textContent).toContain(text);
    // … and nothing inside it became an amber verse span.
    expect(container.querySelectorAll("span.text-amber-800").length).toBe(0);
  });

  it("does not mark a clock time as a verse", () => {
    const text = "Wir treffen uns um 14:30 Uhr.";
    const { container } = renderAssistant(text);
    expect(container.textContent).toContain(text);
    expect(container.querySelectorAll("span.text-amber-800").length).toBe(0);
  });

  it("does not swallow a whole clause via greedy over-match", () => {
    const text = "In 1. Mose lesen wir dass Gott alles 1:1 erschuf.";
    const { container } = renderAssistant(text);
    expect(container.textContent).toContain(text);
    expect(container.querySelectorAll("span.text-amber-800").length).toBe(0);
  });
});

describe("ChatMessage inline verse marking — markdown links", () => {
  it("renders a verse-reference link as an amber clickable span (not a blue <a>)", () => {
    const { container, onVerseClick } = renderAssistant(
      "Wie es in [Hiob 7:3](https://example.com/hiob-7-3) heißt.",
    );
    const span = screen.getByText("Hiob 7:3");
    expect(span.tagName).toBe("SPAN");
    expect(span.className).toContain("text-amber-800");
    // It must NOT be rendered as an anchor element.
    expect(container.querySelector('a[href*="hiob-7-3"]')).toBeNull();
    // Clicking opens the in-app verse view.
    fireEvent.click(span);
    expect(onVerseClick).toHaveBeenCalledWith("Hiob", 7, 3);
  });

  it("works for a localized (Korean) reference link", () => {
    const { onVerseClick } = renderAssistant(
      "[요한복음 3:16](https://example.com/jn) 말씀입니다.",
    );
    const span = screen.getByText("요한복음 3:16");
    expect(span.className).toContain("text-amber-800");
    fireEvent.click(span);
    expect(onVerseClick).toHaveBeenCalledWith("요한복음", 3, 16);
  });

  it("keeps a non-verse link as a real anchor", () => {
    const { container } = renderAssistant(
      "See [Bible Gateway](https://www.biblegateway.com) for more.",
    );
    const anchor = container.querySelector("a");
    expect(anchor).not.toBeNull();
    expect(anchor!.getAttribute("href")).toBe("https://www.biblegateway.com");
    expect(anchor!.textContent).toBe("Bible Gateway");
  });
});
