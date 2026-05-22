# BITB-027: Android Chat-First Navigation with History Drawer

## User Story

As an Android user, I want the app to open directly into the chat experience (resuming my last conversation) so that I can start interacting immediately, with my chat history one tap away behind a clearly labelled button.

## Problem

Today the Android app lands on `ConversationsScreen` (a list of past conversations) and forces users to tap a row or the FAB before they can start interacting. This adds friction for the primary use case ("ask the Bible something") and buries the actual product behind a list screen.

**Current navigation flow** (`MainActivity.kt:97–153`):

- `splash` → `conversations` (start destination after first launch) → `chat/{conversationId}`
- `ConversationsScreen.kt:60` shows the list + FAB to start a new chat.
- `ChatScreen.kt:74` is the actual interaction surface.

**Issues:**

- New users see a (possibly empty) list instead of the chat input + example prompts.
- Returning users have to re-tap their last conversation every launch.
- The "history" concept is given top-level real estate even though most sessions are continuations or fresh chats.

## Proposed Changes

### 1. Make Chat the start destination, resuming the last conversation

- Change the NavHost start destination (after `splash`) from `conversations` to `chat/{conversationId}`.
- On launch, resolve the conversation to open in this order:
  1. The **most recently updated** conversation (resume).
  2. If none exists, create a new conversation and open it (so the user always lands on a usable chat surface with the example prompts visible).
- Persist the "last opened conversation id" in DataStore so resume is fast and survives process death.

### 2. History accessible via a hamburger drawer

- Add a `ModalNavigationDrawer` to `ChatScreen` opened by a **hamburger icon at the top-left** of the chat top bar.
- Drawer contents:
  - Header: app name / logo.
  - **"+ New chat"** action at the top.
  - Scrollable list of past conversations (reuse the row composable from `ConversationsScreen` where possible).
  - Footer link to **Settings**.
- Tapping a conversation closes the drawer and navigates to `chat/{id}`.
- Swipe-from-left edge gesture also opens the drawer (default `ModalNavigationDrawer` behaviour).

### 3. New chat affordance on the chat top bar

- Add a **"+ New chat"** icon on the **top-right** of the chat top bar (in addition to the drawer entry), matching the muscle memory of other AI chat apps.
- Tapping it creates a new conversation and navigates to it (replacing the current chat in the back stack so Back exits the app rather than returning to an empty chat).

### 4. Retire `ConversationsScreen` from the main flow (keep the composable)

- Remove the `conversations` route from the start of the back stack.
- Keep `ConversationsScreen` reachable only as a "See all conversations" link at the bottom of the drawer (optional follow-up); the drawer list itself should usually be enough.
- Splash screen behaviour is unchanged — it still shows on first launch, then routes to chat.

### 5. Empty / first-launch state

- When the resumed conversation has zero messages (i.e. brand new), show the existing example-prompt suggestions inside `ChatScreen` (already supported). No separate onboarding screen.

## Acceptance Criteria

- [ ] After `splash`, the app navigates directly to `ChatScreen` with the last-used conversation pre-loaded.
- [ ] If no prior conversation exists, a fresh one is created and opened automatically; example prompts are visible.
- [ ] A hamburger icon on the **top-left** of the chat top bar opens a `ModalNavigationDrawer` listing past conversations + "+ New chat" + Settings link.
- [ ] A **"+ New chat"** icon on the **top-right** creates a new conversation and replaces the current entry in the back stack.
- [ ] Pressing the system Back button from the resumed chat exits the app (not navigates to a conversations list).
- [ ] Swiping from the left edge of the chat screen opens the history drawer.
- [ ] The "last opened conversation id" survives app restarts (DataStore-backed).
- [ ] Existing conversation persistence and loading logic is unchanged (no data migration required).
- [ ] No regression in deep-links to `chat/{conversationId}` from notifications or other entry points.
- [ ] Manual QA: fresh install lands on a new chat with example prompts; second launch resumes the last chat; drawer lists all conversations and switches between them.

## Files to Modify

| File | Change |
|---|---|
| `android/app/src/main/kotlin/org/voxquieta/app/MainActivity.kt` | Change NavHost start destination; resolve last/new conversation id at launch |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/ChatScreen.kt` | Wrap content in `ModalNavigationDrawer`; add hamburger and "+ New chat" icons in top bar |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/screens/ConversationsScreen.kt` | Extract conversation-row composable for reuse inside the drawer (no behaviour change) |
| `android/app/src/main/kotlin/org/voxquieta/app/data/preferences/` (new or existing prefs file) | Add `lastConversationId` to DataStore |
| `android/app/src/main/kotlin/org/voxquieta/app/presentation/viewmodels/ChatViewModel.kt` | Expose `openConversation(id)` / `newConversation()` actions used by drawer + top-bar buttons |
| `android/app/src/main/res/values/strings.xml` | Add content descriptions: "Open chat history", "Start new chat" |

## Out of Scope

- iOS app.
- Web frontend.
- Renaming, deleting, or pinning conversations from the drawer (follow-up story).
- Multi-account / multi-profile support.

## Priority

P1 – High (improves time-to-first-interaction for every launch; primary funnel improvement)

## Size

M (~1 day) — navigation refactor + new drawer composable + small DataStore addition; no backend work.

## Assignee

android-expert
