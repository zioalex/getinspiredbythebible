import { describe, it, expect } from "vitest";
import { createVersePattern, createVersePatternGlobal } from "./versePatterns";

// ── ReDoS regression (BITB-108 / audit item E13) ───────────────────────────
//
// The multi-word book-name "connector" branch
// ([\p{L}\p{M}]{2,}(?:\s+(?:of|dei|des|...)\s+[\p{L}\p{M}]+){1,3}) used to have
// an unbounded `+` on the connector-repeat group. That let adversarial input
// (repeated " of aa" segments) drive the regex engine's backtracking into
// superlinear blowup — ~22s on a 300KB adversarial string, benchmarked via
// the actual compiled pattern from createVersePatternGlobal(). Bounding the
// group to {1,3} closes this without affecting real book names (verified:
// zero entries in localizedBookMap.generated.ts use more than one connector
// repeat). See docs/BACKLOG_STORIES/BITB-108-verse-parser-phase-3-regex-grammar.md
// for the full writeup.
//
// This test is a permanent regression guard: if the bound is ever widened
// back to `+` (or removed), this test should start timing out / blowing the
// budget below.

describe("versePatterns ReDoS regression", () => {
  it(
    "matches an adversarial 'of'-chain string within a time budget",
    { timeout: 5000 },
    () => {
      // ~120,000 chars — large enough to clearly separate O(n) from
      // O(n^2)/superlinear behaviour, but still fast to run under the fix.
      const n = 20000;
      const input = "aa" + " of aa".repeat(n) + "!";

      const pattern = createVersePatternGlobal();
      const start = performance.now();
      // Consumed the same way verseExtraction.ts / linkifyVerses.ts consume
      // the pattern: iterate all matches via matchAll().
      const matches = Array.from(input.matchAll(pattern));
      const elapsed = performance.now() - start;

      // Not asserting on match *content* — this is adversarial nonsense text,
      // not meant to represent a real verse reference. Only timing matters
      // here: with the bounded connector group this completes in low tens of
      // ms; with the old unbounded `+` it took ~22s on a 300KB input, so a
      // generous 500ms budget still clearly catches a regression.
      expect(elapsed).toBeLessThan(500);
      // matches.length is intentionally not asserted: this input has no
      // trailing chapter:verse digits, so it never matches at all (0 results)
      // — that's expected and irrelevant here. Only the timing matters; see
      // the "connector-repeat cap is enforced" suite below for assertions on
      // what the connector branch actually captures.
      void matches;
    },
  );
});

// ── Connector-repeat cap is actually enforced ──────────────────────────────
//
// The two suites above don't, on their own, prove the {1,3} bound is what's
// doing the work: every "legitimate" example above resolves via the
// multi-word book-name alternation (getMultiWordAlternation()), which is
// tried before the connector branch and matches regardless of the bound —
// deleting the connector branch entirely still passes those. This suite
// exercises the connector branch directly with synthetic (non-book) chained
// phrases, so it fails if the bound is ever widened back to `+`.
//
// Empirically confirmed while writing this test: on the pre-fix (unbounded
// `+`) pattern, a 4-connector chain like "Xylo of Zorp of Quix of Wobble of
// Nix 3:16" captures the full 5-word phrase as the book name. On the fixed
// ({1,3}) pattern, the same input can't start its match at "Xylo" (that
// would need a 4th connector repeat), so the regex engine instead starts the
// match one word later, capturing "Zorp of Quix of Wobble of Nix" (still
// within the {1,3} cap) — silently dropping "Xylo of" rather than including
// it. That shift in *where the match starts* is the bound in action.

describe("connector-repeat cap ({1,3}) is enforced, not just documented", () => {
  it("matches 1-3 chained connector words as a single book capture", () => {
    const re = createVersePattern();
    expect(re.exec("Xylo of Zorp 3:16")?.[1]).toBe("Xylo of Zorp");
    expect(re.exec("Xylo of Zorp of Quix 3:16")?.[1]).toBe("Xylo of Zorp of Quix");
    expect(re.exec("Xylo of Zorp of Quix of Wobble 3:16")?.[1]).toBe(
      "Xylo of Zorp of Quix of Wobble",
    );
  });

  it("refuses a 4th connector repeat from the same start, instead of matching it unbounded", () => {
    const re = createVersePattern();
    const match = re.exec("Xylo of Zorp of Quix of Wobble of Nix 3:16");
    // Not null, not undefined — some later branch/start-position still finds
    // a valid (shorter) reference in this string.
    expect(match).not.toBeNull();
    // The captured book name must NOT be the full 5-word chain: that would
    // only be possible with an unbounded connector-repeat group.
    expect(match?.[1]).not.toBe("Xylo of Zorp of Quix of Wobble of Nix");
    // What it actually captures instead: the match starts one word later,
    // using exactly 3 connector repeats (the cap) from "Zorp" instead of 4
    // from "Xylo".
    expect(match?.[1]).toBe("Zorp of Quix of Wobble of Nix");
  });
});

// ── Legitimate multi-connector-locale regression ───────────────────────────
//
// Confirms the {1,3} bound (down from unbounded +) does not break any real
// multi-word book name that uses a connector word. One real example is
// picked per connector where localizedBookMap.generated.ts actually contains
// one; a connector is skipped (and noted) when no real book name using it
// exists in the generated map.
//
// Coverage found in localizedBookMap.generated.ts:
//   of  -> "song of solomon" (en)
//   dei -> "cantico dei cantici" (it)
//   des -> "cantique des cantiques" (fr) / "actes des apôtres" (fr)
//   dos -> "cântico dos cânticos" (pt)
//   के  -> "प्रेरितों के काम" (hi)
// No real book name in the generated map uses "der", "van", "de", "af",
// "da", "del", or "ال" as a connector (they exist only as substrings of
// single-word names, e.g. German "der" is not a connector word in any
// multi-word book form) — so those connectors are skipped here rather than
// tested against invented book names.

describe("legitimate multi-connector book names still match after {1,3} bound", () => {
  const cases: Array<[string, string, string]> = [
    ["of", "Song of Solomon 1:1", "song of solomon"],
    ["dei", "Cantico dei Cantici 1:1", "cantico dei cantici"],
    ["des", "Cantique des Cantiques 1:1", "cantique des cantiques"],
    ["des (Acts)", "Actes des Apôtres 1:1", "actes des apôtres"],
    ["dos", "Cântico dos Cânticos 1:1", "cântico dos cânticos"],
    ["के", "प्रेरितों के काम 1:1", "प्रेरितों के काम"],
  ];

  it.each(cases)(
    "matches a real book name using connector %s",
    (_connector, text, expectedBookLower) => {
      const re = createVersePattern();
      expect(re.test(text)).toBe(true);

      const global = createVersePatternGlobal();
      const matches = Array.from(text.matchAll(global));
      expect(matches.length).toBe(1);
      expect(matches[0][1].toLowerCase()).toBe(expectedBookLower);
    },
  );
});
