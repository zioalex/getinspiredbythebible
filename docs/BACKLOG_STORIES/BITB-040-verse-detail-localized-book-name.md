# BITB-040: Verse-Detail Header Shows English Book Name Instead of Localized

**Status:** ✅ Done
**Priority:** P1 (High) — pervasive localization defect affecting every non-English locale on every verse tap
**Size:** S (< 4 hours)
**Created:** 2026-06-10

## User Story

As a non-English user, when I tap a Bible verse reference and the verse-detail
bottom sheet opens, I want the header to show the reference using my translation's
book name (e.g. Italian *"Esodo 30:22"*), so that the reference matches the
language I'm reading in and the app feels trustworthy and consistent.

## Problem

Tapping a verse opened the bottom sheet with the header showing the **English**
book name (e.g. **"Exodus 30:22"**) instead of the translation's localized name
(e.g. Italian **"Esodo 30:22"**, German **"2. Mose 30:22"**). Affects every
non-English locale on every verse tap.

## Root Cause (Android)

`buildSyntheticVerse()` never set `localizedBook` on the synthetic verse, so
`verse.reference` always fell back to the English canonical `book` field in
`Verse.kt`: `val reference: String get() = "${localizedBook ?: book} $chapter:$verse"`.

## Fix

The Android flow already carries the localized token through:
- LLM-detected localized book name encoded into the verse URL (`?localizedBook=...`)
- `parseVerseLink()` extracts and passes it to `PendingVerseLink`
- `buildSyntheticVerse()` sets `localizedBook` from the link (with chapter-response backstop)
- `Verse.reference` renders it correctly

## Test Gap Closed (this PR)

`VerseDetailBottomSheet` had no Compose UI test — the localized-header path was
untested and could silently regress.

**Changes:**
1. `VerseDetailBottomSheet.kt` — extracted inner `Column` content into
   `VerseDetailContent()` composable (mirrors the `VersesPanelContent` pattern)
   so Robolectric tests can mount it without `ModalBottomSheet` rendering caveats.
2. `VerseDetailBottomSheetComposeTest.kt` — 5 new tests covering:
   - Top header shows localized book name (Italian script)
   - Top header falls back to English when `localizedBook` is null
   - Top header shows non-Latin script (Russian Cyrillic)
   - Chapter section header shows localized book on `Success` state
   - Chapter section header falls back to English when response `localizedBook` is null

## Acceptance Criteria (all met)

- [x] Tapping a verse shows the localized header (e.g. "Esodo 30:22") — not English
- [x] `Verse.reference` uses `localizedBook` when present, falls back to `book`
- [x] Compose UI test covers the localized header before and after chapter loads
- [x] Non-Latin script locale (Russian) covered by tests
- [x] All existing Android tests pass

## Files Changed

| File | Change |
|---|---|
| `android/app/src/main/kotlin/.../VerseDetailBottomSheet.kt` | Extract `VerseDetailContent` composable for testability |
| `android/app/src/test/kotlin/.../VerseDetailBottomSheetComposeTest.kt` | 5 new Compose UI tests |
| `docs/BACKLOG_STORIES/BITB-040-verse-detail-localized-book-name.md` | This story |
