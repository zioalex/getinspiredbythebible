# BITB-037: Android Amber Quote Chip — Test Coverage Follow-up

**Status:** 🎯 Todo

## User Story

As a maintainer of the Android app, I want the inline amber-quote span and its
quote-detection regex to be fully unit-tested, so that future refactors of
`ChatMessageItem.kt` are safe and the styling behaviour introduced in BITB-036
(PR #637) does not silently regress.

## Problem

PR #637 (BITB-036) introduced `InlineAmberQuoteSpan` (a `ReplacementSpan`)
applied via compose-markdown's `beforeSetMarkdown` hook, plus a new
`QUOTE_HIGHLIGHT_REGEX`. The regex is well-covered by unit tests, but the PR's
own acceptance criterion — *"new unit tests cover `InlineAmberQuoteSpan` **and**
`QUOTE_HIGHLIGHT_REGEX`"* — is **not** met. The following gaps remain:

1. **`InlineAmberQuoteSpan` has zero tests** and is declared `private`, so the
   test package cannot even reference it. The span is untestable as written.
2. **Two advertised regex quote styles are untested:** CJK corner `「…」`
   (U+300C / U+300D) and double CJK `《…》` (U+300A / U+300B). Both are claimed
   in the PR body but have no assertion.
3. **Newline-spanning matches are unguarded.** The content class
   `[^"“”»」》]{3,}` does **not** exclude `\n`, so a stray
   unbalanced quote can highlight across newlines / paragraphs — a regression
   versus the previous same-line-only `VERSE_QUOTE_REGEX`, with no test pinning
   the behaviour.
4. **`beforeSetMarkdown` wiring is untested** — nothing asserts that an
   `InlineAmberQuoteSpan` is actually applied to the spannable for quoted text.
5. **`enableSoftBreakAddsNewLine = true`** is called out in BITB-036 as
   load-bearing (preserving 0.5.x soft-break rendering after the 0.7.x default
   flipped to `false`), but has no regression test.

## Proposed Solution

### Step 1 — Make `InlineAmberQuoteSpan` testable

Change its visibility from `private` to `internal` in
`ChatMessageItem.kt` so the test source set can construct it directly.

```kotlin
internal class InlineAmberQuoteSpan(
    // …unchanged constructor…
) : ReplacementSpan() { … }
```

---

### Step 2 — Unit-test `InlineAmberQuoteSpan`

Add Robolectric tests (`robolectric = "4.14.1"` is already a project
dependency) — `Paint`/`Canvas` require an Android runtime:

- **`getSize()`** returns `measureText + barWidth + paddingH * 2` for a known
  string and paint.
- **`draw()` paint save/restore** — assert `paint.color`, `paint.style`, and
  `paint.typeface` are restored to their pre-`draw()` values afterwards. This
  guards the explicit fix that stops amber colour / serif typeface bleeding into
  adjacent prose on the same line (Markwon reuses a shared `Paint`).

---

### Step 3 — Cover the remaining quote styles in `QUOTE_HIGHLIGHT_REGEX`

Add assertions for the two untested pairs:

```kotlin
// CJK corner brackets
assertTrue(QUOTE_HIGHLIGHT_REGEX.containsMatchIn("「神は世を愛された」"))
// Double CJK corner brackets
assertTrue(QUOTE_HIGHLIGHT_REGEX.containsMatchIn("《神は世を愛された》"))
```

---

### Step 4 — Pin newline behaviour

Decide and lock down what happens when a candidate quote span contains a
newline. **Recommended:** exclude `\n` from the content class so matches stay
within a single paragraph (matching the prior `VERSE_QUOTE_REGEX` intent and
avoiding accidental highlighting of large unbalanced-quote blocks).

```kotlin
// add \n to the negated content class
internal val QUOTE_HIGHLIGHT_REGEX = Regex(
    "(["“”«„「《]" +
        "(?:[^"“”»」》\n]{3,})" +
        "["”“»」》])"
)
```

Add a regression test asserting a quote opener and closer separated by a
newline does **not** produce a single cross-paragraph match.

---

### Step 5 — Integration-test `beforeSetMarkdown`

Add a Robolectric test that runs quoted text through the span-application logic
(extract the `beforeSetMarkdown` lambda into a small testable helper, e.g.
`applyQuoteHighlights(spannable: Spannable)`, and call it) and asserts at least
one `InlineAmberQuoteSpan` is present over the expected range.

---

### Step 6 — Soft-break regression test

Add a test (or documented Compose UI test) asserting that with
`enableSoftBreakAddsNewLine = true`, a single newline in message content renders
as a line break — guarding against the 0.7.x default (`false`) collapsing
existing chat messages.

## Files Affected

| File | Change |
|---|---|
| `android/app/src/main/kotlin/…/ChatMessageItem.kt` | `private` → `internal` on `InlineAmberQuoteSpan`; add `\n` to `QUOTE_HIGHLIGHT_REGEX` content class; optionally extract `beforeSetMarkdown` body into a testable helper |
| `android/app/src/test/kotlin/…/InlineAmberQuoteSpanTest.kt` (new) | Robolectric tests for `getSize()`, `draw()` paint save/restore, and `beforeSetMarkdown` span application |
| `android/app/src/test/kotlin/…/VerseRefLinkTest.kt` | Add `QUOTE_HIGHLIGHT_REGEX` tests for CJK / double-CJK styles and the newline regression |

## Acceptance Criteria

- [ ] `InlineAmberQuoteSpan` is `internal` and constructible from the test source
      set
- [ ] `InlineAmberQuoteSpan.getSize()` is unit-tested for known input
- [ ] `InlineAmberQuoteSpan.draw()` is unit-tested to restore `paint` color,
      style, and typeface after drawing (no prose bleed)
- [ ] `QUOTE_HIGHLIGHT_REGEX` has passing tests for CJK corner `「…」` and double
      CJK `《…》`
- [ ] Newline-spanning quote behaviour is decided, implemented, and covered by a
      regression test
- [ ] `beforeSetMarkdown` span application is covered by an integration test
- [ ] `enableSoftBreakAddsNewLine = true` soft-break rendering is regression-tested
- [ ] All existing + new unit tests pass; Android Lint, Unit Tests, and Build
      Prod APK all pass

## References

- PR #637 — BITB-036 implementation (inline amber quote chip); origin of these
  test gaps
- `docs/BACKLOG_STORIES/BITB-036-android-inline-amber-quote-chip.md` — parent story
- `android/app/src/main/kotlin/…/ChatMessageItem.kt` — `InlineAmberQuoteSpan`,
  `QUOTE_HIGHLIGHT_REGEX`, `beforeSetMarkdown` wiring
- `frontend/src/components/ChatMessage.tsx → highlightQuotes()` — web reference
