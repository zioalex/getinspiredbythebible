import { screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import VerseCard from "./VerseCard";
import { renderWithIntl } from "@/test/i18n-helpers";
import { Verse } from "@/lib/api";

const baseVerse: Verse = {
  reference: "John 3:16",
  text: "For God so loved the world...",
  book: "John",
  chapter: 3,
  verse: 16,
};

describe("VerseCard", () => {
  it("renders verse reference and text", () => {
    renderWithIntl(<VerseCard verse={baseVerse} />);
    expect(screen.getByText("John 3:16")).toBeDefined();
    expect(screen.getByText(/For God so loved the world/)).toBeDefined();
  });

  it("shows similarity percentage when similarity is provided", () => {
    const verse: Verse = { ...baseVerse, similarity: 0.85 };
    renderWithIntl(<VerseCard verse={verse} />);
    expect(screen.getByText("85%")).toBeDefined();
  });

  it("shows green relevance color for similarity > 0.7", () => {
    const verse: Verse = { ...baseVerse, similarity: 0.85 };
    const { container } = renderWithIntl(<VerseCard verse={verse} />);
    const dot = container.querySelector(".bg-green-400");
    expect(dot).not.toBeNull();
  });

  it("shows yellow relevance color for similarity > 0.5", () => {
    const verse: Verse = { ...baseVerse, similarity: 0.6 };
    const { container } = renderWithIntl(<VerseCard verse={verse} />);
    const dot = container.querySelector(".bg-yellow-400");
    expect(dot).not.toBeNull();
  });

  it("shows orange relevance color for similarity <= 0.5", () => {
    const verse: Verse = { ...baseVerse, similarity: 0.4 };
    const { container } = renderWithIntl(<VerseCard verse={verse} />);
    const dot = container.querySelector(".bg-orange-400");
    expect(dot).not.toBeNull();
  });

  it("shows translation badge when translation is provided", () => {
    const verse: Verse = { ...baseVerse, translation: "kjv" };
    renderWithIntl(<VerseCard verse={verse} />);
    expect(screen.getByText("KJV")).toBeDefined();
  });

  it("shows localized book name when localized_book is set", () => {
    const verse: Verse = { ...baseVerse, localized_book: "Giovanni" };
    renderWithIntl(<VerseCard verse={verse} />);
    expect(screen.getByText("Giovanni 3:16")).toBeDefined();
  });

  it("shows 'Read full chapter' link when onClick is provided", () => {
    renderWithIntl(<VerseCard verse={baseVerse} onClick={vi.fn()} />);
    expect(screen.getByText("Read full chapter")).toBeDefined();
  });

  it("hides 'Read full chapter' when no onClick", () => {
    renderWithIntl(<VerseCard verse={baseVerse} />);
    expect(screen.queryByText("Read full chapter")).toBeNull();
  });
});
