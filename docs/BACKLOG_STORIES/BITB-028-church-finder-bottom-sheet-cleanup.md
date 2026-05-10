# BITB-028: Simplify Church Finder Headers (Banner + Bottom Sheet)

## User Story

As an Android user, I want the church-finder UI surfaces (the in-chat suggestion banner *and* the bottom sheet that opens from it) to have an obvious, single-tap way to dismiss them, so that I'm not distracted by unclear secondary text or low-contrast labels.

## Problem

Two separate church-finder surfaces both expose dismiss/close affordances as small, low-contrast text instead of a clear icon:

1. **Bottom sheet header** (`ChurchFinderBottomSheet.kt:74–242`)
   - Right-side subtitle is small, low-contrast, and not actionable.
   - No explicit close (X) button — users must swipe the sheet down.
2. **In-chat suggestion banner** (`ChurchFinderBanner.kt`)
   - The dismiss control on the right side is rendered as the literal text "Dismiss" inside an `IconButton` at 60% alpha.
   - It's hard to read, easy to miss, and visually inconsistent with other dismiss affordances in the app.
   - The same `ChurchFinderBanner` is used both above the input field (after 3+ interactions) and inline in the message list (after 5+ interactions), so fixing it once fixes both placements.

## Proposed Changes

### 1. Bottom-sheet header — remove subtitle, add X close

- Remove the secondary/subtitle text from the header `Row` in `ChurchFinderBottomSheet.kt`.
- Add an `IconButton` with `Icons.Default.Close`, aligned to the right, that calls the existing `onDismiss` lambda.
- `contentDescription = "Close church finder"` for TalkBack.

### 2. Suggestion banner — replace "Dismiss" text with X icon

- In `ChurchFinderBanner.kt`, replace the `Text` inside the dismiss `IconButton` with `Icon(Icons.Default.Close, …)`.
- Reuse the existing `church_finder_dismiss` string ("Dismiss") as the icon's `contentDescription` — no new string resource required.
- Keep the existing 28dp button size + `onSecondaryContainer` tint so it matches the surrounding card chrome.

### 3. Visual polish

- Bottom-sheet header row uses `Arrangement.SpaceBetween`; banner row keeps existing layout.
- Touch targets remain ≥ 48dp where possible (default `IconButton` size).

## Acceptance Criteria

- [x] Right-side subtitle text removed from the Church Finder bottom sheet header.
- [x] Close (X) `IconButton` added on the right of the bottom sheet header and dismisses the sheet on tap.
- [x] In-chat suggestion banner replaces the "Dismiss" text label with a clear `Icons.Default.Close` icon.
- [x] Banner close icon has a `contentDescription` for accessibility (reusing `church_finder_dismiss`).
- [x] Swipe-to-dismiss continues to work on the bottom sheet (no regression).
- [x] The bottom sheet location input still shows clear guidance via `placeholder` / `supportingText`.
- [x] No changes to search behaviour or `ChurchResultCard` content.
- [x] Manual QA on light + dark themes: bottom sheet header is balanced (title left, X right); banner shows a clear X on the right that dismisses the suggestion.

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChurchFinderBottomSheet.kt` | Remove subtitle; add close `IconButton`; tweak header `Row` to `SpaceBetween` |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChurchFinderBanner.kt` | Swap "Dismiss" text for `Icons.Default.Close` icon |
| `android/app/src/main/res/values/strings.xml` | Add `action_close_church_finder` for the bottom sheet close icon; remove unused `church_finder_modal_subtitle` |

## Out of Scope

- Changes to the per-result card layout (Website / Email buttons on the right of each `ChurchResultCard`) — tracked separately if needed.
- Changes to when the sheet/banner is triggered from `ChatScreen` (after 3+ / 5+ interactions).
- Backend / search API changes.

## Priority

P3 – Low (minor UX polish; functionality is unaffected, but clarity improves)

## Size

XS (< 1 hour) — two composable edits + small string resource changes.

## Assignee

android-expert
