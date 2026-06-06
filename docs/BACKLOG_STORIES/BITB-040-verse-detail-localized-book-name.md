# BITB-040: Verse-Detail Header Shows English Book Name Instead of Localized

**Status:** ✅ Done (PR #694 — 2026-06-06)
**Priority:** P1 (High) — pervasive localization defect affecting every non-English locale on every verse tap
**Size:** S (< 4 hours)
**Created:** 2026-06-04

## User Story

As a non-English user, when I tap a Bible verse reference and the verse-detail
bottom sheet opens, I want the header to show the reference using my translation's
book name (e.g. Italian *"Esodo 30:22"*), so that the reference matches the
language I'm reading in and the app feels trustworthy and consistent.

## Problem

Tapping a verse opens the bottom sheet with the header showing the **English**
book name (e.g. **"Exodus 30:22"**) instead of the translation's localized name
(e.g. Italian **"Esodo 30:22"**, German **"2. Mose 30:22"**). **Reported across
multiple non-English languages** — it is not Italian-specific, and it happens
**even when the verse text loads correctly**. (Originally surfaced alongside the
Italian load failure in BITB-041, but it is an independent, general defect.)

### Root cause (Android — affects all non-English locales)

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

Because `localizedBook` is never populated on the synthetic verse, the top header
(`VerseDetailBottomSheet.kt:106`) shows the English book name for **every**
non-English locale, regardless of whether the chapter fetch succeeds. (The loaded-
chapter element at `:184` does use `response.localizedBook`, but the sheet's own
header at `:106` is driven by the synthetic verse and is never corrected — so the
defect persists even on a successful load.) This is independent of the Italian
load failure in **BITB-041**; that bug just made it more visible because the header
never gets a chance to update.

### The book name is already known locally — no fetch needed

The LLM writes the reference in the user's language (e.g. "Esodo 30:22") and the
verse-link regex matches that localized token; it is then normalized to the English
canonical for `link.book`. The **original localized token is discarded**. Carrying
it through the link lets the header localize **immediately**, without depending on
the chapter response at all.

### Backend already returns localized names

`get_verse` / `get_chapter` call `get_localized_book_name(name, translation)`
(`api/routes/scripture.py:93-167`), mapping each translation to its book map
(`ita1927 → ENGLISH_TO_ITALIAN_BOOKS`, `schlachter → ENGLISH_TO_GERMAN_BOOKS`, …)
with an English fallback on a miss (`api/utils/language.py:1212-1238`). Verify the
maps are complete for all supported translations (see AC) — a missing key would be
a second, per-language source of the same English fallback.

## Proposed Changes

1. **Carry the localized book name through the link (Android) — primary fix.**
   Retain the originally-matched localized book token on `PendingVerseLink` and set
   it as `localizedBook` on the synthetic verse in `buildSyntheticVerse()`
   (`ChatMessageItem.kt:753-770`), so the header (`VerseDetailBottomSheet.kt:106`)
   is localized **immediately and independently of the chapter fetch**.
2. **Backstop from the response.** When the chapter loads, also copy
   `response.localizedBook` into the synthetic verse so the header is consistent
   with the `:184` element.
3. **Verify the backend book maps.** Confirm every supported translation's
   English→localized map is complete and wired in `get_localized_book_name`'s
   `book_map` (fix any gaps found).

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/kotlin/.../components/ChatMessageItem.kt` | Retain the localized book token on `PendingVerseLink`; set `localizedBook` on the synthetic verse from the link (and backstop from the chapter response) |
| `android/app/src/main/kotlin/.../components/VerseDetailBottomSheet.kt` | Ensure the header (line 106) uses the localized reference consistently with line 184 |
| `api/utils/language.py` | Verify/complete every translation's English→localized book map and `book_map` wiring (fix any gaps) |

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

- [ ] Tapping a verse shows the localized header for the selected translation
      (e.g. *"Esodo 30:22"*, *"2. Mose 30:22"*) — not the English book name —
      **before and after** the chapter loads, and **even if the fetch fails**.
- [ ] Verified across several non-English locales (Latin-script and at least one
      non-Latin-script, e.g. Russian/Korean) — no regression in English.
- [ ] `get_localized_book_name` is covered by a real (un-mocked) unit test for all
      supported translations (every canonical book round-trips).
- [ ] A Compose UI test covers the localized header in the verse-detail sheet.
- [ ] All existing Android and backend tests pass.

## Out of Scope

- The "verse never loads / infinite spinner" failure and its monitoring — tracked
  in **BITB-041**. (Independent bug; this story fixes the header for all locales,
  including the cases where the fetch succeeds.)
- Changing scripture retrieval or translation selection.

## Related

- **BITB-041** — verse-detail load resilience + monitoring (surfaced this bug, but
  the two are independent — BITB-040 also occurs when loading works)
- BITB-034 — Android Compose UI test tier (use it for the new header test)

## Assignee

android-expert
