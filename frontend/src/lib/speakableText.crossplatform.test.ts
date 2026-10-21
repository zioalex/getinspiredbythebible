/**
 * BITB-119 — shared cross-platform speakable-text fixture (web side).
 *
 * Loads tests/fixtures/speakable_text.json (shared with the Android JUnit suite — see
 * tests/fixtures/README.md) and asserts that normalizeForSpeech / chunkForSpeech produce
 * the expected strings, and that the in-code verse template table equals the fixture's.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  VERSE_SPEECH_TEMPLATES,
  chunkForSpeech,
  normalizeForSpeech,
  speakableChunks,
} from "./speakableText";

interface NormalizeCase {
  id: string;
  language: string;
  input: string;
  expected: string;
  origin: string;
  skip: string[];
  skipReason: string;
}
interface ChunkCase {
  id: string;
  language: string;
  input: string;
  expected: string[];
}
interface Fixture {
  maxChunkChars: number;
  verseTemplates: Record<string, { verse: string; range: string }>;
  normalize_cases: NormalizeCase[];
  chunk_cases: ChunkCase[];
}

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixture: Fixture = JSON.parse(
  readFileSync(
    resolve(__dirname, "../../../tests/fixtures/speakable_text.json"),
    "utf-8",
  ),
);

const LANGUAGES = [
  "en",
  "it",
  "de",
  "es",
  "fr",
  "pt",
  "ar",
  "ru",
  "zh",
  "hi",
  "ko",
];

describe("speakable_text.json fixture shape", () => {
  it("covers all 11 languages with verse + range templates", () => {
    expect(Object.keys(fixture.verseTemplates).sort()).toEqual(
      [...LANGUAGES].sort(),
    );
  });

  it("has at least one single-verse and one range normalize case per language", () => {
    for (const lang of LANGUAGES) {
      const cases = fixture.normalize_cases.filter((c) => c.language === lang);
      expect(
        cases.some((c) => c.id === `verse_${lang}`),
        lang,
      ).toBe(true);
      expect(
        cases.some((c) => c.id === `range_${lang}`),
        lang,
      ).toBe(true);
    }
  });

  it("requires a skipReason whenever a case is skipped", () => {
    for (const c of fixture.normalize_cases) {
      if (c.skip.length > 0) expect(c.skipReason.length).toBeGreaterThan(0);
    }
  });
});

describe("verse template parity", () => {
  it("web template table equals the fixture's", () => {
    expect(VERSE_SPEECH_TEMPLATES).toEqual(fixture.verseTemplates);
  });
});

describe("normalizeForSpeech (shared fixture)", () => {
  it.each(fixture.normalize_cases.filter((c) => !c.skip.includes("web")))(
    "$id ($language)",
    (c) => {
      expect(normalizeForSpeech(c.input, c.language)).toBe(c.expected);
    },
  );

  it("falls back to English templates for an unknown locale", () => {
    expect(normalizeForSpeech("John 3:16", "xx")).toBe(
      "John chapter 3, verse 16",
    );
  });

  it("accepts regional locale tags (zh-CN, pt_BR)", () => {
    expect(normalizeForSpeech("约翰福音 3:16", "zh-CN")).toBe(
      "约翰福音第3章第16节",
    );
    expect(normalizeForSpeech("João 3:16", "pt_BR")).toBe(
      "João capítulo 3, versículo 16",
    );
  });
});

describe("chunkForSpeech (shared fixture)", () => {
  it("uses the fixture's chunk limit", () => {
    expect(fixture.maxChunkChars).toBe(200);
  });

  it.each(fixture.chunk_cases)("$id ($language)", (c) => {
    const chunks = chunkForSpeech(c.input, fixture.maxChunkChars);
    expect(chunks).toEqual(c.expected);
    for (const chunk of chunks) {
      expect(chunk.length).toBeLessThanOrEqual(fixture.maxChunkChars);
    }
  });

  it("never splits a surrogate pair", () => {
    const chunks = chunkForSpeech("x".repeat(199) + "😊😊😊", 200);
    for (const chunk of chunks) {
      expect(chunk).not.toMatch(/[\ud800-\udbff]$/);
      expect(chunk).not.toMatch(/^[\udc00-\udfff]/);
    }
    expect(chunks.join("")).toBe("x".repeat(199) + "😊😊😊");
  });
});

describe("speakableChunks", () => {
  it("normalizes then chunks", () => {
    expect(speakableChunks("**Read** John 3:16.", "en")).toEqual([
      "Read John chapter 3, verse 16.",
    ]);
  });

  it("returns no chunks for markup-only input", () => {
    expect(speakableChunks("---\n\n```\n", "en")).toEqual([]);
  });
});
