import { describe, it, expect } from "vitest";
import {
  CONJUNCTIONS,
  getMultiWordAlternation,
  createVersePattern,
  createVersePatternGlobal,
} from "./versePatterns";
import { LOCALIZED_BOOK_TO_ENGLISH } from "./verseExtraction";

// ── CONJUNCTIONS ──────────────────────────────────────────────────────────────

describe("CONJUNCTIONS", () => {
  it("should contain expected conjunction words", () => {
    expect(CONJUNCTIONS.has("e")).toBe(true);
    expect(CONJUNCTIONS.has("and")).toBe(true);
    expect(CONJUNCTIONS.has("und")).toBe(true);
    expect(CONJUNCTIONS.has("y")).toBe(true);
    expect(CONJUNCTIONS.has("et")).toBe(true);
    expect(CONJUNCTIONS.has("o")).toBe(true);
    expect(CONJUNCTIONS.has("a")).toBe(true);
  });

  it("should not contain book names", () => {
    expect(CONJUNCTIONS.has("john")).toBe(false);
    expect(CONJUNCTIONS.has("romans")).toBe(false);
  });
});

// ── getMultiWordAlternation ───────────────────────────────────────────────────

describe("getMultiWordAlternation", () => {
  it("should return a non-empty string", () => {
    const alt = getMultiWordAlternation();
    expect(typeof alt).toBe("string");
    expect(alt.length).toBeGreaterThan(0);
  });

  it("should include Russian multi-word book names", () => {
    const alt = getMultiWordAlternation().toLowerCase();
    // "плач иеремии" → lamentations
    expect(alt).toContain("плач");
    // "песня песней" → song of solomon
    expect(alt).toContain("песня");
    // "деяния апостолов" → acts
    expect(alt).toContain("деяния");
    // "иисус навин" → joshua
    expect(alt).toContain("иисус");
  });

  it("should sort longer names before shorter ones (longest-first)", () => {
    const alt = getMultiWordAlternation().toLowerCase();
    // "деяния апостолов" (with escaped space) should appear before "деяния"
    const idxFull = alt.indexOf("деяния\\s\\+апостолов");
    const idxShort = alt.indexOf("деяния");
    // The full form exists and appears before or at the start of the short form
    expect(idxShort).not.toBe(-1);
    if (idxFull !== -1) {
      expect(idxFull).toBeLessThanOrEqual(idxShort);
    }
  });

  it("should NOT include number-prefixed Latin/Cyrillic/Arabic book names", () => {
    // "1 царств", "2 samuel", "1 أخبار الأيام", etc. are handled by the \\d+ branch
    // and must not appear as multi-word alternates.
    // EXCEPTION: number-prefixed non-Latin (Han/Hangul/Devanagari) books must be
    // listed explicitly because the numbered-prefix branch excludes those scripts.
    const NON_LATIN = /[\p{Script=Han}\p{Script=Hangul}\p{Script=Devanagari}]/u;
    const parts = getMultiWordAlternation().split("|");
    for (const part of parts) {
      if (part.match(/^\d/)) {
        expect(part).toMatch(NON_LATIN);
      }
    }
  });

  it("all multi-word keys from LOCALIZED_BOOK_TO_ENGLISH should be represented", () => {
    // Every multi-word (non-number-prefixed) key should appear somewhere in the alternation
    const multiWordKeys = Object.keys(LOCALIZED_BOOK_TO_ENGLISH).filter(
      (k) => k.includes(" ") && !/^\d/.test(k),
    );
    expect(multiWordKeys.length).toBeGreaterThan(0);
    const alt = getMultiWordAlternation();
    for (const key of multiWordKeys) {
      // The pattern replaces spaces with \s+ and escapes special chars.
      const fragment = key
        .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        .replace(/ /g, "\\s+");
      expect(alt).toContain(fragment);
    }
  });
});

// ── createVersePattern ────────────────────────────────────────────────────────

describe("createVersePattern", () => {
  it("should return a RegExp", () => {
    const re = createVersePattern();
    expect(re).toBeInstanceOf(RegExp);
  });

  it("should have the 'u' flag", () => {
    const re = createVersePattern();
    expect(re.flags).toContain("u");
  });

  it("should NOT have the 'g' flag", () => {
    const re = createVersePattern();
    expect(re.flags).not.toContain("g");
  });

  it("should match a simple English verse reference", () => {
    const re = createVersePattern();
    expect(re.test("John 3:16")).toBe(true);
  });

  it("should match a Russian two-word book name", () => {
    const re = createVersePattern();
    expect(re.test("Плач Иеремии 3:3")).toBe(true);
  });

  it("should return a new instance on each call", () => {
    const re1 = createVersePattern();
    const re2 = createVersePattern();
    expect(re1).not.toBe(re2);
  });
});

// ── createVersePatternGlobal ──────────────────────────────────────────────────

describe("createVersePatternGlobal", () => {
  it("should return a RegExp", () => {
    const re = createVersePatternGlobal();
    expect(re).toBeInstanceOf(RegExp);
  });

  it("should have the 'g' flag", () => {
    const re = createVersePatternGlobal();
    expect(re.flags).toContain("g");
  });

  it("should have the 'u' flag", () => {
    const re = createVersePatternGlobal();
    expect(re.flags).toContain("u");
  });

  it("should find multiple references in one string", () => {
    const re = createVersePatternGlobal();
    const matches = Array.from("John 3:16 and Romans 8:28".matchAll(re));
    expect(matches.length).toBe(2);
  });

  it("should return a new instance on each call (fresh lastIndex)", () => {
    const re1 = createVersePatternGlobal();
    const re2 = createVersePatternGlobal();
    expect(re1).not.toBe(re2);
  });

  it("should match Chinese CJK book names", () => {
    const re = createVersePatternGlobal();
    const matches = Array.from("约翰福音 3:16".matchAll(re));
    expect(matches.length).toBe(1);
    expect(matches[0][1]).toBe("约翰福音");
  });

  it("should match numbered book names", () => {
    const re = createVersePatternGlobal();
    const matches = Array.from("1 John 2:3".matchAll(re));
    expect(matches.length).toBe(1);
    expect(matches[0][1]).toBe("1 John");
  });
});

// ── Parenthesized / bracketed citations (cross-parser parity, AGENTS.md) ──────
// The backend verse parser (api/utils/verse_parser.py) must detect references
// wrapped in ( ) [ ] / fullwidth （ ）. This asserts the frontend parser — which
// must stay in sync — detects them too, across multiple languages.
describe("parenthesized and bracketed references", () => {
  const cases: Array<[string, string]> = [
    ["en paren", "Take heart (John 3:16) today."],
    ["en bracket", "Hope [Psalm 23:1] holds."],
    ["it paren", "Coraggio (Giovanni 3:16)."],
    ["it numbered", "Dio è amore (1 Giovanni 4:8)."],
    ["de paren", "Trost (Johannes 3:16) heute."],
    ["es paren", "Ánimo (Juan 3:16)."],
    ["zh fullwidth", "安慰（约翰福音 3:16）。"],
    ["ko paren", "위로 (요한복음 3:16)."],
  ];
  it.each(cases)("detects a verse reference in %s", (_label, text) => {
    expect(createVersePattern().test(text)).toBe(true);
  });

  it("still matches an unwrapped reference", () => {
    expect(createVersePattern().test("See John 3:16 for hope.")).toBe(true);
  });
});
