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
skip never silently rots into "nobody remembers why this is disabled." Two skips are currently in
the corpus:

- `known_divergence_android_russian_lamentations` (skipped for `"android"`) is a real, deliberate
  gap: Android's regex resolves a two-word Russian book name differently from Python and web. It
  is captured here on purpose so the follow-up unification work (BITB-059 AC #1–#3) has a concrete
  regression case to close, rather than being fixed ad hoc in this test-only PR.
- The eight `zh_hant_*` / `zh_mixed_script_*` cases (skipped for `"android"`) are BITB-025
  (Traditional-to-Simplified Chinese normalization for verse parsing): shipped for Python and web
  only in the PR that added them, with the Android T2S table + `injectVerseLinks` shadow-string
  surgery as an explicit fast-follow — see
  `docs/BACKLOG_STORIES/BITB-025-traditional-chinese-t2s-normalization.md`.

## `localized_book_map.json`

The single source of truth for the localized-book-name → canonical-English-book-name map used by
the client apps (BITB-059). `scripts/generate_localized_book_map.py` generates:

- `android/app/src/main/kotlin/org/voxquieta/app/utils/LocalizedBookToEnglish.kt`
- `frontend/src/lib/localizedBookMap.generated.ts`

from this file. **Never hand-edit either generated file** — edit the JSON, run the generator, and
commit all three files together:

```sh
python scripts/generate_localized_book_map.py
```

CI enforces this with `python scripts/generate_localized_book_map.py --check` (the
"book-name maps stay generated" step in `.github/workflows/test_update.yml`, `backend-tests`
job) — it fails if either generated file is hand-edited, or if the JSON changed without
regenerating.

Verified against this JSON:

- `android/app/src/test/kotlin/org/voxquieta/app/utils/LocalizedBookToEnglishTest.kt`
- `frontend/src/lib/localizedBookMap.parity.test.ts`
- `api/tests/test_localized_book_map_registry_parity.py` (verifies against
  `api/utils/translation_registry.py` — see below, this one holds a *separate* master
  contradiction-free rather than generating from/into it)

Because `--check` is byte-exact, it also depends on the JSON's key **order** — if the JSON is
ever reordered (e.g. an editor "cleans up" the key order), regenerate and commit all three files
in the same commit, or `--check` will report a spurious diff on the next CI run even though the
content is unchanged.

Three semantic notes from the Korean section of the map that generation drops (key order still
preserves the original language grouping, but per-entry comments do not survive code
generation):

- `계시록` → `revelation` — short for `요한계시록`
- `애가` → `lamentations` — short for `예레미야 애가`
- `행전` → `acts` — short for `사도행전`

## `localized_book_map_registry_gaps.json`

`localized_book_map.json` (the client-bundle map, above) and `api/utils/translation_registry.py`
(the backend's per-translation-code, case-preserving master) are two **independent masters** —
neither generates the other, because the registry carries data (which translation code an alias
belongs to, cased canonical forms) the flat lowercase JSON structurally cannot represent. Instead,
`api/tests/test_localized_book_map_registry_parity.py` holds them **contradiction-free**: any key
shared between the two must resolve to the same English book, and any key present on only one side
must be listed here with a reviewed reason. A new one-sided key (e.g. a citation-form alias added
to one side and not the other) fails that test until it is either propagated to the other side or
added here — so a gap can't ship silently, and the allowlist can't rot once a gap is closed
elsewhere (a stale entry also fails the test).
