import { screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChapterModal from "./ChapterModal";
import { renderWithIntl } from "@/test/i18n-helpers";

describe("ChapterModal responsive layout", () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    book: "Genesis",
    chapter: 1,
    verses: [
      {
        book: "Genesis",
        chapter: 1,
        verse: 1,
        text: "In the beginning...",
        reference: "Genesis 1:1",
      },
      {
        book: "Genesis",
        chapter: 1,
        verse: 2,
        text: "And the earth was...",
        reference: "Genesis 1:2",
      },
    ],
    highlightVerse: 1,
  };

  it("renders modal with responsive rounded corners (full screen on mobile)", () => {
    const { container } = renderWithIntl(<ChapterModal {...defaultProps} />);
    // The modal panel should have sm:rounded-2xl (no rounding on mobile)
    const modal = container.querySelector('[class*="shadow-2xl"]');
    expect(modal).not.toBeNull();
    expect(modal!.className).toContain("sm:rounded-2xl");
    // Should not have standalone rounded-2xl (only sm: prefixed)
    const classes = modal!.className.split(" ");
    expect(classes).not.toContain("rounded-2xl");
  });

  it("renders modal with responsive max-height (full screen on mobile)", () => {
    const { container } = renderWithIntl(<ChapterModal {...defaultProps} />);
    const modal = container.querySelector('[class*="shadow-2xl"]');
    expect(modal!.className).toContain("max-h-screen");
    expect(modal!.className).toContain("sm:max-h-[85vh]");
  });

  it("renders modal with responsive margin (no margin on mobile)", () => {
    const { container } = renderWithIntl(<ChapterModal {...defaultProps} />);
    const modal = container.querySelector('[class*="shadow-2xl"]');
    expect(modal!.className).toContain("sm:m-4");
    // Should not have standalone m-4 (only sm: prefixed)
    const classes = modal!.className.split(" ");
    expect(classes).not.toContain("m-4");
  });

  it("renders header with responsive padding and text sizes", () => {
    renderWithIntl(<ChapterModal {...defaultProps} />);
    const heading = screen.getByText("Genesis 1");
    expect(heading.className).toContain("text-xl");
    expect(heading.className).toContain("sm:text-2xl");

    // Header container should have responsive padding
    const header = heading.closest('[class*="border-b"]');
    expect(header!.className).toContain("p-4");
    expect(header!.className).toContain("sm:p-5");
  });

  it("renders content area with responsive padding", () => {
    const { container } = renderWithIntl(<ChapterModal {...defaultProps} />);
    const content = container.querySelector('[class*="overflow-y-auto"]');
    expect(content!.className).toContain("px-4");
    expect(content!.className).toContain("py-4");
    expect(content!.className).toContain("sm:px-6");
    expect(content!.className).toContain("sm:py-5");
  });

  it("does not render when isOpen is false", () => {
    const { container } = renderWithIntl(
      <ChapterModal {...defaultProps} isOpen={false} />,
    );
    expect(container.innerHTML).toBe("");
  });
});
