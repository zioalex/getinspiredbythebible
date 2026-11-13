# BITB-049: Always Start with a Fresh Chat on App Launch (Android)

**Status:** ✅ Done
**Priority:** P2 (Medium) — startup behaviour preference
**Size:** S (< 1 hr)
**Created:** 2026-06-12
**Source:** Beta tester feedback (Oliver Osthoever, 2026-06-12)

## User Story

**As an** Android user,
**I want** the app to open a new, empty chat every time I start it,
**so that** I begin fresh instead of landing back in my last conversation.

## Problem

> "Beim Start der App beginnt diese immer mit dem letzten Chat und man muss bewusst einen neuen
> Chat anfangen. Ich finde es besser wenn die App automatisch bei jedem Neustart einen neuen Chat
> beginnen würde."

On launch, `MainActivity.kt`'s `resume` nav entry calls `resolveResumeConversationId()` and
navigates to `chat/{lastId}` when a prior conversation exists, restoring the last chat. The tester
prefers a blank slate; history is already reachable via the conversation drawer.

## Approach

Always navigate the `resume` entry to `chat/new`. Keep `LastConversationPreferences` and
`resolveResumeConversationId()` in place for a possible future "resume last chat" setting.

## Acceptance Criteria

- [ ] Opening the app always shows a blank chat (welcome state).
- [ ] Past conversations remain accessible via the `ModalNavigationDrawer` and load correctly.
- [ ] The "New Chat" button continues to work.
- [ ] No dead code warnings (drop the now-unused `resumeViewModel` from the `resume` entry).

## Files / Config

| Item | Location | Change |
|---|---|---|
| Nav graph | `android/app/src/main/kotlin/org/voxquieta/app/MainActivity.kt` | in `composable("resume")`, set `target = "chat/new"`; remove the unused `resolveResumeConversationId()` call + `resumeViewModel` |

## Implementation Notes

```kotlin
composable("resume") {
    LaunchedEffect(Unit) {
        navController.navigate("chat/new") {
            popUpTo("resume") { inclusive = true }
        }
    }
}
```

`ChatViewModel.resolveResumeConversationId()` and `LastConversationPreferences` are retained
(unused on startup) so a future opt-in "resume last chat" preference can re-enable resume cheaply.

## Testing

- ViewModel/nav test: assert the resume route resolves to `chat/new` regardless of stored last id.
- Manual: have an active chat → kill app → reopen → blank chat; drawer still lists/loads history.

## Out of Scope

- A user-facing "resume last chat on startup" toggle (possible follow-up).
- Deleting `LastConversationPreferences`.
