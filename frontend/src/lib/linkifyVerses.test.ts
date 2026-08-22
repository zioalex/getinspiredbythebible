import { describe, it, expect } from "vitest";
import { linkifyVerses, parseVerseHref } from "./linkifyVerses";

describe("linkifyVerses", () => {
  it("links a reference in prose", () => {
    expect(linkifyVerses("Lies Johannes 3,16 heute.")).toContain(
      "[Johannes 3,16](verse://Johannes/3/16)",
    );
  });

  it("links references inside list items (the reported bug)", () => {
    const md = [
      '- Römer 12,14: "Segnet, die euch verfolgen"',
      '- Matthäus 5,44: "Liebet eure Feinde"',
      '- Lukas 6,28: "segnet, die euch fluchen"',
    ].join("\n");
    const out = linkifyVerses(md);
    expect(out).toContain("[Römer 12,14](verse://R%C3%B6mer/12/14)");
    expect(out).toContain("[Matthäus 5,44](verse://Matth%C3%A4us/5/44)");
    expect(out).toContain("[Lukas 6,28](verse://Lukas/6/28)");
  });

  it("keeps a comma range in the display text, canonical start in href", () => {
    expect(linkifyVerses("Siehe Römer 13,1-7 hier.")).toContain(
      "[Römer 13,1-7](verse://R%C3%B6mer/13/1)",
    );
  });

  it("links a numbered book so markdown cannot eat the ordinal as a list marker", () => {
    // "- 1. Petrus 3,9" would otherwise be parsed as a nested ordered list.
    // Wrapping it in [ ] first keeps "1." inside the link, not as a marker.
    const out = linkifyVerses('- 1. Petrus 3,9: "Vergeltet nicht Böses"');
    expect(out).toContain("[1. Petrus 3,9](verse://1.%20Petrus/3/9)");
  });

  it("still links colon references", () => {
    expect(linkifyVerses("See John 3:16.")).toContain(
      "[John 3:16](verse://John/3/16)",
    );
  });

  it("recovers a reference hidden by a greedy connector over-match", () => {
    const out = linkifyVerses("I remind you of Psalm 56:9 today.");
    expect(out).toContain("[Psalm 56:9](verse://Psalm/56/9)");
  });

  it("does not link a decimal amount (not a known book)", () => {
    const md = "Ich habe 3,50 Euro gespart.";
    expect(linkifyVerses(md)).toBe(md);
  });

  it("leaves an existing markdown link untouched", () => {
    const md = "See [John 3:16](https://example.com/john) here.";
    expect(linkifyVerses(md)).toBe(md);
  });

  it("leaves the VERSES html comment untouched", () => {
    const md = "Antwort.\n<!-- VERSES: Römer 12,14; Matthäus 5,44 -->";
    expect(linkifyVerses(md)).toBe(md);
  });

  it("leaves inline code untouched", () => {
    const md = "Schreibe `John 3:16` wörtlich.";
    expect(linkifyVerses(md)).toBe(md);
  });

  it("leaves fenced code untouched", () => {
    const md = "```\nJohn 3:16\n```";
    expect(linkifyVerses(md)).toBe(md);
  });

  it("normalizes Devanagari digits in the href (regression: NaN chapter bug)", () => {
    const out = linkifyVerses("यूहन्ना ५:२४ के अनुसार।");
    expect(out).toContain(
      "[यूहन्ना ५:२४](verse://%E0%A4%AF%E0%A5%82%E0%A4%B9%E0%A4%A8%E0%A5%8D%E0%A4%A8%E0%A4%BE/5/24)",
    );
  });

  it("normalizes Eastern Arabic digits in the href", () => {
    const out = linkifyVerses("يوحنا ٣:١٦");
    expect(out).toContain(
      "[يوحنا ٣:١٦](verse://%D9%8A%D9%88%D8%AD%D9%86%D8%A7/3/16)",
    );
  });
});

