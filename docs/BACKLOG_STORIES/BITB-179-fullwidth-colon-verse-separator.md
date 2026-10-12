# BITB-179: Fullwidth Verse References — Colon, Range Tildes and Digits (All Three Parsers)

**Status:** 🚧 In Review (PR #1163)
**Priority:** P2
**Size:** M
**Created:** 2026-10-10
**Prompted by:** BITB-178 follow-up — the fullwidth-colon case is pinned as a strict `xfail` in
`api/tests/test_passage_context.py` (`路加福音1：79`).

## Bug Report

Chinese IME input writes chapter and verse with a fullwidth colon (`路加福音1：79`, `约翰福音3：16`),
often writes ranges with a wave dash or fullwidth tilde (`马太福音5：3～12`, `5：3〜12`), and sometimes
uses fullwidth digits (`约翰福音３：１６`). None of these are detected consistently today:

| Form | Backend | Web | Android |
|------|---------|-----|---------|
| `：` separator | ✗ (`CV_PATTERN` is `[:,]`) | ✗ | ✗ |
| `～` / `〜` range | ✗ (range is `[-–]`) | ✗ | ✗ |
| fullwidth digits `０-９` | ✓ by accident (Python `\d` is Unicode) | ✗ | ✗ |

A missed reference gets no direct verse lookup, no BITB-178 passage context, no grounding (BITB-053)
and no link in the chat bubble. The web and Android grammars are generated from
`tests/fixtures/verse_grammar.json` by `scripts/generate_localized_book_map.py`. The backend
`CV_PATTERN` (`api/utils/verse_parser.py`) is contract-tested against the same file by
`api/tests/test_verse_grammar_parity.py`.

## User Story

**As** a Chinese-speaking user typing on a phone IME, **I want** `路加福音1：79`, `马太福音5：3～12` and
`约翰福音３：１６` to be recognised as verse references, **so that** I get the same verse lookup, passage
context, grounding and tappable links as someone typing `Luke 1:79`.

## Decisions (product owner, 2026-10-11)

- Separators: add **only** the fullwidth colon `：` (U+FF1A). Not the fullwidth comma `，`, not `﹕`/`∶`.
- Ranges: add the fullwidth tilde `～` (U+FF5E) and the wave dash `〜` (U+301C). Not the em dash.
- Fullwidth digits `０`–`９` (U+FF10–U+FF19): **supported in all three parsers**, normalised to ASCII.
- Accepted after **any** book name in **any** of the 11 languages (the grammar is shared, no
  per-script gating).

## Functional Requirements

- FR1 `verse_grammar.json`: add `：` to `chapter_verse_separators`, `～` and `〜` to
  `range_separators`, and a `Fullwidth` entry (`０`–`９`) to `non_ascii_digit_ranges`. Regenerate
  `verseGrammar.generated.ts` and `VerseGrammar.kt` with the generator — never by hand.
- FR2 Backend: extend `CV_PATTERN` to the same separator, range and digit sets, keeping it
  contract-equal to the JSON (`test_verse_grammar_parity.py` updated to cover the digit ranges too).
- FR3 Normalise to ASCII wherever a reference is turned into data: backend `VerseReference` ints and
  `str()` (`Luke 1:79-81`), web `normalizeDigits` (add fullwidth), Android digit → `Int` conversion and
  link URLs. Lookups, cache keys, URLs and `scripture_context` are byte-identical to the ASCII form.
- FR4 Every consumer that re-parses a reference string or splits on a range separator stays correct:
  web `verseExtraction`, `linkifyVerses`, `speakableText`; Android `ChatMessageItem.parseVerseLink`,
  `VersesPanel`, `tts/SpeakableText`; backend grounding / inline-quote extraction / citation spans.
- FR5 The surrounding text is unchanged on display (the link label keeps the user's `：`/`～`); only
  the parsed data is normalised.

## Non-Functional Requirements

- **Platforms:** backend, web, Android. No API schema change.
- **Languages:** parametrised tests over all 11 (en, it, de, es, fr, pt, ar, ru, zh, hi, ko): a
  fullwidth-colon reference after each language's book name parses to the same reference as the
  ASCII form; CJK no-space, bracketed `「…」` / `（…）` / `《…》`, Devanagari and Eastern Arabic digits
  keep working.
- **Version-faithfulness:** passage context for a fullwidth reference uses the user's selected
  translation (e.g. CUV vs CUVS or KJV vs WEB), as in BITB-178.
- **Performance / safety:** no new unbounded quantifiers; the existing ReDoS guards and their tests
  still pass.

## Acceptance Criteria

- [x] AC1 `路加福音1：79`, `「约翰福音3：16」`, `（诗篇23：1）`, `马太福音5：3-12`, `马太福音5：3～12`,
      `马太福音5：3〜12` and `约翰福音３：１６` parse to the same reference as their ASCII forms in the
      backend, the web and Android, each with a test per parser
- [x] AC2 Parity: `test_verse_grammar_parity.py` (backend vs JSON, now including digit ranges),
      Android `VerseGrammarTest` / `VersesPanelGrammarParityTest`, and the web grammar test all pass
      against the regenerated grammar; the generator's own test passes
- [x] AC3 The strict `xfail` in `test_passage_context.py` is removed; the case passes in `chat()` and
      `chat_stream()`, and the window uses the selected translation
- [x] AC4 Grounding integration test through `chat()` for a fullwidth-colon citation in the model's
      answer: resolved and corrected (per the AGENTS.md grounding rule)
- [x] AC5 Cross-language test: each of the 11 languages' book name + `１：７９` / `1：79` parses
- [x] AC6 No false positives: `时间：3点`, `比例3：1`, `第3～5章` without a book name, and
      `约翰福音3：` (no verse) produce no reference in any parser; the 11-language corpus
      (`test_verse_parser_corpus.py`) does not regress
- [x] AC7 Normalisation: link URLs, `VerseReference.__str__`, web `references` set keys and Android
      `parseVerseLink` output contain only ASCII digits, `:` and `-`
- [ ] AC8 Backend, web (vitest, lint, tsc, build) and Android unit suites pass; Android verified by CI
      if Gradle cannot run in the sandbox

  *AC6 exception (deliberate):* on Android, `约翰福音3：` (no verse) still yields a chapter-only
  link, exactly like the ASCII `约翰福音3:` today — Android links bare chapter references
  (`Psalm 23`) by design. The shared corpus case is skipped for Android with a `skipReason`.

**Verification (2026-10-11, commit 197ca15):** independent verifier PASS after one FAIL→fix loop
(Android link tests asserted a capitalised book; bundled map is lowercase). Backend 5201 passed /
8 failed (the 8 sandbox-only failures also on `main`) / 120 skipped; ruff, black, mypy clean;
reverting `CV_PATTERN` makes 118 of the new tests fail (not vacuous). Web vitest 1299 passed, lint
0 errors, tsc and build clean. Android Gradle cannot fetch AGP in the sandbox: the regexes were
re-run on a JVM with the bundled book map and every new assertion traced; AC8 stays open until the
PR's Android CI is green.

## Out of Scope

- Fullwidth comma `，` and other colon look-alikes (`﹕`, `∶`).
- Em dash `—` as a range separator.
- Japanese book names (not a supported language).
- Changing how the reference is displayed in the chat bubble.
- A bracketed chapter:verse after the book name (`罗马书（8：28）`) — BITB-184.

## Open Questions

- None blocking.

---

## Plan (2026-10-11)

### Findings

- `tests/fixtures/verse_grammar.json` is the single source for separators, range separators and
  non-ASCII digit ranges. `scripts/generate_localized_book_map.py` emits them generically, so the
  web (`verseGrammar.generated.ts`) and Android (`VerseGrammar.kt`) regexes pick up new characters
  with no hand edits to the patterns (`versePatterns.ts` builds `[${CV_SEPARATOR_CLASS}]`,
  `[${RANGE_SEPARATOR_CLASS}]` and `[\d${NON_ASCII_DIGIT_CLASS}]`; `ChatMessageItem.kt` builds
  `CV_DIGIT = "[0-9$NON_ASCII_DIGIT_CLASS]"` and the same classes).
- Backend `CV_PATTERN = r"(\d+)[:\,](\d+)(?:\s*[-–]\s*(\d+))?"`. Python `\d` is Unicode, so fullwidth
  digits already match and `int()` converts them; `VerseReference` stores ints, so `str()` is ASCII.
- Digit normalisation is hard-coded to Devanagari + Eastern Arabic in two places: web
  `normalizeDigits` (`frontend/src/lib/verseExtraction.ts`) and Android `normalizeDigits`
  (`android/.../tts/SpeakableText.kt`, private). Android link building
  (`ChatMessageItem.kt` ~L443–455) puts the raw matched chapter/verse strings into the `verse://`
  URL and rebuilds the display as `"$book $chapter$sep$verse"` with `sep` only `:` or `,`.
  Kotlin `toIntOrNull()` accepts any Unicode decimal digit, so parsing works but URLs would carry
  fullwidth digits.
- `tests/fixtures/verse_reference_corpus.json` is the shared cross-parser corpus (pytest
  `test_verse_parser_corpus.py`, vitest `verseCorpus.crossplatform.test.ts`, JUnit
  `VerseCorpusParityTest.kt`) and supports negative cases (`expectNone: true`).

### Changes per file

1. `tests/fixtures/verse_grammar.json` — `chapter_verse_separators: [":", ",", "："]`;
   `range_separators: ["-", "–", "～", "〜"]` (hyphen stays first); add
   `{ "label": "Fullwidth", "start": "０", "end": "９" }` to `non_ascii_digit_ranges`.
2. Run `python scripts/generate_localized_book_map.py` → regenerated
   `frontend/src/lib/verseGrammar.generated.ts` and
   `android/app/src/main/kotlin/org/voxquieta/app/utils/VerseGrammar.kt` (commit the output).
3. `api/utils/verse_parser.py` — `CV_PATTERN = r"(\d+)[:\,：](\d+)(?:\s*[-–～〜]\s*(\d+))?"`; update the
   comment above it. No other backend code change expected; confirm `extract_inline_quotes`,
   citation spans and grounding only consume the parsed ints / `str(ref)`.
4. `api/tests/test_verse_grammar_parity.py` — existing separator/range assertions now cover the new
   characters; add a test that every digit in each `non_ascii_digit_ranges` entry matches the
   backend's digit class and converts with `int()` (documents that `\d` is a superset).
5. `frontend/src/lib/verseExtraction.ts` — rewrite `normalizeDigits` to map every code point in
   `NON_ASCII_DIGIT_RANGES` (from the generated grammar) to ASCII, so a new range in the JSON needs
   no further code; keep the exported name and behaviour for Devanagari/Eastern Arabic.
6. Android — new `android/app/src/main/kotlin/org/voxquieta/app/utils/VerseDigits.kt` with
   `fun normalizeVerseDigits(s: String): String` driven by `VerseGrammar.NON_ASCII_DIGIT_RANGES`, and
   `fun normalizeRangeSeparators(s: String): String` (any `RANGE_SEPARATORS` char → `-`).
   Use it in `tts/SpeakableText.kt` (replace the private `normalizeDigits`), in
   `ChatMessageItem.kt` link building (URL path: ASCII digits, `-` for ranges; display keeps the
   source's separator — extend `sep` detection to the actual matched separator char, including
   `：`, and keep the digits as written), and in `resolveLinkBook` / `VersesPanel.kt` before
   `toIntOrNull()` for consistency.
7. Shared corpus `tests/fixtures/verse_reference_corpus.json` — add positive cases:
   `路加福音1：79`, `「约翰福音3：16」`, `（诗篇23：1）`, `马太福音5：3-12`, `马太福音5：3～12`, `马太福音5：3〜12`,
   `约翰福音３：１６`, `요한복음 3：16`, `Lukas 1：79`, `यूहन्ना ३：१६`; negative cases (`expectNone`):
   `时间：3点`, `比例3：1`, `第3～5章`, `约翰福音3：` (no verse). Follow the README schema (`origin`,
   `skip` only with a reason).
8. Per-parser tests:
   - Backend: parametrised 11-language test in `api/tests/test_verse_parser.py` (each language's
     John/Luke book name from `translation_registry` + `1：79` and `１：７９` → `Luke 1:79` /
     same reference as ASCII), range `～`/`〜` → `verse_end`, and `str(ref)` is ASCII.
   - Backend: remove the strict `xfail` in `api/tests/test_passage_context.py`; add a grounding
     integration test through `chat()` (mock `search_service.get_verse`) where the model's answer
     cites `约翰福音3：16` with wrong text and the output is corrected to the DB text for the
     selected translation (follow the existing grounding integration tests' harness).
   - Web: tests in the existing `versePatterns` / `verseExtraction` / `linkifyVerses` test files:
     fullwidth forms extract to ASCII keys, `linkifyVerses` href is ASCII while display keeps
     `：`/`～`/fullwidth digits, `normalizeDigits("３：１６")` digits → ASCII.
   - Android: `VerseGrammarTest` (new separators/ranges/digit range present),
     `ParseVerseLinkTest` / `VerseRefLinkTest` (fullwidth reference → ASCII `verse://` URL,
     display keeps `：`), a unit test for `VerseDigits.kt`, and `SpeakableTextParityTest` still passing.
9. `AGENTS.md` — update the *Multilingual & Multi-Version Correctness* note that says all three
   parsers accept `[:,]` to the new separator set.

### Verification

```bash
python scripts/generate_localized_book_map.py --check   # or re-run and confirm a clean git diff
cd api && DATABASE_URL=postgresql://test:test@localhost/test python -m pytest tests/ -q   # pragma: allowlist secret
cd api && ruff check . --select E,F,W,C90,I,N --ignore E501 && black --check . && mypy . --ignore-missing-imports --no-strict-optional
cd frontend && npx vitest run && npm run lint && npx tsc --noEmit && npm run build
cd android && ./gradlew testDebugUnitTest --no-daemon   # CI is the gate if Gradle cannot run here
```

Expected: no new backend failures versus `main` in the sandbox; all new corpus cases pass on all
three platforms; AC1–AC8 each map to at least one test above.
