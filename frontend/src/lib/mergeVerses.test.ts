import { describe, it, expect } from "vitest";
import { mergeVerses } from "./mergeVerses";
import type { Verse } from "./api";

function v(reference: string, overrides: Partial<Verse> = {}): Verse {
  const [bookChapter, verseStr] = reference.split(":");
  const parts = bookChapter.split(" ");
  const verse = parseInt(verseStr ?? "1", 10);
  const chapter = parseInt(parts[parts.length - 1] ?? "1", 10);
  const book = parts.slice(0, -1).join(" ");
  return {
    reference,
    text: `text for ${reference}`,
    book,
    chapter,
    verse,
    ...overrides,
  };
}

describe("mergeVerses", () => {
  it("appends extra verses not already in the pool", () => {
    const pool = [v("Philippians 4:6")];
    const extra = [v("John 14:27")];

    const result = mergeVerses(pool, extra);

    const refs = result.map((x) => x.reference);
    expect(refs).toContain("Philippians 4:6");
    expect(refs).toContain("John 14:27");
    expect(result).toHaveLength(2);
  });

  it("dedupes by normalized reference, keeping the pool entry", () => {
    const pool = [v("John 3:16", { text: "pool text" })];
    const extra = [v("john 3:16", { text: "extra text" })];

    const result = mergeVerses(pool, extra);

    expect(result).toHaveLength(1);
    expect(result[0].text).toBe("pool text");
  });

  it("preserves pool order and appends extras after", () => {
    const pool = [v("Genesis 1:1"), v("Exodus 2:2")];
    const extra = [v("Mark 1:1"), v("Genesis 1:1")];

    const result = mergeVerses(pool, extra);

    expect(result.map((x) => x.reference)).toEqual([
      "Genesis 1:1",
      "Exodus 2:2",
      "Mark 1:1",
    ]);
  });

  it("handles empty / undefined extra gracefully", () => {
    const pool = [v("John 3:16")];
    expect(mergeVerses(pool, [])).toHaveLength(1);
    expect(mergeVerses(pool, undefined)).toHaveLength(1);
  });

  it("dedupes within the extra list too", () => {
    const pool: Verse[] = [];
    const extra = [v("Acts 2:1"), v("acts 2:1")];

    const result = mergeVerses(pool, extra);

    expect(result).toHaveLength(1);
  });
});
