# BITB-071: Verse Link Click Sends NaN Chapter for Non-ASCII (Devanagari/Eastern Arabic) Digits

**Status:** ✅ Done (PR #893 merged 2026-07-17)
**Priority:** P1 (High) — breaks the core "click a cited verse" flow for every Hindi
response and any Arabic response that uses native Eastern Arabic numerals.
**Size:** S (< 4 hrs)
**Created:** 2026-07-17
**Completed:** 2026-07-17

## User Story

As a Hindi (or Arabic) user, I want to click a cited verse reference in the chat answer
and have it open the correct chapter, so that I can read the scripture the assistant
quoted.

## Problem / Motivation

Reported: clicking a Hindi verse link (e.g. "यूहन्ना ५:२४") called the API with a
literal `NaN` chapter:

```
GET /api/v1/scripture/chapter/यूहन्ना/NaN?translation=hindi&lang=hi → 422
```

**Root cause (frontend):** three independent places parse a matched
`book chapter:verse` reference into numbers. Only `verseExtraction.ts` (citation
matching against backend data) normalized Devanagari (०-९) and Eastern Arabic (٠-٩)
digits before converting to a number. The two places that build/parse the actual
click target did not:

- `frontend/src/lib/linkifyVerses.ts` — built the `verse://` href from raw regex
  captures, then `parseVerseHref()` ran a plain `parseInt` on non-ASCII digits → `NaN`.
- `frontend/src/components/ChatMessage.tsx` — `handleTextClick()` had the same
  unnormalized `parseInt` for the click-on-highlighted-text path.

**Related parity gap found while investigating (Android):** Android's verse regex
(`ChatMessageItem.kt`) uses plain `\d` in its chapter/verse capture groups. Java regex's
`\d` only matches ASCII `0-9` unless `Pattern.UNICODE_CHARACTER_CLASS` is set, which
this codebase does not set. So on Android, a reference written with native Devanagari
or Eastern Arabic numerals wasn't even recognised as a verse reference — a different
failure mode (silently no link at all) from the same root cause (missing non-ASCII
digit support), and exactly the "parsers diverge subtly" trap called out in
`AGENTS.md` → *Verse Detection / Parsing*.

**Backend not affected:** `api/utils/verse_parser.py` uses Python's `re` module,
where `\d` matches any Unicode decimal-digit character by default, and `int()` natively
parses Unicode decimal digit strings (`int("५२४") == 524`, confirmed directly). No
backend change needed — `api/tests/test_verse_parser.py` already has pre-existing
Devanagari- and Eastern-Arabic-numeral coverage (`test_hindi_devanagari_numerals`,
`test_arabic_eastern_numerals`, etc., ~lines 1077, 1085, 1328, 1336), so this parser
was already exercised against the exact bug scenario before this fix.

## Fix

- Frontend: exported `normalizeDigits()` from `verseExtraction.ts` (previously private)
  and applied it at both previously-unnormalized parse sites.
- Android: extended the chapter/verse digit character class in `ChatMessageItem.kt`
  from plain `\d` to `[0-9०-९٠-٩]` (`CV_DIGIT`) in all four regex
  alternatives (default + dynamic pattern), matching the frontend's `versePatterns.ts`
  approach. Confirmed via `jshell` that `Character.digit`/`Integer.parseInt` already
  handle pure Devanagari/Eastern-Arabic digit strings correctly once the regex captures
  them — only the capture was missing, not the numeric conversion.
- Backend: no code change needed — already correct, and already tested.

## Why this regressed despite existing test coverage

`verseExtraction.test.ts` already had thorough Devanagari/Eastern-Arabic digit
coverage — but only for the citation-matching path. `linkifyVerses.test.ts` and
`ChatMessage.verseMarking.test.tsx` (the modules that build the actual clickable
API call) had zero non-ASCII-digit test cases. Testing digit normalization in one
of three parse sites created false confidence that the feature worked end to end.

## Acceptance Criteria

- [x] Clicking a Hindi verse reference with Devanagari digits calls the API with a
      numeric chapter/verse, not `NaN`.
- [x] Same for Eastern Arabic digits.
- [x] Regression tests added at every parse site that was previously untested
      (`linkifyVerses.test.ts`, `ChatMessage.verseMarking.test.tsx`), not just the
      one that already had coverage.
- [x] Android verse-detection regex mirrors the frontend's non-ASCII digit support
      (parser parity, per `AGENTS.md`).
- [x] Backend parity confirmed: no code change needed, pre-existing tests already
      cover Devanagari/Eastern-Arabic numerals end to end.
- [x] Android tests (`VerseRefLinkTest.kt`) verified green in CI — could not run
      `./gradlew testDebugUnitTest` locally (sandbox network policy blocks
      `dl.google.com`), but PR #893's `android-ci.yml` run confirmed all jobs green:
      `Unit Tests`, `Kotlin Compile Check`, `Android Lint`, `Instrumented UI Tests`,
      `Compose UI Tests (Robolectric)`, `Build Prod APK`.

## Files Changed

- `frontend/src/lib/verseExtraction.ts` — export `normalizeDigits`
- `frontend/src/lib/linkifyVerses.ts` — normalize digits before building href / in `parseVerseHref`
- `frontend/src/components/ChatMessage.tsx` — normalize digits in `handleTextClick`
- `frontend/src/lib/linkifyVerses.test.ts`, `frontend/src/components/ChatMessage.verseMarking.test.tsx` — regression tests
- `frontend/src/app/[locale]/page.test.tsx` — added `normalizeDigits` to the existing `verseExtraction` mock allowlist
- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt` — `CV_DIGIT` character class
- `android/app/src/test/kotlin/org/voxquieta/app/components/VerseRefLinkTest.kt` — regression tests
