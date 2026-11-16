---
id: BITB-331
status: in-review
priority: P1
size: M
created: 2026-11-16
---

# BITB-331: Changing Language Starts a New Chat (Web + Android)

**Reported by:** owner, 2026-11-16. Spec confirmed by the owner in chat.

## Problem

After changing the UI language, the last chat in the *previous* language is shown.

- **Web:** `ChatIsland.tsx` resumes `listConversations()[0]` on mount regardless of language,
  and `handleLanguageSwitch` stashes `preservedConversation` in sessionStorage so the thread
  survives the switch. `StoredConversation` has no language field.
- **Android:** `ChatViewModel.setLocale` only persists the locale and recreates the Activity;
  the nav destination `chat/<id>` survives recreation, so the old thread stays open. (Cold
  start already opens `chat/new`, BITB-049.)

## Requirements

1. Switching language (language switcher, and the language-suggestion banner) opens a new empty
   chat with a rotated session id. The old chat stays in history.
2. Web reload resumes the latest chat **in the active UI language** only; none -> new chat.
   Store an optional `language` on `StoredConversation` (no IDB version bump); legacy rows with
   no language are never auto-resumed (still reachable from the history sidebar).
3. Android: `setLocale` -> `startNewConversation()` and navigate to `chat/new`. No Room migration.

## Acceptance criteria

- [ ] Web test: switch locale -> empty chat, new session id, old chat still listed.
- [ ] Web test: reload resumes latest same-language chat; ignores other-language and legacy rows.
- [ ] Parametrized across the 11 locales (en, it, de, es, fr, pt, ar, ru, zh, hi, ko).
- [ ] Android ViewModel test: `setLocale` resets conversation state and session.

## Plan

**Web**
- `frontend/src/lib/conversationStore.ts`: add optional `language?: string` to `StoredConversation`;
  `saveFullConversation` (and `saveConversation`) take and persist it; add
  `latestConversationForLanguage(lang)` returning the newest row whose `language === lang`
  (legacy rows without a language are never matched).
- `ChatIsland.tsx`: save with `locale`; on mount resume via that helper instead of `list[0]`;
  remove the `preservedConversation` stash from `handleLanguageSwitch`. A language switch (both the
  `LanguageSwitcher` and the suggestion banner) sets a one-shot `sessionStorage` flag
  `vq_fresh_chat`; mount consumes it, skips resume, and rotates the session id via `resetSessionId()`.
- `LanguageSwitcher.tsx`: set the flag before `router.replace`.
**Android**
- `ChatViewModel.setLocale`: call `startNewConversation()` when the locale actually changes; the
  chat screen navigates to `chat/new` on locale change (call sites: `ChatScreen.kt:313`,
  `:666`, `ConversationsScreen.kt:147`).
**Tests:** frontend vitest parametrized over the 11 locales (switch -> empty chat + new session id;
reload -> same-language resume only; legacy rows ignored); Android `ChatViewModelTest`.
**Verify:** `cd frontend && npx vitest run && npm run lint && npx tsc --noEmit`; Android
`./gradlew testDebugUnitTest` if Gradle can run, else static review and CI.

## Implementation notes

- Web: the language is tagged only when a conversation row is first created; viewing a chat from
  the sidebar neither re-tags it nor re-saves it (autosave skips just-restored messages).
- Web: the one-shot fresh-chat flag decision is held in a ref so React StrictMode's double effect
  run keeps it.
- Android: the `setLocale` persist/apply and the session reset run under `NonCancellable`. There is
  no application-scoped CoroutineScope in the repo; moving this work onto one is a follow-up.
