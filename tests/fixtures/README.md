# tests/fixtures/

## `verse_reference_corpus.json`

Shared cross-platform regression corpus for BITB-059
(`docs/BACKLOG_STORIES/BITB-059-unify-verse-parser-single-source-of-truth.md`), acceptance
criterion #4:

> A shared cross-platform test corpus (citation string → expected book/chapter/verse, including
> the #799/#801/#804 regression cases and non-Latin numerals) runs against all three
> implementations in their respective CI jobs.

Vox Quieta hand-maintains three independent verse-reference parsers — Python
(`api/utils/verse_parser.py`), TypeScript (`frontend/src/lib/versePatterns.ts` +
`verseExtraction.ts`), and Kotlin (`android/.../ChatMessageItem.kt` +
`LocalizedBookToEnglish.kt`). They have drifted apart before (PRs #799, #801, #804, #893, #903),
each time as a hand-discovered, hand-repaired bug. This corpus gives all three platforms one
shared, versioned set of inputs and expected outputs so a future regression in *any* parser is
caught by *that platform's own CI job*, without needing a human to notice the drift first.

This file is consumed by:

- `api/tests/test_verse_parser_corpus.py` (pytest)
- `frontend/src/lib/verseCorpus.crossplatform.test.ts` (vitest)
- `android/app/src/test/kotlin/org/voxquieta/app/components/VerseCorpusParityTest.kt` (JUnit)

This PR is test-only: it does not change any parsing behavior. It is scoped to AC #4 alone; the
full single-source-of-truth generator (AC #1–#3, #5) is a separate, larger follow-up.

### Schema

```jsonc
{
  "description": "…",
  "test_cases": [
    {
      "id": "unique_snake_case_id",
      "input": "the raw text to parse",
      "language": "en", // BCP-47-ish language tag, informational only
      "expected": {
        "book": "john",            // lowercase, English canonical (e.g. "1 corinthians", "song of solomon")
        "chapter": 3,
        "verseStart": 16,
        "verseEnd": null           // int, or null when the reference is not a range
      },
      "origin": "free-text provenance — which PR/incident/behavior this case guards",
      "skip": [],                  // subset of ["python", "web", "android"] — platforms that must skip this case
      "skipReason": ""             // required (non-empty) whenever "skip" is non-empty
    }
  ]
}
```

Negative-control cases (text that must NOT resolve to a verse reference — e.g. a decimal amount
or a clock time) use `"expectNone": true` and `"expected": null` instead of an `expected` object.

### Why `book` is lowercase-English-canonical

All three parsers ultimately resolve a localized book name (Italian "Giovanni", German
"Matthäus", Chinese "约翰福音", …) to the same English canonical name so that verse lookups hit
the same database rows regardless of the language the reference was written in. Comparing against
that shared English form — rather than the raw localized token — is what lets one JSON file
express expectations that are valid across all three parsers and all supported languages at once.
Lowercase is used because the web parser (`extractVerseReferences`) normalizes to lowercase by
construction (its `Set<string>` entries are always lowercase), so lowercase is the least common
denominator all three can be compared against.

### Why only Python asserts `verseEnd`

- **Python** (`parse_verse_reference` → `VerseReference`) has an explicit `verse_end: int | None`
  field, so a range like "Romans 8:28-30" can be asserted precisely (`verse_start=28,
  verse_end=30`).
- **Web** (`extractVerseReferences`) returns a `Set<string>` of `"book chapter:verse"` strings
  with no range information at all — a range collapses to just its start verse (e.g. "Romans
  8:28-30" → the set contains `"romans 8:28"`, never `"...28-30"` or `"...30"`). There is nothing
  to assert `verseEnd` against.
- **Android** (`parseVerseLink` → `PendingVerseLink`) has no range field either; `verseNumber` is
  a single `Int` (the *display* text keeps the written range, e.g. `[Romans 8:38-39]`, but the
  parsed link data does not carry an end verse).

So the corpus's `verseEnd` field exists for the Python test only; the web and Android tests
compare book/chapter/verseStart (web) or book/chapter/verseNumber (Android) and ignore
`verseEnd` entirely — this is expected, not an omission.

### `skip` / `skipReason` convention

A case is skipped on a platform when that platform has a **known, tracked** behavioral gap for
it — not when a test is merely inconvenient to write. Every non-empty `skip` entry must be paired
with a non-empty `skipReason` explaining *why* (ideally referencing a backlog story or PR), so a
skip never silently rots into "nobody remembers why this is disabled." The one skip currently in
the corpus (`known_divergence_android_russian_lamentations`, skipped for `"android"`) is a real,
deliberate gap: Android's regex resolves a two-word Russian book name differently from Python and
web. It is captured here on purpose so the follow-up unification work (BITB-059 AC #1–#3) has a
concrete regression case to close, rather than being fixed ad hoc in this test-only PR.
