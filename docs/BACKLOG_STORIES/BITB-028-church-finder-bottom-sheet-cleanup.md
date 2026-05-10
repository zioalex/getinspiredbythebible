# BITB-028: Simplify Church Finder Bottom Sheet Header

## User Story

As an Android user opening the Church Finder bottom sheet, I want a clean header with an obvious way to dismiss it, so that I'm not distracted by unclear secondary text and I can close the panel with a single tap.

## Problem

The Church Finder `ModalBottomSheet` (`ChurchFinderBottomSheet.kt:74–242`) currently shows a header with:

- A location icon
- Title: **"Find a Church"**
- A subtitle / supporting line on the right side that is small, low-contrast, and not actionable
- No explicit close (X) button — users must swipe the sheet down to dismiss it

**Issues:**

- The right-side subtitle is hard to read and adds visual noise without conveying useful information.
- Swipe-to-dismiss is not discoverable (especially for less technical users) and is not keyboard- / accessibility-friendly.
- The hint copy duplicates information already conveyed by the input field's `placeholder` and `supportingText`.

## Proposed Changes

### 1. Drop the unclear right-side subtitle from the header

- Remove the secondary/subtitle text shown to the right of the title in the header `Row` (`ChurchFinderBottomSheet.kt:88–109`).
- Keep the location icon + title **"Find a Church"** as the only header content on the left.

### 2. Add an explicit close (X) button on the right of the header

- Add an `IconButton` with an `Icons.Default.Close` icon, aligned to the **right** of the header row.
- Tapping it dismisses the bottom sheet (calls the same `onDismiss` lambda that `ModalBottomSheet` already uses).
- `contentDescription = "Close church finder"` for TalkBack.

### 3. Migrate any still-useful hint copy into the input field

- If any of the removed subtitle text was actually useful (e.g. "Enter a city or postcode"), move it into the `OutlinedTextField`'s `placeholder` or `supportingText` (`ChurchFinderBottomSheet.kt:113–137`) — do not reintroduce it in the header.

### 4. Visual polish

- Header row uses `Arrangement.SpaceBetween` so the title stays left and the close button stays right.
- Vertical alignment: `Alignment.CenterVertically`.
- Touch target for the close icon: at least 48dp (default `IconButton` size is fine).

## Acceptance Criteria

- [ ] The right-side subtitle text is removed from the Church Finder bottom sheet header.
- [ ] A close (X) `IconButton` is shown on the right of the header and dismisses the sheet on tap.
- [ ] The close button has a `contentDescription` for accessibility.
- [ ] Swipe-to-dismiss continues to work (no regression to existing `ModalBottomSheet` behaviour).
- [ ] The location input field still shows clear guidance via `placeholder` / `supportingText`.
- [ ] No changes to search behaviour, results rendering, or `ChurchResultCard` content.
- [ ] Manual QA on light + dark themes: header is balanced (title left, X right), close button dismisses the sheet.

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChurchFinderBottomSheet.kt` | Remove subtitle; add close `IconButton`; tweak header `Row` to `SpaceBetween` |
| `android/app/src/main/res/values/strings.xml` | Add `church_finder_close_cd` string for the close button content description; remove now-unused subtitle string if any |

## Out of Scope

- Changes to the per-result card layout (Website / Email buttons on the right of each `ChurchResultCard`) — tracked separately if needed.
- Changes to when the sheet is triggered from `ChatScreen` (after 3+ / 5+ interactions).
- Backend / search API changes.

## Priority

P3 – Low (minor UX polish; functionality is unaffected, but clarity improves)

## Size

XS (< 1 hour) — single composable edit + one string resource.

## Assignee

android-expert
