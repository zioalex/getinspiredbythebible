import fs from "fs";
import path from "path";
import { describe, it, expect } from "vitest";
import { linkifyVerses } from "./linkifyVerses";
import { linkifyWithCitations, CitationSpan } from "./citationSpans";
import { createVersePatternGlobal } from "./versePatterns";
import { isKnownBook } from "./verseExtraction";
import { normalizeTraditionalToSimplified } from "./chineseScript";

interface CorpusCase {
  id: string;
  input: string;
  language: string;
  expected: {
    book: string;
    chapter: number;
    verseStart: number;
    verseEnd: number | null;
  } | null;
  expectNone?: boolean;
  skip?: string[];
}

const corpusPath = path.join(
  __dirname,
  "../../../tests/fixtures/verse_reference_corpus.json",
);
const corpus: { test_cases: CorpusCase[] } = JSON.parse(
  fs.readFileSync(corpusPath, "utf-8"),
);

// Note on `book`: a real CitationSpan.book is the canonical English name
// (e.g. "John" — see api/utils/verse_parser.py's CitationSpan docstring),
// which for a non-English match (e.g. "Matthäus") is a different STRING
// from what the regex path puts in its own href, even though both resolve
// to the same book via normalize_book_name(). Byte-identical parity can
// only be tested by giving the span the same book string the regex match
// itself produced — using the corpus's normalized `expected.book` instead
// would make this suite fail on href casing/localization alone, which is a
// fixture-data mismatch, not a citationSpans bug.
describe("linkifyWithCitations — corpus parity (BITB-109)", () => {
  let comparedCount = 0;

  for (const testCase of corpus.test_cases) {
    if (testCase.expectNone) continue;
    if (testCase.skip?.includes("web")) continue;

    it(`matches the regex path for corpus case "${testCase.id}"`, () => {
      const pattern = createVersePatternGlobal();
      const search = normalizeTraditionalToSimplified(testCase.input);
      const match = pattern.exec(search);

      // A residual few corpus cases may not match this regex flavor at all
      // (e.g. cases exercised only by the Python/Kotlin implementations) —
      // that's not a citationSpans bug, so skip rather than fail.
      if (!match) return;

      const book = match[1].trim();
      if (!isKnownBook(book)) return;

      const start = match.index;
      const end = match.index + match[0].length;
      const text = testCase.input.slice(start, end);

      const span: CitationSpan = {
        text,
        start,
        end,
        occurrence: 0,
        book: match[1].trim(),
        chapter: testCase.expected!.chapter,
        verse: testCase.expected!.verseStart,
        verse_end: testCase.expected!.verseEnd,
      };

      comparedCount++;
      expect(linkifyWithCitations(testCase.input, [span])).toBe(
        linkifyVerses(testCase.input),
      );
    });
  }

  it("actually compared a meaningful number of corpus cases (test isn't vacuous)", () => {
    expect(comparedCount).toBeGreaterThanOrEqual(20);
  });
});

describe("linkifyWithCitations — citations absent", () => {
  it("falls back to the regex path byte-for-byte when citations is undefined", () => {
    const messages = [
      "Lies Johannes 3,16 heute.",
      "See John 3:16 and Romans 8:28 for context.",
      "No verse references here at all.",
    ];
    for (const md of messages) {
      expect(linkifyWithCitations(md, undefined)).toBe(linkifyVerses(md));
    }
  });
});

describe("linkifyWithCitations — citations is an empty array", () => {
  it("still runs the regex fallback (an empty array must not suppress it)", () => {
    const md = "Read John 3:16 for encouragement today.";
    expect(linkifyWithCitations(md, [])).toBe(linkifyVerses(md));
    expect(linkifyWithCitations(md, [])).toContain(
      "[John 3:16](verse://John/3/16)",
    );
  });
});

describe("linkifyWithCitations — valid span parity on prose", () => {
  it("renders identically to the regex path for a realistic multi-sentence reply", () => {
    const md =
      "Peace be with you. As it says in John 3:16, God loved the world. " +
      "Consider also Romans 8:28, which reminds us that all things work together for good.";

    const johnStart = md.indexOf("John 3:16");
    const johnEnd = johnStart + "John 3:16".length;
    const romansStart = md.indexOf("Romans 8:28");
    const romansEnd = romansStart + "Romans 8:28".length;

    const spans: CitationSpan[] = [
      {
        text: "John 3:16",
        start: johnStart,
        end: johnEnd,
        occurrence: 0,
        book: "John",
        chapter: 3,
        verse: 16,
        verse_end: null,
      },
      {
        text: "Romans 8:28",
        start: romansStart,
        end: romansEnd,
        occurrence: 0,
        book: "Romans",
        chapter: 8,
        verse: 28,
        verse_end: null,
      },
    ];

    expect(linkifyWithCitations(md, spans)).toBe(linkifyVerses(md));
  });
});

