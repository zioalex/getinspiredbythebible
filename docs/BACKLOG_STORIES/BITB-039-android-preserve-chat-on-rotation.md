# BITB-039: Android — Keep the Current Chat When the Phone Is Rotated

**Status:** ✅ Done (PR #TODO — 2026-06-06)
**Priority:** P1 (High) — data-loss UX bug on a common interaction
**Size:** S (< 4 hours)
**Created:** 2026-06-04

## User Story

As an Android user mid-conversation, I want rotating my phone to keep me in the
same chat with all my messages, so that I don't lose my conversation just because
the screen orientation changed.

## Problem

Rotating the device during a chat drops the user back into an empty/new chat
instead of preserving the current conversation and its messages.

### Root cause

`MainActivity` has **no `android:configChanges`** attribute
(`android/app/src/main/AndroidManifest.xml:21-25`), so a rotation destroys and
recreates the Activity. The `ChatViewModel` is Activity-scoped (`by viewModels()`
/ `hiltViewModel()`) and therefore *survives* the change — the messages are still
in memory after rotation. The data loss comes from the UI layer:

1. Recreating the Activity restarts the Compose tree, which re-runs
   `LaunchedEffect(conversationId)` in `ChatScreen.kt:141-146`.
2. For an in-progress **new** chat, the nav route is still `chat/new` — it is
   never rewritten to `chat/<realId>` after `ensureConversation()` mints a UUID
   (`ChatViewModel.kt:606-615`).
3. So on rotation the effect hits the `conversationId == "new"` branch and calls
   `startNewConversation()` (`ChatViewModel.kt:650-669`), which **unconditionally
   clears messages, `currentConversationId`, and the session** — the visible
   "reset to a new chat".

## Proposed Changes

### 1. Primary fix — declare config changes on `MainActivity`

**File:** `android/app/src/main/AndroidManifest.xml` (MainActivity, lines 21-25)

Add:

```xml
android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize|keyboardHidden|density"
```

This stops Android from destroying/recreating the Activity on rotation. Jetpack
Compose reads the new `Configuration` and recomposes automatically, so **no
`onConfigurationChanged` override is needed**. The locale-switch flow is
unaffected, because `AppCompatDelegate.setApplicationLocales(...)` recreates the
Activity explicitly regardless of `configChanges` (see the comment at
`MainActivity.kt:97-101`).

### 2. Defense-in-depth — guard the conversation-loading effect

**File:** `android/app/src/main/kotlin/.../screens/ChatScreen.kt` (lines 141-146)

Make the `LaunchedEffect(conversationId)` idempotent so a fresh/`new` route does
not wipe an already-active in-memory conversation:

```kotlin
LaunchedEffect(conversationId) {
    when {
        conversationId == null || conversationId == "new" -> {
            val s = viewModel.uiState.value
            if (s.messages.isEmpty() && s.currentConversationId == null) {
                viewModel.startNewConversation()
            }
        }
        else -> viewModel.loadConversation(conversationId)
    }
}
```

This also protects the conversation across the locale-change recreation path and
process-death restoration — not just rotation.

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/AndroidManifest.xml` | Add `android:configChanges="orientation\|screenSize\|screenLayout\|smallestScreenSize\|keyboardHidden\|density"` to `MainActivity` |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/ChatScreen.kt` | Guard the `LaunchedEffect(conversationId)` so a `new` route only starts a new conversation when none is active |
| `android/app/src/test/kotlin/...` (or `composeTest`) | Test the guard logic: a `new` route with an active in-memory conversation does not call `startNewConversation()` |

## Acceptance Criteria

- [ ] Start a new chat, send a message, then rotate the device → the same messages
      and conversation remain visible (no reset to an empty chat).
- [ ] Open an existing saved conversation, then rotate → still on the same
      conversation.
- [ ] Rotating during an in-flight (loading) response does not start a new chat.
- [ ] Locale switching from Settings still works (still recreates the Activity and
      applies the new language).
- [ ] Existing Android unit tests pass; the guard logic is covered by a test.

## Out of Scope

- Locking the app to a single orientation.
- Persisting transient draft input text across process death beyond the existing
  `rememberSaveable` for the input field (`ChatScreen.kt:116`).
- Rewriting the navigation graph or the `resume`-route start-destination logic
  (`MainActivity.kt:125-155`).

## Notes

The primary fix (`configChanges`) directly satisfies the reported "rotation
resets the chat" symptom with a one-line manifest change and is the standard
recommended approach for Jetpack Compose apps. The `LaunchedEffect` guard is
defense-in-depth that also covers the locale-recreation and process-death paths.

## Assignee

android-expert
