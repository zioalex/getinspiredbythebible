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
      parseVerseHref("verse://%E0%A4%AF%E0%A5%82%E0%A4%B9%E0%A4%A8%E0%A5%8D%E0%A4%A8%E0%A4%BE/५/२४"),
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
