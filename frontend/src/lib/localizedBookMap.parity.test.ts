/**
 * BITB-059 Phase 2 — guards the generated web book-name map against silent drift from its
 * canonical source.
 *
 * tests/fixtures/localized_book_map.json is the single source of truth for the localized
 * book-name -> canonical English book-name map (BITB-059). localizedBookMap.generated.ts is
 * generated from it by scripts/generate_localized_book_map.py, the same way the Android map
 * is. The byte-exact guard lives in that script's `--check` mode (wired into CI); this test
 * is the vitest-visible companion — order-independent, so it reports the actual offending
 * keys rather than a raw diff — mirroring the assertions LocalizedBookToEnglishTest.kt makes
 * on the Android side.
 *
 * Read via Node fs/path rather than a TS/JSON import, matching verseCorpus.crossplatform.test.ts:
 * the fixture lives outside frontend/ (at the repo root) and is shared with the other platforms.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { LOCALIZED_BOOK_TO_ENGLISH } from "./localizedBookMap.generated";

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

  it("maps to exactly the 66 canonical English books", () => {
    expect(new Set(Object.values(LOCALIZED_BOOK_TO_ENGLISH)).size).toBe(66);
  });

  it("has all keys and values lowercased", () => {
    for (const [key, value] of Object.entries(LOCALIZED_BOOK_TO_ENGLISH)) {
      expect(key).toBe(key.toLowerCase());
      expect(value).toBe(value.toLowerCase());
    }
  });

  it("resolves the key English aliases used by the reported bug", () => {
    expect(LOCALIZED_BOOK_TO_ENGLISH["psalm"]).toBe("psalms");
    expect(LOCALIZED_BOOK_TO_ENGLISH["salmos"]).toBe("psalms");
    expect(LOCALIZED_BOOK_TO_ENGLISH["isaías"]).toBe("isaiah");
    expect(LOCALIZED_BOOK_TO_ENGLISH["song of solomon"]).toBe(
      "song of solomon",
    );
  });
});
