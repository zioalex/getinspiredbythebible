import { describe, it, expect } from "vitest";
import { extractVerseReferences, isKnownBook } from "./verseExtraction";

/**
 * Cross-language regression tests for the inline verse-marking fix.
 *
 * Two guarantees are verified for every supported locale
 * (en, it, de, es, fr, pt, ar, ru, zh, hi, ko):
 *
 *   1. A real verse reference in that language is recognised
 *      (isKnownBook + extractVerseReferences).
 *   2. Prose / clock times / scores / conjunctions that merely contain a
 *      "word digit:digit" shape are NOT treated as verses — this is what
 *      previously caused text to be swallowed into clickable spans.
 */

// One representative "John 3:16" per supported language → normalizes to "john 3:16".
const JOHN_3_16: Array<{ locale: string; book: string; text: string }> = [
  { locale: "en", book: "John", text: "John 3:16" },
  { locale: "it", book: "Giovanni", text: "Giovanni 3:16" },
  { locale: "de", book: "Johannes", text: "Johannes 3:16" },
  { locale: "es", book: "Juan", text: "Juan 3:16" },
  { locale: "fr", book: "Jean", text: "Jean 3:16" },
  { locale: "pt", book: "João", text: "João 3:16" },
  { locale: "ar", book: "يوحنا", text: "يوحنا 3:16" },
  { locale: "hi", book: "यूहन्ना", text: "यूहन्ना 3:16" },
  { locale: "ru", book: "Иоанна", text: "Иоанна 3:16" },
  { locale: "zh", book: "约翰福音", text: "约翰福音 3:16" },
  { locale: "zh", book: "約翰福音", text: "約翰福音 3:16" }, // Traditional-script input (BITB-025)
  { locale: "ko", book: "요한복음", text: "요한복음 3:16" },
];

describe("isKnownBook — accepts real books in every language", () => {
  for (const { locale, book } of JOHN_3_16) {
    it(`accepts ${locale} book name "${book}"`, () => {
      expect(isKnownBook(book)).toBe(true);
    });
  }

  it("accepts English canonical names (stored as map values, not keys)", () => {
    for (const b of [
      "Genesis",
      "Job",
      "Psalms",
      "Matthew",
      "Romans",
      "1 Samuel",
      "Song of Solomon",
      "Revelation",
      "Acts",
      "Jude",
    ]) {
      expect(isKnownBook(b)).toBe(true);
    }
  });

  it("accepts numbered / multi-word localized books", () => {
    expect(isKnownBook("1. Mose")).toBe(true); // German Genesis
    expect(isKnownBook("Hiob")).toBe(true); // German Job
    expect(isKnownBook("Psalm")).toBe(true); // German/English alias
    expect(isKnownBook("Cantico dei Cantici")).toBe(true); // Italian Song of Solomon
  });

  it("is case- and whitespace-insensitive", () => {
    expect(isKnownBook("  hIoB  ")).toBe(true);
    expect(isKnownBook("JOHANNES")).toBe(true);
  });
});

describe("isKnownBook — rejects non-books (the false positives that cut text)", () => {
  const NON_BOOKS = [
    "Trost der Hoffnung", // German prose ("der" connector)
    "treu", // ordinary German word
    "um", // German "at" (clock times: "um 14:30")
    "Ergebnis", // "score" prose
    "vers",
    "kapitel",
    "und", // German conjunction
    "and",
    "e", // Italian conjunction
    "et", // French conjunction
    "y", // Spanish conjunction
    "Trost der Hoffnung", // greedy multi-word over-match
    "1. Mose lesen wir dass Gott alles", // greedy numbered over-match
  ];
  for (const word of NON_BOOKS) {
    it(`rejects "${word}"`, () => {
      expect(isKnownBook(word)).toBe(false);
    });
  }
});

describe("extractVerseReferences — real references in every language", () => {
  for (const { locale, text } of JOHN_3_16) {
    it(`extracts "${text}" (${locale}) → john 3:16`, () => {
      const refs = extractVerseReferences(text);
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.size).toBe(1);
    });
  }

  it("extracts a real reference embedded in a localized sentence", () => {
    // German, Italian, Spanish, French, Portuguese sentences.
    expect(
      extractVerseReferences("Wie es in Johannes 3:16 heißt, ...").has(
        "john 3:16",
      ),
    ).toBe(true);
    expect(
      extractVerseReferences("Come dice Giovanni 3:16, ...").has("john 3:16"),
    ).toBe(true);
    expect(
      extractVerseReferences("Como dice Juan 3:16, ...").has("john 3:16"),
    ).toBe(true);
    expect(
      extractVerseReferences("Comme le dit Jean 3:16, ...").has("john 3:16"),
    ).toBe(true);
    expect(
      extractVerseReferences("Como diz João 3:16, ...").has("john 3:16"),
    ).toBe(true);
  });
});

describe("extractVerseReferences — German screenshot scenario", () => {
  it("marks Hiob 7:3 and Psalm 70:3 but nothing else", () => {
    const text =
      'Wie es in Hiob 7:3 heißt, wurden ihm "Monate der Enttäuschung" zuteil. ' +
      "In Psalm 70:3 steht, dass diejenigen, die uns nach dem Leben trachten, " +
      "beschämt und zuschanden werden.";
    const refs = extractVerseReferences(text);
    expect(refs.has("job 7:3")).toBe(true);
    expect(refs.has("psalms 70:3")).toBe(true);
    expect(refs.size).toBe(2);
  });
});

describe("extractVerseReferences — rejects non-verse 'word digit:digit'", () => {
  const NON_VERSES = [
    "Gott schenkt uns Trost der Hoffnung 5:5 jeden Tag.", // connector over-match
    "Wir treffen uns um 14:30 Uhr.", // clock time
    "Das Spiel endete 2:1 für uns.", // score
    "Gott ist treu 3:4 immer.", // arbitrary word + numbers
    "In 1. Mose lesen wir dass Gott alles 1:1 erschuf.", // greedy numbered over-match
    "Il rapporto è 3:2 e 51:17 punti.", // conjunctions + ratios
  ];
  for (const text of NON_VERSES) {
    it(`extracts nothing from: "${text}"`, () => {
      expect(extractVerseReferences(text).size).toBe(0);
    });
  }
});
