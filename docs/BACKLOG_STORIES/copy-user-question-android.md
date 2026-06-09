# User Story: Copy the User's Question in the Android App

**As a** user reading my conversation in the Android app
**I want** to select and copy the text of the question I asked
**So that** I can reuse, save, or share my own wording — not just the AI's response

**Priority:** P2
**Status:** ✅ Done
**Size:** S
**Created:** 2026-06-09

---

## Problem Statement

**Current Behavior:**

- In the chat screen, the AI **response** can be copied manually — its text is
  rendered with `MarkdownText(..., isTextSelectable = true)`, so a long-press
  brings up the Android text-selection toolbar with a Copy action.
- The **user's own question** is rendered as a plain `Text` composable with no
  selection support, so its text cannot be selected or copied at all.

**Root Cause:** In
`android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt`,
the bubble-content `when` block wraps the streaming assistant branch in a
`SelectionContainer` and renders the finished assistant branch with
`isTextSelectable = true`, but the user-message branch (case `(d)`) renders a bare
`Text(...)` with no selection wrapper.

---

## Functional Requirements

- [x] Long-pressing a user question bubble enters text-selection mode
- [x] The standard Android selection toolbar (Copy / Select all) is available on the question text
- [x] Copied text matches the question content exactly
- [x] Assistant-response selection & copy behavior is unchanged
- [x] No new copy button/icon is added — copy is via manual text selection, matching the response

---

## Non-Functional Requirements

- **UX:** Selection behaves identically to the assistant response (same gestures, same toolbar)
- **Theming:** Works correctly in both light and dark themes (selection handles use system colors)
- **Performance:** No measurable impact — change is a pure composable wrapper with no added logic

---

## Acceptance Criteria

**Code Changes:**

- [x] Wrap the user-message `Text` (case `(d)`) in `ChatMessageItem.kt` with a `SelectionContainer`
- [x] No new imports required (`SelectionContainer` is already used by the streaming branch)
- [x] No changes to data models, ViewModel, or layouts (questions already carry full `content`)

**Testing:**

- [x] Builds/compiles cleanly (`./gradlew :app:compileDebugKotlin`)
- [ ] Manual: send a message → long-press the user question → confirm selection
      handles + Copy toolbar appear and the copied text matches the question
- [ ] Manual: confirm the assistant response remains selectable/copyable as before

**Documentation:**

- [x] This user story added to `docs/BACKLOG_STORIES/`

---

## Out of Scope

- Adding a dedicated copy button/icon to the question bubble (manual selection was the requested behavior)
- Changing the existing Share button or the assistant-response copy/selection behavior
- Equivalent change on the web frontend (this story targets the Android app only)

---

## Implementation Notes

**Files Modified:**

- `android/app/src/main/kotlin/org/voxquieta/app/presentation/components/ChatMessageItem.kt`
  — wrapped the user-message `Text` (case `(d)`) in `SelectionContainer`.

**Branch:** `claude/android-copy-question-acz55e`

**Verification Steps:**

1. From `android/`, run `./gradlew :app:compileDebugKotlin` to confirm it compiles.
2. On an emulator/device, send a message, then long-press the user question bubble
   and confirm the selection toolbar appears and Copy works.
3. Confirm the assistant response is still selectable/copyable.

---

## Risk Assessment

**Risk Level:** Low
**Rationale:** Single-branch composable wrapper with no logic change; mirrors a
pattern already used elsewhere in the same file.
**Mitigation:** Manual verification of both question and response selection in light/dark themes.
