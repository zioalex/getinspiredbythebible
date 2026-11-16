---
id: BITB-331
status: todo
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
