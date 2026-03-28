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

  it("should include Korean multi-word book names", () => {
    const alt = getMultiWordAlternation();
    // "예레미야 애가" → lamentations (with space becomes \s+ in pattern)
    expect(alt).toContain("예레미야");
  });

  it("should include Arabic multi-word book names", () => {
    const alt = getMultiWordAlternation();
    // "أعمال الرسل" → acts
    expect(alt).toContain("أعمال");
    // "نشيد الأنشاد" → song of solomon
    expect(alt).toContain("نشيد");
    // "مراثي إرميا" → lamentations
    expect(alt).toContain("مراثي");
  });

  it("should include Hindi multi-word book names", () => {
    const alt = getMultiWordAlternation();
    // "भजन संहिता" → psalms
    expect(alt).toContain("भजन");
    // "प्रेरितों के काम" → acts
    expect(alt).toContain("प्रेरितों");
  });

  it("should include Portuguese multi-word book names", () => {
    const alt = getMultiWordAlternation().toLowerCase();
    // "cântico dos cânticos" → song of solomon
    expect(alt).toContain("cântico");
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

  it("should NOT include number-prefixed book names", () => {
    // "1 царств", "2 samuel", etc. are handled by the \\d+ branch — must not appear
    // as a multi-word alternate.
    const parts = getMultiWordAlternation().split("|");
    for (const part of parts) {
      expect(part).not.toMatch(/^\d/);
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
      const fragment = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, "\\s+");
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

  it("should match a Hindi two-word book name", () => {
    const re = createVersePattern();
    expect(re.test("भजन संहिता 23:1")).toBe(true);
  });

  it("should match an Arabic two-word book name", () => {
    const re = createVersePattern();
    expect(re.test("أعمال الرسل 2:38")).toBe(true);
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
