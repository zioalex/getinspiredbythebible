import { describe, it, expect } from "vitest";
import { stripTrailer } from "./streamRecovery";

describe("stripTrailer (BITB-320)", () => {
  it.each([
    [
      "en",
      'Body text.\n<!-- VERSES: ["John 3:16"] -->\n<!-- FOLLOWUPS: ["Why?"] -->',
    ],
    ["zh", '正文。\n<!-- VERSES: ["约翰福音 3:16"] -->'],
    ["ar", 'نص.\n<!-- FOLLOWUPS: ["لماذا؟"] -->'],
  ])("removes complete trailers (%s)", (_l, text) => {
    const out = stripTrailer(text);
    expect(out).not.toContain("<!--");
    expect(out.length).toBeGreaterThan(0);
  });

  it("removes an unterminated trailer cut off by the connection", () => {
    expect(stripTrailer('Text.\n<!-- FOLLOWUPS: ["Wh')).toBe("Text.");
  });

  it("leaves text without a trailer untouched", () => {
    expect(stripTrailer("Plain text.")).toBe("Plain text.");
  });
});
