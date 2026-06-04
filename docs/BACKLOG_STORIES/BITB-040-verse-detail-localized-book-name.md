# BITB-040: Verse-Detail Header Shows English Book Name Instead of Localized

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — localization/trust defect, verse still readable once loaded
**Size:** S (< 4 hours)
**Created:** 2026-06-04

## User Story

As a non-English user, when I tap a Bible verse reference and the verse-detail
bottom sheet opens, I want the header to show the reference using my translation's
book name (e.g. Italian *"Esodo 30:22"*), so that the reference matches the
language I'm reading in and the app feels trustworthy and consistent.

## Problem

Tapping a verse in an Italian chat opens the bottom sheet with the header
**"Exodus 30:22"** (English) instead of **"Esodo 30:22"**. Reported as happening
in **Italian** while **English and German work**.

### Root cause (Android)

When a verse link is tapped, `buildSyntheticVerse()` builds a `Verse` for the
sheet but never sets `localizedBook`
(`android/app/src/main/kotlin/.../components/ChatMessageItem.kt:753-770`):

```kotlin
return Verse(
    book = link.book,          // English canonical, e.g. "Exodus"
    chapter = link.chapter,
    verse = link.verseNumber,
    text = actualText,
    translation = translation,
    // localizedBook is never set → defaults to null
)
```

The header renders `verse.reference`
(`VerseDetailBottomSheet.kt:106`), and the reference getter falls back to the
English `book` when `localizedBook` is null (`domain/models/Verse.kt:16`):

```kotlin
val reference: String get() = "${localizedBook ?: book} $chapter:$verse"
```

So the header is English until — **and only if** — the chapter fetch succeeds and
the localized name becomes available (`VerseDetailBottomSheet.kt:184` uses
`response.localizedBook`). When the Italian chapter fetch fails or hangs (see
**BITB-041**), the header stays English. This is why the English book name and the
"never loads" symptom appear together in Italian.

### Backend is mostly correct

The backend already returns a `localized_book` field. `get_verse` /
`get_chapter` call `get_localized_book_name(name, translation)`
(`api/routes/scripture.py:93-167`), which maps `ita1927 → ENGLISH_TO_ITALIAN_BOOKS`
and falls back to English on a miss (`api/utils/language.py:1212-1238`). The
Italian map should contain "Exodus"→"Esodo"; this must be verified (see AC) since
a missing/odd key would also explain the English fallback.

## Proposed Changes

1. **Carry the localized book name into the sheet header (Android).**
   Populate `localizedBook` on the synthetic verse from the loaded chapter
   response (`ChapterResponseDto.localizedBook`) so the top header
   (`VerseDetailBottomSheet.kt:106`) shows the localized reference, consistent
   with the `:184` path. While the chapter is still loading, prefer the localized
   name already known from the tapped link if available, rather than the English
   canonical.
2. **Verify the Italian book map (backend).** Confirm `ENGLISH_TO_ITALIAN_BOOKS`
   contains every canonical book (incl. "Exodus"→"Esodo") and that `ita1927` is
   wired in `get_localized_book_name`'s `book_map`.

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/kotlin/.../components/ChatMessageItem.kt` | Set `localizedBook` on the synthetic verse from the chapter response (and/or the link) |
| `android/app/src/main/kotlin/.../components/VerseDetailBottomSheet.kt` | Ensure the header (line 106) uses the localized reference consistently with line 184 |
| `api/utils/language.py` | Verify/complete `ENGLISH_TO_ITALIAN_BOOKS` and `book_map` wiring (fix if a gap is found) |

## Test Gaps to Close

The existing suite let this ship because it **over-mocks** localization:

- Backend `test_multilanguage_routes.py` **mocks** `get_localized_book_name`, so the
  real function is never validated; `test_api.py` integration coverage is **skipped**.
- No Compose UI test exists for `VerseDetailBottomSheet` (header rendering untested).

Add:

- [ ] Backend unit test for the **real** `get_localized_book_name(...)` across
      translations (incl. `ita1927 → Esodo`, every canonical book round-trips).
- [ ] Android Compose UI test (in the `composeTest` tier from BITB-034) asserting
      the verse-detail header renders the **localized** reference for a non-English
      translation, both before and after the chapter loads.

## Acceptance Criteria

- [ ] Tapping a verse in Italian shows the localized header (e.g. *"Esodo 30:22"*),
      not the English book name — before and after the chapter loads.
- [ ] Same verified for German and another non-Latin-script locale (no regression).
- [ ] `get_localized_book_name` is covered by a real (un-mocked) unit test for all
      supported translations.
- [ ] A Compose UI test covers the localized header in the verse-detail sheet.
- [ ] All existing Android and backend tests pass.

## Out of Scope

- The "verse never loads / infinite spinner" failure and its monitoring — tracked
  in **BITB-041** (shared root cause; do that one for the loading/resilience fix).
- Changing scripture retrieval or translation selection.

## Related

- **BITB-041** — verse-detail load resilience + monitoring (shared Italian root cause)
- BITB-034 — Android Compose UI test tier (use it for the new header test)

## Assignee

android-expert
