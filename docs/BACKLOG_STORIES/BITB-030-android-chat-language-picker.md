# BITB-030: Add Language Picker to Android ChatScreen

**Status:** 🚧 In Progress
**Priority:** P3
**Size:** XS (< 1 hour)
**Created:** 2026-05-10

## User Story

**As an** Android user chatting with the AI on the chat screen,
**I want** a language selection button in the top app bar of the chat screen,
**so that** I can switch the UI language without first navigating back to the
conversations screen.

## Background

`ConversationsScreen` already exposes a language picker
(`Icons.Default.Language` `IconButton` + `DropdownMenu` driven by
`LANGUAGE_OPTIONS`) in its `TopAppBar.actions`. The chat screen
(`ChatScreen.kt`), where users spend most of their time, does not. This
forces an extra navigation step to change the UI language mid-conversation.

## Acceptance Criteria

- [ ] `ChatScreen`'s `TopAppBar.actions` shows a language icon
      (`Icons.Default.Language`) with `contentDescription =
      stringResource(R.string.action_select_language)`.
- [ ] Tapping the icon opens a `DropdownMenu` listing all entries from
      `LANGUAGE_OPTIONS`.
- [ ] The currently selected locale is highlighted using
      `MaterialTheme.colorScheme.primary` (matches the
      `ConversationsScreen` pattern).
- [ ] Selecting an entry calls `viewModel.setLocale(code)` on the existing
      `ChatViewModel` and dismisses the menu.
- [ ] No new string resources required (existing
      `R.string.action_select_language` is already translated in all 11
      locale resource folders).
- [ ] No changes to other screens, ViewModels, navigation, or string
      resources.
- [ ] Existing chat top-bar actions (verses panel, clear, new chat,
      settings) are unchanged in behaviour and ordering.

## Implementation Notes

- Reuse the exact `Box { IconButton + DropdownMenu }` block from
  `ConversationsScreen.kt` (~lines 119–153). `ChatScreen` already
  injects `viewModel: ChatViewModel`, which exposes `uiState.currentLocale`
  and `setLocale(...)`.
- Add a `var showLanguageMenu by remember { mutableStateOf(false) }` near
  the other `var show…` state declarations.
- Add imports for `Icons.Default.Language`, `DropdownMenu`,
  `DropdownMenuItem` (`Box`, `Row`, `Alignment`, `remember`,
  `mutableStateOf` already imported).

## Out of Scope

- Reorganising the rest of the top app bar.
- Adding new locales or translations.
- Persisting locale changes (already handled by `ChatViewModel.setLocale`).

## Validation

- `./gradlew testDebugUnitTest --no-daemon`
- `./gradlew lint`
- `./gradlew compileDebugKotlin`
- Manual: open chat screen, tap globe icon, switch locale, confirm UI
  strings update and selection highlight reflects the new locale.
