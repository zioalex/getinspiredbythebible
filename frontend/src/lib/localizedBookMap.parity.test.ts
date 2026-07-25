/**
 * BITB-059 Phase 1 — locks the hand-written web book-name map to the canonical JSON.
 *
 * tests/fixtures/localized_book_map.json is the single source of truth for the localized
 * book-name -> canonical English book-name map (BITB-059). The Android map is generated
 * from it (scripts/generate_localized_book_map.py); the web map stays hand-written for now
 * (Phase 2 will generate it too — see the BITB-059 story's Scope Note) but this test fails
 * CI the moment the two diverge, so an edit to one without the other can't ship silently.
 *
 * Read via Node fs/path rather than a TS/JSON import, matching verseCorpus.crossplatform.test.ts:
 * the fixture lives outside frontend/ (at the repo root) and is shared with the other platforms.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { LOCALIZED_BOOK_TO_ENGLISH } from "./verseExtraction";

interface LocalizedBookMapFixture {
  description: string;
  book_map: Record<string, string>;
}

// frontend/src/lib/ -> repo root is three levels up: lib -> src -> frontend -> repo root.
const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = resolve(
  __dirname,
  "../../../tests/fixtures/localized_book_map.json",
);

const fixture: LocalizedBookMapFixture = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
);

describe("localized book-name map parity (web vs. canonical JSON)", () => {
  it("has the same entries as tests/fixtures/localized_book_map.json", () => {
    expect(LOCALIZED_BOOK_TO_ENGLISH).toEqual(fixture.book_map);
  });
});
