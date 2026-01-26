import { describe, it, expect } from "vitest";
import { extractVerseReferences, isVerseReferenced } from "./verseExtraction";

describe("extractVerseReferences", () => {
  it("should extract simple book references", () => {
    const text = "Check out John 3:16 for encouragement";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract numbered book references (single digit)", () => {
    const text = "Read 1 John 2:3 today";
    const refs = extractVerseReferences(text);
    expect(refs.has("1 john 2:3")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract numbered multi-word books", () => {
    const text = "Consider 2 Corinthians 5:17";
    const refs = extractVerseReferences(text);
    expect(refs.has("2 corinthians 5:17")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it('should extract books with "of" in the name', () => {
    const text = "Song of Solomon 1:1 is beautiful";
    const refs = extractVerseReferences(text);
    expect(refs.has("song of solomon 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should handle verse ranges", () => {
    const text = "Read Matthew 5:3-12 for the beatitudes";
    const refs = extractVerseReferences(text);
    // Should capture the starting verse
    expect(refs.has("matthew 5:3")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract multiple references from text", () => {
    const text = "I'm feeling anxious about John 3:16 and Romans 8:28";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.size).toBe(2);
  });

  it("should extract references from longer sentences", () => {
    const text = "Check out 1 Peter 5:7 and Philippians 4:6-7 for peace";
    const refs = extractVerseReferences(text);
    expect(refs.has("1 peter 5:7")).toBe(true);
    expect(refs.has("philippians 4:6")).toBe(true);
    expect(refs.size).toBe(2);
  });

  it("should not extract false positives from regular text", () => {
    const text = "I have 3 apples and 16 oranges";
    const refs = extractVerseReferences(text);
    expect(refs.size).toBe(0);
  });

  it("should handle empty text", () => {
    const refs = extractVerseReferences("");
    expect(refs.size).toBe(0);
  });

  it("should handle text with no verse references", () => {
    const text = "This is just regular text without any Bible verses";
    const refs = extractVerseReferences("");
    expect(refs.size).toBe(0);
  });

  it("should handle plural book names", () => {
    const text = "Psalms 23:1 is comforting";
    const refs = extractVerseReferences(text);
    expect(refs.has("psalms 23:1")).toBe(true);
  });

  it("should normalize references to lowercase", () => {
    const text = "Read John 3:16 and Matthew 5:5";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("matthew 5:5")).toBe(true);
  });

  it("should extract Italian book names", () => {
    const text = "Leggi Giovanni 3:16 per incoraggiamento";
    const refs = extractVerseReferences(text);
    expect(refs.has("giovanni 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Italian book names with accents", () => {
    const text = "Considera Giosuè 1:9";
    const refs = extractVerseReferences(text);
    expect(refs.has("giosuè 1:9")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German book names", () => {
    const text = "Lies Johannes 3:16 für Ermutigung";
    const refs = extractVerseReferences(text);
    expect(refs.has("johannes 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German book names with umlauts", () => {
    const text = "Betrachte Römer 8:28";
    const refs = extractVerseReferences(text);
    expect(refs.has("römer 8:28")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German numbered books with period", () => {
    const text = "Am Anfang steht 1. Mose 1:1";
    const refs = extractVerseReferences(text);
    expect(refs.has("1. mose 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German book with umlauts and number", () => {
    const text = "Lese 2. Könige 5:14";
    const refs = extractVerseReferences(text);
    expect(refs.has("2. könige 5:14")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should not cause recursion error on large text", () => {
    // This is a regression test for the catastrophic backtracking bug
    const largeText = "John 3:16 and Romans 8:28 ".repeat(1000);
    const start = Date.now();
    const refs = extractVerseReferences(largeText);
    const duration = Date.now() - start;

    // Should complete quickly (under 1 second)
    expect(duration).toBeLessThan(1000);
    // Should find the repeated references
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("romans 8:28")).toBe(true);
  });
});

describe("isVerseReferenced", () => {
  it("should match exact references", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "John 3:16",
    };
    expect(isVerseReferenced(verse, references)).toBe(true);
  });

  it("should match using normalized book names", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "JOHN 3:16",
    };
    expect(isVerseReferenced(verse, references)).toBe(true);
  });

  it("should match singular/plural book names (Psalm vs Psalms)", () => {
    const references = new Set(["psalm 23:1"]);
    const verse = {
      book: "Psalms",
      chapter: 23,
      verse: 1,
      reference: "Psalms 23:1",
    };
    expect(isVerseReferenced(verse, references)).toBe(true);
  });

  it("should match using book/chapter/verse fields", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "Jn 3:16", // Different abbreviation
    };
    expect(isVerseReferenced(verse, references)).toBe(true);
  });

  it("should not match different verses", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "John",
      chapter: 3,
      verse: 17,
      reference: "John 3:17",
    };
    expect(isVerseReferenced(verse, references)).toBe(false);
  });

  it("should not match different books", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "Romans",
      chapter: 3,
      verse: 16,
      reference: "Romans 3:16",
    };
    expect(isVerseReferenced(verse, references)).toBe(false);
  });

  it("should handle empty reference set", () => {
    const references = new Set<string>();
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "John 3:16",
    };
    expect(isVerseReferenced(verse, references)).toBe(false);
  });
});