describe("linkifyWithCitations — self-verification failure + occurrence recovery", () => {
  it("recovers the correct position when start/end are wrong but text/occurrence are right", () => {
    const md = "As it says in John 3:16, God loved the world.";
    const trueStart = md.indexOf("John 3:16");
    const span: CitationSpan = {
      text: "John 3:16",
      start: trueStart + 4, // deliberately wrong offsets
      end: trueStart + 4 + "John 3:16".length,
      occurrence: 0,
      book: "John",
      chapter: 3,
      verse: 16,
      verse_end: null,
    };
    const out = linkifyWithCitations(md, [span]);
    expect(out).toContain("verse://John/3/16");
    expect(out).toContain("[John 3:16](verse://John/3/16)");
  });

  it("recovers the second occurrence of a repeated reference by its occurrence index", () => {
    const md = "See John 3:16. Again, John 3:16 is worth memorizing.";
    const firstStart = md.indexOf("John 3:16");
    const secondStart = md.indexOf("John 3:16", firstStart + 1);
    const span: CitationSpan = {
      text: "John 3:16",
      start: -1, // deliberately invalid — forces occurrence-based recovery
      end: -1,
      occurrence: 1,
      book: "John",
      chapter: 3,
      verse: 16,
      verse_end: null,
    };
    const out = linkifyWithCitations(md, [span]);
    expect(out.indexOf("[John 3:16](verse://John/3/16)")).toBeGreaterThan(
      -1,
    );
    // The first occurrence should still be handled by the regex fallback,
    // and the second by the recovered span — both end up linked once each.
    expect(out.split("[John 3:16](verse://John/3/16)").length - 1).toBe(2);
    expect(secondStart).toBeGreaterThan(firstStart);
  });
});

describe("linkifyWithCitations — corrupt spans (adversarial)", () => {
  it("does not throw and keeps the text when end is past end-of-string", () => {
    const md = "See John 3:16 today.";
    const span: CitationSpan = {
      text: "John 3:16",
      start: md.indexOf("John 3:16"),
      end: md.length + 50,
      occurrence: 0,
      book: "John",
      chapter: 3,
      verse: 16,
      verse_end: null,
    };
    let out = "";
    expect(() => {
      out = linkifyWithCitations(md, [span]);
    }).not.toThrow();
    // Offsets don't self-verify and "John 3:16" alone doesn't literally
    // occur at that exact substring, but occurrence-recovery should still
    // find the real "John 3:16" in the text — verify the reference isn't lost.
    expect(out).toContain("John 3:16");
  });

  it("falls back to plain regex handling when text is mismatched and unrecoverable", () => {
    const md = "See John 3:16 today.";
    const span: CitationSpan = {
      text: "Nonexistent 99:99",
      start: 0,
      end: 5,
      occurrence: 0,
      book: "John",
      chapter: 3,
      verse: 16,
      verse_end: null,
    };
    let out = "";
    expect(() => {
      out = linkifyWithCitations(md, [span]);
    }).not.toThrow();
    expect(out).toBe(linkifyVerses(md));
    expect(out).toContain("John 3:16");
  });

  it("renders the reference exactly once when two spans overlap the same text", () => {
    const md = "See John 3:16 today.";
    const start = md.indexOf("John 3:16");
    const end = start + "John 3:16".length;
    const spanA: CitationSpan = {
      text: "John 3:16",
      start,
      end,
      occurrence: 0,
      book: "John",
      chapter: 3,
      verse: 16,
      verse_end: null,
    };
    const spanB: CitationSpan = {
      text: "John 3:16",
      start: start - 1 < 0 ? start : start - 1, // overlaps spanA's range
      end: end - 1,
      occurrence: 0,
      book: "John",
      chapter: 3,
      verse: 16,
      verse_end: null,
    };
    let out = "";
    expect(() => {
      out = linkifyWithCitations(md, [spanA, spanB]);
    }).not.toThrow();
    expect(out.split("verse://John/3/16").length - 1).toBe(1);
    expect(out).toContain("John 3:16");
  });

  it("treats an empty-string text span as invalid and falls through to regex", () => {
    const md = "See John 3:16 today.";
    const span: CitationSpan = {
      text: "",
      start: 0,
      end: 0,
      occurrence: 0,
      book: "John",
      chapter: 3,
      verse: 16,
      verse_end: null,
    };
    let out = "";
    expect(() => {
      out = linkifyWithCitations(md, [span]);
    }).not.toThrow();
    expect(out).toBe(linkifyVerses(md));
    expect(out).toContain("John 3:16");
  });
});

describe("linkifyWithCitations — vocalized-Arabic fallback (documented BITB-086 gap)", () => {
  it("still links a vocalized-Arabic reference the server didn't emit a span for", () => {
    // Same case already covered for linkifyVerses in linkifyVerses.test.ts —
    // simulating the server omitting this citation from `citations` entirely.
    const text = "يوحنا ٣:١٦";
    const out = linkifyWithCitations(text, []);
    expect(out).toContain(
      "[يوحنا ٣:١٦](verse://%D9%8A%D9%88%D8%AD%D9%86%D8%A7/3/16)",
    );
  });
});
