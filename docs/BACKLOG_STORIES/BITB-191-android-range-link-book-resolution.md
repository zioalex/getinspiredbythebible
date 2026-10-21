# BITB-191: Android Range Links Skip the Cited-Verse Book Fallback

**Status:** 🎯 Todo
**Priority:** P3
**Size:** XS
**Created:** 2026-10-12
**Prompted by:** BITB-179 follow-up — noted by the builder and confirmed by the verifier.

## Bug Report

`resolveLinkBook` (`android/.../ChatMessageItem.kt` ~L324) falls back to the cited verses to pick the
link's book when the name map does not resolve it. It receives the verse group with the range still
attached (`16-18`, `3～12`), so `normalizeVerseDigits(verse).toIntOrNull()` is `null` and the fallback
never runs for a range. Single verses are unaffected. Pre-existing for `-` ranges; BITB-179 added
`～`/`〜` to the same path.

## Functional Requirements

- FR1 Use the range start (split on `VerseGrammar.RANGE_SEPARATORS`) for the fallback lookup.

## Acceptance Criteria

- [ ] Unit test: an unmapped book with a range reference resolves via the cited verses, for `-`, `–`,
      `～` and `〜`
