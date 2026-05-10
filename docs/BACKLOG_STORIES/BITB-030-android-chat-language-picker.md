# BITB-030: ChatScreen Top App Bar Cleanup — Language + Bible Version Only

**Status:** 🚧 In Progress
**Priority:** P3
**Size:** S (< 4 hours)
**Created:** 2026-05-10

## User Story

**As an** Android user on the Chat screen,
**I want** the top-right of the screen to expose only the controls I reach
for most often (language, Bible version, and the verses panel when it has
content),
**so that** the top bar stays uncluttered while the less-frequent actions
(clearing the conversation, starting a new one, opening Settings) are
discoverable in the left hamburger drawer alongside the existing
conversation history.

## Background

`ConversationsScreen` already exposes a language picker
(`Icons.Default.Language` `IconButton` + `DropdownMenu(LANGUAGE_OPTIONS)`)
in its `TopAppBar.actions`. The Chat screen previously cluttered the
top-right with: Bible version chip, verses panel, Clear, New chat,
Settings. Settings was already duplicated in the drawer; New chat and
Clear belong with conversation management on the left.

## Acceptance Criteria

- [x] `ChatScreen` `TopAppBar.actions` shows **only**, in order:
      Bible-version `SuggestionChip`, verses panel `IconButton` (when
      `allVerses.isNotEmpty()`), language `IconButton` +
      `DropdownMenu(LANGUAGE_OPTIONS)`.
- [x] Language picker is wired to `viewModel.setLocale(...)` and
      highlights the active locale.
- [x] Drawer adds a "Clear conversation" entry (visible only when the
      current conversation has messages); existing New chat,
      conversations list, Settings entries are preserved.
- [x] Closing the drawer is performed before the corresponding action
      runs, matching the pattern already used for New chat / Settings.
- [x] No new string resources required (all needed
      `R.string.action_*` resources already exist in every locale).
- [x] No changes to ViewModels, navigation, other screens, or shared
      `LANGUAGE_OPTIONS`.
- [x] A pure `chatTopBarPolicy(versesCount, messagesCount)` helper
      encodes the visibility rules and is covered by JVM unit tests
      under `app/src/test/.../screens/ChatTopBarPolicyTest.kt`.

## Implementation Notes

- The top-bar / drawer visibility rules are factored into
  `ChatTopBarPolicy` (`app/src/main/.../screens/ChatTopBarPolicy.kt`) so
  they can be unit-tested without a Compose / instrumented test
  harness — matching the convention used by `LanguageOptionsTest`.
- The verses panel icon stays in the top-right (per product feedback)
  with its existing `BadgedBox` showing the verse count.
- Drawer item ordering: Chat history title → New chat → conversations
  list → divider → Clear conversation (conditional) → Settings.

## Out of Scope

- Reorganising `ConversationsScreen` or any non-Chat top bar.
- Adding new locales / translations.
- Persisting locale changes (already handled by
  `ChatViewModel.setLocale`).

## Validation

- `./gradlew testDebugUnitTest --no-daemon`
- `./gradlew lint`
- `./gradlew compileDebugKotlin`
- Manual: open Chat screen — top-right shows only Bible chip + (verses
  badge when present) + globe icon. Open the drawer — "Clear
  conversation" appears once a message exists; New chat and Settings
  always appear.

