# BITB-167: Tapped Verse Link With an En-Dash Range Falls Back to Verse 1 on Android

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-09-30
**Found by:** BITB-164 verification

## User Story

**As** an Android reader, **I want** tapping "Romans 8:28–30" to open verse 28, **so that** en-dash
ranges behave like hyphen ranges.

## Why This Exists

`parseVerseLink` in `ChatMessageItem.kt` splits the verse range on `-` only, while the shared
`VerseGrammar.RANGE_SEPARATORS` also accepts the en dash. The link is injected but resolves to
verse 1.

## Acceptance Criteria

- [ ] `parseVerseLink` splits on `VerseGrammar.RANGE_SEPARATORS`
- [ ] Test across all 11 languages' separators (hyphen, en dash) and non-ASCII digits
