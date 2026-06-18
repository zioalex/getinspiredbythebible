# BITB-047: One-Tap Copy of the User's Prompt (Web + Android)

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — UX convenience for power users
**Size:** S (< 4 hrs)
**Created:** 2026-06-12
**Source:** Beta tester feedback (Oliver Osthoever, 2026-06-11)

## User Story

**As a** user who wants to reuse my own question elsewhere (e.g. paste it into Perplexity),
**I want** a one-tap button to copy just my prompt text,
**so that** I don't have to manually select it or copy the whole formatted Q&A.

## Problem

> "Man kann einen geschriebenen Prompt nicht kopieren um selbigen z.Bsp in Perplexity einzugeben."

- **Web:** there is no way to copy a user prompt. The existing `ShareMenu` copies the full
  formatted Q&A (`sharePrefix + "Q: " + question + answer`), not the raw question.
- **Android:** a prior story (`copy-user-question-android.md`, ✅ Done) added manual text-selection
  on the user bubble, but deliberately added **no button** and explicitly left **web out of scope**.

This story revisits that decision based on direct tester feedback: provide an explicit one-tap copy
control on both platforms that copies **only the raw question text**.

## Acceptance Criteria

- [ ] A small copy icon appears on/under user message bubbles on **web** and **Android**.
- [ ] Tapping it copies **only** `message.content` (no `sharePrefix`, no `"Q:"` label, no answer).
- [ ] Brief confirmation: web shows a checkmark for ~2 s; Android shows a short Toast.
- [ ] Assistant-message copy/share controls are unchanged.
- [ ] Android manual text-selection on the user bubble (from the prior story) still works.

## Files / Config

| Platform | Location | Change |
|---|---|---|
| Web | `frontend/src/components/ChatMessage.tsx` | add `copied` state + `handleCopyPrompt`; render copy/check button in the `isUser` branch |
| Android | `android/.../presentation/components/ChatMessageItem.kt` | add an `IconButton` (ContentCopy) below the user bubble; copy via `ClipboardManager` + Toast |

## Implementation Notes

- **Web:** import `Copy`, `Check` from `lucide-react` and `useState`. Use
  `navigator.clipboard.writeText(message.content)` with a `document.execCommand("copy")` fallback
  (mirrors `ShareMenu.tsx`).
- **Android:** `ClipboardManager`, `ClipData`, `Toast`, and `Icons.Default.ContentCopy` are already
  imported in `ChatMessageItem.kt`. The string resources `R.string.action_copied` and
  `R.string.action_copy_message` already exist (used by the assistant copy button) — no new strings,
  so Android translation-validation CI stays green.

## Testing

- Web: `frontend/src/test/` — render a user `ChatMessage`, click the copy button, assert
  `navigator.clipboard.writeText` called with the exact question text; assert checkmark appears.
- Android: `ChatMessageItem` Compose test (`*ComposeTest.kt`) — assert the copy button exists on a
  user message and is absent on assistant messages (which use the existing share/copy row).
- Manual: copy on each platform, paste into another app, confirm only the question text.

## Out of Scope

- Changing the assistant `ShareMenu` / full-Q&A copy behaviour.
- Removing the existing Android manual text-selection (kept as a complementary path).

## Related

- `docs/BACKLOG_STORIES/copy-user-question-android.md` (✅ Done) — prior Android-only,
  selection-based approach this story extends with an explicit button + web support.
