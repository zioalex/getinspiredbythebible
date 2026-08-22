# BITB-025: Traditional→Simplified Chinese Conversion Layer for Verse Parsing

**Status:** 🚧 In Progress — Backend + web shipped; Android is an explicit fast-follow
**Priority:** P3
**Size:** M (1-2 days)
**Created:** 2026-04-03

**Note (ID collision):** this ID number is also used by the unrelated, already-Done
`docs/BACKLOG_STORIES/BITB-025-verse-linking-android.md`. Kept as a separate file rather than
overwriting it; worth a renumbering pass at some point, out of scope here.

## User Story

As a Chinese-speaking user writing in Traditional script, I want verse references like
`約翰福音 3:16` or `馬太福音 5:3` to be detected and linked, so that I get verse lookups
regardless of whether an LLM (or I) produce Simplified or Traditional characters.

## Problem

`translation_registry.py`'s `ENGLISH_TO_CHINESE` map and its `CHINESE_ALIASES` (added by
PR #389 for 记↔纪 swaps and Catholic 思高本 names) store Simplified-script book names almost
exclusively. A book name written in Traditional script — 66 books × 2 scripts, plus mixed-script
input where only some characters are Traditional — had no path to resolve at all before this
story, on any of the three platforms.

## Approach

A single Traditional→Simplified (T2S) normalization function, applied to a *copy* of the input
text immediately before verse-reference matching runs. Deliberately **not** a general-purpose
converter (no `opencc-python-reimplemented`/`hanziconv` on the backend, no `chinese-conv` on the
frontend, no ICU `Transliterator` on Android — all three were the story's original proposal):
those all do phrase-level conversion and are not guaranteed length-preserving. This repo's parsers
depend on length-preservation:

- `api/utils/verse_parser.py`'s `extract_reference_mentions` and `_find_adjacent_reference` return
  **offsets** into the original text (used by the unquoted-paraphrase grounding path and inline
  quote detection). A conversion that changes string length would shift those offsets out from
  under the original.
- `frontend/src/lib/linkifyVerses.ts`'s `linkifyPlainSegment` and
  `frontend/src/components/ChatMessage.tsx`'s `highlightText` must display the reference **exactly
  as the user wrote it** (Traditional characters on screen), while still resolving it to the
  Simplified form the lookup tables use internally. This only works cleanly with a 1:1
  substitution: match against a normalized shadow copy, but slice the *original* string for
  display.

So the implementation is a single hand-derived character table — 29 entries — shared across
platforms via `tests/fixtures/t2s_char_map.json` and locked in place by a parity test on each
platform (`api/tests/test_chinese_script.py`, `frontend/src/lib/chineseScript.test.ts`, and the
Android equivalent once the fast-follow lands). The table was derived by running every current
Chinese book name/alias in `translation_registry.py` through an authoritative
Simplified→Traditional converter (dev-time only, not a shipped dependency) and collecting the
resulting character-level diffs — not guessed. It covers `亞來傳創啓啟師彌後數書歷爾猶瑪竇紀約結羅記詩該賽達錄門馬鴻`
(29 characters; two Traditional variants of the same character, 啟 and 啓, both map to 启).

The original story estimated "< 20 unique characters" for the frontend table; the actual count
derived from the real book-name data is 29. Still far smaller than a 50KB npm package.

## What shipped in this PR (backend + web)

- `api/utils/chinese_script.py` / `frontend/src/lib/chineseScript.ts` — the table and
  `normalize_traditional_to_simplified()` / `normalizeTraditionalToSimplified()`, both a no-op on
  non-Chinese text and length-preserving by construction.
- `api/utils/verse_parser.py` — normalization inserted at all four call sites that run the verse
  regex (`parse_verse_reference`, `extract_all_references`, both directions of
  `_find_adjacent_reference`, and `extract_reference_mentions`). The last one is the offset-return
  path: the *matching* copy is normalized, but `ref_span`/`sentence`/`content_text` are still
  sliced from the original text, so a Traditional-script user's own words are preserved verbatim
  in what gets returned.
- `api/utils/book_names.py` — `normalize_book_name()` retries against the Simplified form when the
  exact-case lookup misses, so a Traditional book name arriving already-isolated (e.g. from a
  client-supplied parameter) still resolves.
- `frontend/src/lib/verseExtraction.ts` — `extractVerseReferences()` normalizes upfront (it returns
  a Set of reference keys, not offsets, so a plain overwrite is safe); `isKnownBook()` and the
  internal `normalizeBookName()` retry against the Simplified form, same shape as the backend.
- `frontend/src/lib/linkifyVerses.ts` (`linkifyPlainSegment`) and
  `frontend/src/components/ChatMessage.tsx` (`highlightText`, `handleTextClick`, and the
  already-linkified-markdown fallback in the `a` renderer) — the shadow-string pattern: the verse
  regex runs against a normalized copy for matching/book-validation, while the *displayed* text and
  the `lastIndex` bookkeeping are sliced from the original string.

## Deferred: Android

`injectVerseLinks` (`ChatMessageItem.kt`) has a 6-group two-alternative regex, a manual rewind
loop, and — unlike the web version — it *reconstructs* the display string as
`"$book $chapter$sep$verse"` rather than re-slicing the original match, so preserving Traditional
display text there means pulling the original book substring out of the match's capture-group
ranges per alternative. It's also the one platform whose parity test
(`VerseCorpusParityTest.kt`) cannot be run locally (no Android SDK in this environment) — shipping
that surgery unverified was judged higher-risk than shipping it as a small, explicitly-tracked
fast-follow. The eight `zh_hant_*` / `zh_mixed_script_*` corpus cases carry
`"skip": ["android"]` for exactly this reason; removing that skip (plus adding the Kotlin table
and the display-preserving rewrite to `injectVerseLinks`, and the equivalent T2S retry to
`BookNameNormalizer.kt`) is the fast-follow.

## Acceptance Criteria

- [x] Backend: Traditional Chinese book names are normalized to simplified before verse parsing
- [x] Frontend: Traditional Chinese book names are normalized before verse extraction
- [ ] Android: Traditional Chinese book names are normalized in client-side regex (fast-follow)
- [x] Mixed-script text handled correctly (e.g. `創世记` — Traditional 創 + already-Simplified 世记)
- [x] No regression on existing simplified Chinese tests (full backend + frontend suites green)
- [x] Minimal bundle size impact — a 29-character table, not a library
- [x] Performance: normalization is a single `str.translate()` / regex `.replace()` pass, well
      under 1ms
- [x] Display text preserved: text shown to the user retains its original script (Traditional or
      mixed); only the internal matching copy is normalized. Not in the original AC list — added
      here because it's the property most easily gotten wrong (a naive `text = t2s(text)` at the
      top of a rendering function would pass every other AC while silently rewriting a
      Traditional-script user's own message to Simplified on screen).

## Related

- PR #389 — the 记↔纪 / Catholic 思高本 aliases this story's table complements
- `tests/fixtures/t2s_char_map.json`, `tests/fixtures/verse_reference_corpus.json`,
  `tests/fixtures/README.md` — shared cross-platform fixtures and the `skip`/`skipReason`
  convention used for the Android deferral