describe("linkifyVerses / parseVerseHref — cross-language chapter/verse parity", () => {
  // Per AGENTS.md's multilingual-correctness rule: verify every supported UI
  // language's digit system round-trips to a real number end to end (build the
  // href, then parse it back), not just the two non-ASCII-digit languages this
  // bug was reported in. en/it/de/es/fr/pt/ru/zh/ko all use plain ASCII digits,
  // so they were never at risk — asserting it here makes that explicit instead
  // of assumed.
  const cases: Array<{
    lang: string;
    text: string;
    book: string;
    chapter: number;
    verse: number;
  }> = [
    { lang: "en", text: "John 3:16", book: "John", chapter: 3, verse: 16 },
    {
      lang: "it",
      text: "Giovanni 3:16",
      book: "Giovanni",
      chapter: 3,
      verse: 16,
    },
    {
      lang: "de",
      text: "Johannes 3:16",
      book: "Johannes",
      chapter: 3,
      verse: 16,
    },
    { lang: "es", text: "Juan 3:16", book: "Juan", chapter: 3, verse: 16 },
    { lang: "fr", text: "Jean 3:16", book: "Jean", chapter: 3, verse: 16 },
    { lang: "pt", text: "João 3:16", book: "João", chapter: 3, verse: 16 },
    { lang: "ru", text: "Иоанна 3:16", book: "Иоанна", chapter: 3, verse: 16 },
    {
      lang: "zh",
      text: "约翰福音3:16",
      book: "约翰福音",
      chapter: 3,
      verse: 16,
    },
    {
      lang: "ko",
      text: "요한복음 3:16",
      book: "요한복음",
      chapter: 3,
      verse: 16,
    },
    {
      lang: "hi",
      text: "यूहन्ना ३:१६",
      book: "यूहन्ना",
      chapter: 3,
      verse: 16,
    },
    { lang: "ar", text: "يوحنا ٣:١٦", book: "يوحنا", chapter: 3, verse: 16 },
  ];

  it.each(cases)(
    "$lang: linkifyVerses → parseVerseHref round-trips to numeric chapter/verse",
    ({ text, book, chapter, verse }) => {
      const linked = linkifyVerses(text);
      const hrefMatch = linked.match(/\(verse:\/\/[^)]+\)/);
      expect(hrefMatch).not.toBeNull();
      const href = hrefMatch![0].slice(1, -1);
      const parsed = parseVerseHref(href);
      expect(parsed).toEqual({ book, chapter, verse });
    },
  );
});

describe("parseVerseHref", () => {
  it("parses a verse:// href (with an encoded book)", () => {
    expect(parseVerseHref("verse://R%C3%B6mer/12/14")).toEqual({
      book: "Römer",
      chapter: 12,
      verse: 14,
    });
  });

  it("returns null for external links", () => {
    expect(parseVerseHref("https://example.com")).toBeNull();
    expect(parseVerseHref(undefined)).toBeNull();
  });

  it("normalizes Devanagari digits (regression: NaN chapter bug)", () => {
    expect(
      parseVerseHref(
        "verse://%E0%A4%AF%E0%A5%82%E0%A4%B9%E0%A4%A8%E0%A5%8D%E0%A4%A8%E0%A4%BE/५/२४",
      ),
    ).toEqual({ book: "यूहन्ना", chapter: 5, verse: 24 });
  });

  it("normalizes Eastern Arabic digits", () => {
    expect(parseVerseHref("verse://John/٣/١٦")).toEqual({
      book: "John",
      chapter: 3,
      verse: 16,
    });
  });
});

describe("linkifyVerses — Traditional Chinese (BITB-025)", () => {
  it("links a Traditional-script reference and keeps the Traditional display text", () => {
    const out = linkifyVerses("約翰福音 3:16");
    // Display text is the ORIGINAL Traditional characters, byte-identical —
    // matching must not silently rewrite what the user wrote to Simplified.
    expect(out).toContain("[約翰福音 3:16](verse://");
    expect(out).not.toContain("约翰福音 3:16"); // Simplified must never appear in display text
    const href = out.match(/\(verse:\/\/([^)]+)\)/)?.[1];
    expect(parseVerseHref(`verse://${href}`)).toEqual({
      book: "约翰福音", // href carries the Simplified form for lookup
      chapter: 3,
      verse: 16,
    });
  });

  it("encodes the Simplified book name in the href even though display stays Traditional", () => {
    const out = linkifyVerses("馬太福音 5:3");
    expect(out).toContain("[馬太福音 5:3](verse://");
    const href = out.match(/\(verse:\/\/([^)]+)\)/)?.[1];
    expect(href).toBeDefined();
    const parsed = parseVerseHref(`verse://${href}`);
    expect(parsed?.book).toBe("马太福音");
  });

  it("handles mixed-script text (Traditional 創 + Simplified 世记)", () => {
    const out = linkifyVerses("創世记 1:1");
    expect(out).toContain("[創世记 1:1](verse://");
    const href = out.match(/\(verse:\/\/([^)]+)\)/)?.[1];
    expect(parseVerseHref(`verse://${href}`)?.book).toBe("创世记");
  });

  it("does not alter a pure-English input", () => {
    const text = "See John 3:16 for context.";
    expect(linkifyVerses(text)).toBe(
      "See [John 3:16](verse://John/3/16) for context.",
    );
  });

  it("links multiple Traditional references in the same segment, each keeping its own display text", () => {
    const out = linkifyVerses("約翰福音 3:16 and 羅馬書 8:28");
    expect(out).toContain("[約翰福音 3:16](verse://");
    expect(out).toContain("[羅馬書 8:28](verse://");
    const hrefs = [...out.matchAll(/\(verse:\/\/([^)]+)\)/g)].map(
      (m) => parseVerseHref(`verse://${m[1]}`)?.book,
    );
    expect(hrefs).toEqual(["约翰福音", "罗马书"]);
  });
});
