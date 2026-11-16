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

  // Shared table: identical on backend, web and Android.
  it.each<[string, string, string]>([
    ["plain text", "Plain text.", "Plain text."],
    ["complete verses", "Peace.\n<!-- VERSES: John 14:27 -->", "Peace."],
    [
      "both complete",
      "Peace.\n<!-- VERSES: John 14:27 -->\n<!-- FOLLOWUPS: a|b|c -->",
      "Peace.",
    ],
    [
      "unterminated followups",
      "Peace.\n<!-- FOLLOWUPS: What does this me",
      "Peace.",
    ],
    ["partial marker word", "Peace. <!-- FOLLOW", "Peace."],
    ["bare opener", "Peace.\n<!--", "Peace."],
    ["opener then unrelated text", "Peace. <!-- note that", "Peace."],
    ["dangling <!-", "Peace. <!-", "Peace."],
    ["dangling <!", "Peace. <!", "Peace."],
    ["dangling <", "Peace. <", "Peace."],
    [
      "closed unrelated comment kept",
      "A <!-- note --> B.",
      "A <!-- note --> B.",
    ],
    [
      "cjk",
      "神爱世人（约翰福音3:16）。\n<!-- VERSES: John 3:16 -->",
      "神爱世人（约翰福音3:16）。",
    ],
    ["cjk cut", "神爱世人。<!-- FOLLOW", "神爱世人。"],
    [
      "arabic",
      "الرب راعيّ. <!-- FOLLOWUPS: ماذا تعني؟|لماذا؟ -->",
      "الرب راعيّ.",
    ],
    ["arabic cut", "الرب راعيّ. <!-", "الرب راعيّ."],
  ])("shared rule table: %s", (_name, input, expected) => {
    expect(stripTrailer(input)).toBe(expected);
  });
});
