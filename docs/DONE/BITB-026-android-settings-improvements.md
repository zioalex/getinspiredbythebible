# BITB-026: Android Settings UX Improvements

**Status:** ✅ Done (SettingsScreen.kt already has read-only translation row, clear-history button with confirm dialog, reordered sections; verified 2026-05-24)

## User Story

As an Android user, I want the Settings screen to be clean and purposeful, so that I can find global preferences quickly without redundant controls that already exist in the chat screen.

## Problem

The Settings screen (`SettingsScreen.kt`) currently includes a full Bible translation radio-button list loaded from the backend. An identical picker already exists as a bottom-sheet modal accessible from the translation chip in the Chat screen header (`TranslationPickerBottomSheet.kt`). Both write to the same `TranslationPreferences` DataStore key (`preferred_translation`), making the Settings version purely redundant.

**Issues with the current layout:**

- The translation list can be very long (many translations), making Settings scroll-heavy.
- Users don't know which picker is the "canonical" place — it's confusing to have the same control in two places.
- The in-chat chip is contextually better: users naturally change the Bible version while actively reading/chatting, not in a separate settings screen.
- Current section ordering (Theme → Bible Translation → Support → Contact → About) is not logically grouped.

## Proposed Changes

### 1. Remove Bible Translation section from Settings (primary goal)

- Delete the "Bible Translation" section from `SettingsScreen.kt` (lines 122–154).
- The in-chat translation chip + bottom sheet becomes the sole place to change the Bible version.
- The selection is already persisted via `TranslationPreferences` DataStore — no backend or persistence changes needed.
- Add a **read-only info row** in Settings showing the current translation (e.g. "Bible translation: King James Version") with a caption "Change from the chat screen", so users can still discover where to change it.

### 2. Add "Clear conversation history" action

- Add a destructive action button (with confirmation dialog) to clear local chat history.
- Useful for privacy and for starting fresh.
- Button appears in a new "Data & Privacy" section.

### 3. Improve visual hierarchy and section grouping

Reorder sections to group related items logically:

| New Order | Section | Items |
|---|---|---|
| 1 | **Appearance** | Theme (Light / Dark / System) |
| 2 | **Bible** | Current translation (read-only) + hint |
| 3 | **Data & Privacy** | Clear conversation history |
| 4 | **Support** | Send diagnostic report |
| 5 | **Get in Touch** | Contact form |
| 6 | **About** | Version, Privacy Policy, Terms of Service |

### 4. (Nice-to-have) Daily verse notification opt-in

- Toggle in Settings to enable a daily push notification with a Bible verse.
- Requires Android notification permission request on first enable.
- Can be deferred to a follow-up story.

## Acceptance Criteria

- [ ] Bible translation radio-button list is removed from `SettingsScreen.kt`.
- [ ] A read-only Bible translation row is shown in Settings (displays current translation name + "Change from the chat screen" hint).
- [ ] In-chat translation chip still persists the selection across app restarts (no regression).
- [ ] "Clear conversation history" button added with a confirmation `AlertDialog` before clearing.
- [ ] Settings sections reordered per the table above.
- [ ] All existing unit tests pass: `TranslationPreferencesTest`, `ThemePreferencesTest`, `LanguagePreferencesTest`, `SessionPreferencesTest`.
- [ ] Manual QA: open Settings on a device, verify the translation list is gone, and verify the in-chat chip still works.

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/SettingsScreen.kt` | Remove translation radio list; add read-only translation row; add clear-history button; reorder sections |
| `android/app/src/main/res/values/strings.xml` | Add string resources: clear history button label, confirmation dialog text, read-only translation row label |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt` | Expose `clearHistory()` action if not already present |

## Out of Scope

- Language selector in Settings (language button already exists on the Chat screen and persists via `LanguagePreferences` DataStore — adding it to Settings would recreate the same duplication problem).
- Backend changes (all preferences are client-side).
- iOS app.

## Priority

P2 – Medium (UX polish; no broken functionality, but reduces confusion and clutter)

## Size

S (< 4 hours) — primarily UI deletion + small additions, no new data layer work needed.

## Assignee

android-expert
