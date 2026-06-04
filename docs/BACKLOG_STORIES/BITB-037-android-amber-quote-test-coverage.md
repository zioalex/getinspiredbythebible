# BITB-037: Android Amber Quote Chip — Test Coverage Follow-up

**Status:** ✅ Done (PR #677 + this PR)

## User Story

As a maintainer of the Android app, I want the inline amber-quote span and its
quote-detection regex to be fully unit-tested, so that future refactors of
`ChatMessageItem.kt` are safe and the styling behaviour introduced in BITB-036
(PR #637) does not silently regress.

## Implementation Note (updated 2026-06-04)

The story doc was written against an initial `private InlineAmberQuoteSpan :
ReplacementSpan` implementation. Before any tests were written that class was
replaced with `internal fun applyQuoteHighlights(spanned: Spannable)`, which
uses standard inline spans (`BackgroundColorSpan`, `ForegroundColorSpan`,
`StyleSpan`, `TypefaceSpan`) so that long quotes wrap across lines instead of
being clipped. Steps 1, 2, and 5 of the original Proposed Solution are
**obsolete** — there is no `ReplacementSpan` to make `internal`, no `getSize()`
/`draw()` to test, and `applyQuoteHighlights` is already `internal` and
integration-tested.

## What was done

### PR #677 (branch `claude/affectionate-cannon-6iiWU`)

- **Bug fix:** added `\n` to `QUOTE_HIGHLIGHT_REGEX` negated content class so
  quotes do not match across paragraph breaks.
- **New regex tests** in `VerseRefLinkTest.kt`: CJK corner `「…」`, double CJK
  `《…》`, no-match-across-newline, single-line-after-newline guard.
- **Span tests** in `QuoteHighlightSpanTest.kt`: CJK corner, double CJK, no
  highlight across newline.

### This PR

- **Comment** at `enableSoftBreakAddsNewLine = true` (line ~550 of
  `ChatMessageItem.kt`) explaining why the flag must stay `true` — guards
  against the Markwon 0.7.x default (`false`) collapsing chat line breaks.
- **Span-layer tests** added to `QuoteHighlightSpanTest.kt`:
  - `applies the exact amber background and dark-amber foreground colors` —
    pins the hardcoded `0xFFFFFBEB` / `0xFF78350F` web-parity colors.
  - `applies an italic serif typeface over the quote` — pins
    `StyleSpan(ITALIC)` + `TypefaceSpan("serif")`.
  - `all four span types cover the identical quoted range` — ensures styling
    spans never drift from the background highlight.
  - `does not highlight quotes shorter than three content chars` — mirrors the
    `{3,}` minimum at the span-application layer.
  - `applies a full independent span set to each of multiple quotes` — extends
    the existing multi-quote count test to all four span types.

## Acceptance Criteria (revised)

- [x] `applyQuoteHighlights` is `internal` and testable from the test source set
- [x] `applyQuoteHighlights` is integration-tested (applies spans over quoted
      text, no `ReplacementSpan` used, span ranges correct)
- [x] `QUOTE_HIGHLIGHT_REGEX` has passing tests for CJK corner `「…」` and double
      CJK `《…》` (PR #677)
- [x] Newline-spanning quote behaviour decided (excluded), implemented, and
      covered by a regression test (PR #677)
- [x] `applyQuoteHighlights` span colors, typeface, and range coverage tested
      (this PR)
- [x] `enableSoftBreakAddsNewLine = true` guarded by an explanatory comment
      explaining the Markwon 0.5→0.7 default-flip risk (this PR)
- [x] All existing + new unit tests pass; Android Lint, Unit Tests, and Build
      Prod APK all pass

## References

- PR #637 — BITB-036 implementation (inline amber quote chip); origin of these
  test gaps
- PR #677 — CJK regex tests + `\n` fix
- `docs/BACKLOG_STORIES/BITB-036-android-inline-amber-quote-chip.md` — parent story
- `android/app/src/main/kotlin/…/ChatMessageItem.kt` — `applyQuoteHighlights`,
  `QUOTE_HIGHLIGHT_REGEX`, `enableSoftBreakAddsNewLine`
- `frontend/src/components/ChatMessage.tsx → highlightQuotes()` — web reference
