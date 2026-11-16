---
id: BITB-337
status: todo
priority: P3
size: S
created: 2026-11-16
---

# BITB-337: Persist setLocale Work on an Application Scope

**Follow-up of:** BITB-331 / BITB-334 (verifier findings, 2026-11-16).

## Problem

ChatViewModel.setLocale persists the language and applies it inside viewModelScope. Navigating to chat/new pops the old back-stack entry and may clear its ViewModel before the DataStore write finishes. BITB-331 mitigated it with NonCancellable; no application-scoped CoroutineScope exists in the repo yet.

## Acceptance criteria

- [ ] An injected application scope runs the locale persist/apply and session reset.
- [ ] ChatViewModel tests updated; Android CI green.
