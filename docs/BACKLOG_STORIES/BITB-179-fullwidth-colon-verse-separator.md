# BITB-179: Accept the Fullwidth Colon as a Chapter:Verse Separator (All Three Parsers)

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-10
**Prompted by:** BITB-178 follow-up — the fullwidth-colon case is pinned as a strict `xfail` in
`api/tests/test_passage_context.py` (`路加福音1：79`).

## Bug Report

Chinese (and some Japanese/Korean) text writes chapter and verse with a fullwidth colon:
`路加福音1：79`, `约翰福音3：16`. The backend `CV_PATTERN` (`api/utils/verse_parser.py`) only accepts
`[:,]`, so the reference is not detected. Nothing downstream runs: no direct verse lookup, no
BITB-178 surrounding-passage context, no grounding (BITB-053), and no link in the chat bubble.
Users typing on a Chinese IME produce `：` by default, so this is the common form, not an edge case.

The separators are shared: `tests/fixtures/verse_grammar.json` (`chapter_verse_separators`) is the
single source, and `scripts/generate_localized_book_map.py` generates
`frontend/src/lib/verseGrammar.generated.ts` and the Android `VerseGrammar.kt` from it. The backend
`CV_PATTERN` is checked against the same fixture by `api/tests/test_verse_grammar_parity.py`.

## Functional Requirements

- FR1 Add `：` (U+FF1A) to `chapter_verse_separators` in `verse_grammar.json`; regenerate the web and
  Android grammar with the generator (never by hand); extend the backend `CV_PATTERN` to match.
- FR2 Normalise the matched reference to the ASCII form (`Luke 1:79`) everywhere a reference string
  is built (`VerseReference.__str__`, frontend link href, Android link), so lookups and cache keys
  are unchanged.
- FR3 Consider the fullwidth range dash and fullwidth digits only if they appear in real traffic;
  out of scope unless the audit below finds them.

## Acceptance Criteria

- [ ] `路加福音1：79`, `「约翰福音3：16」`, `（诗篇23：1）` and a range `马太福音5：3-12` parse in the backend,
      the frontend and Android, each with a parity test
- [ ] The strict `xfail` in `test_passage_context.py` is removed and the case passes in both
      `chat()` and `chat_stream()`
- [ ] Grounding integration test through `chat()` for a fullwidth-colon citation (resolved and
      corrected), per the AGENTS.md grounding rule
- [ ] No regression in the 11-language parser corpus (`test_verse_parser_corpus.py`) and no false
      positives on prose like `时间：3` (a non-book word before the colon)
- [ ] `test_verse_grammar_parity.py`, Android `VerseGrammarTest` / `VersesPanelGrammarParityTest`
      and the frontend `versePatterns` tests updated

## Out of Scope

- Fullwidth digits (`１：７９`) unless observed in production logs.
