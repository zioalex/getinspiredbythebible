/**
 * BITB-059 AC#4 — shared cross-platform verse-reference regression corpus (web side).
 *
 * Loads tests/fixtures/verse_reference_corpus.json (shared with the Python and Android test
 * suites — see tests/fixtures/README.md) and asserts that extractVerseReferences() produces the
 * expected "book chapter:verseStart" entry for every non-skipped case.
 *
 * The corpus is read via Node fs/path (not a TS/JSON import) to avoid coupling this test to the
 * bundler's JSON-import resolution — the file lives outside frontend/ (at the repo root) and is
 * shared verbatim with the other two platforms.
 *
 * This is a test-only regression net: it does not change verseExtraction.ts / versePatterns.ts.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { extractVerseReferences } from "./verseExtraction";

interface CorpusExpected {
  book: string;
  chapter: number;
  verseStart: number;
  verseEnd: number | null;
}

interface CorpusCase {
  id: string;
  input: string;
  language: string;
  expected: CorpusExpected | null;
  expectNone?: boolean;
  origin: string;
  skip: string[];
  skipReason: string;
}

interface Corpus {
  description: string;
  test_cases: CorpusCase[];
}

// frontend/src/lib/ -> repo root is four levels up: lib -> src -> frontend -> repo root.
const __dirname = dirname(fileURLToPath(import.meta.url));
const CORPUS_PATH = resolve(
  __dirname,
  "../../../tests/fixtures/verse_reference_corpus.json",
);

const corpus: Corpus = JSON.parse(readFileSync(CORPUS_PATH, "utf-8"));

describe("verse reference corpus (cross-platform, web)", () => {
  for (const testCase of corpus.test_cases) {
    const testFn = testCase.skip.includes("web") ? it.skip : it;

    testFn(`${testCase.id}: ${JSON.stringify(testCase.input)}`, () => {
      const refs = extractVerseReferences(testCase.input);

      if (testCase.expectNone) {
        expect(refs.size).toBe(0);
        return;
      }

      const expected = testCase.expected as CorpusExpected;
      const expectedRef = `${expected.book} ${expected.chapter}:${expected.verseStart}`;
      expect(Array.from(refs)).toContain(expectedRef);
    });
  }
});
