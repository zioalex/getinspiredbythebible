# BITB-024: Fix & Complete the 10-Interaction Session Limit

**Priority:** P1 (High)
**Status:** 🎯 Todo → ✅ Done
**Size:** S (2–4 hours)
**Created:** 2026-03-07

---

## Background

A 10-message-per-session soft limit was partially implemented in BITB-023 (PR #250) to encourage
users to take breaks and reflect on scripture. The backend correctly enforces it (HTTP 429 with
`session_lifetime_limit` error code). The frontend catches the error and shows a "Start New
Session" button. However, the feature shipped with a **critical bug** and a UX gap.

---

## Critical Bug Fixed

**`handleNewSession()` did NOT rotate the `sessionId`.**

The `sessionId` was declared as `const [sessionId] = useState(...)` — immutable for the
component lifetime. Clicking "Start New Session" cleared the UI, but the same `sessionId` was
still sent in subsequent requests. The backend rate limiter still had this session at 10
requests and immediately blocked the very next message with another 429. Users were permanently
stuck until hard-reloading the page.

---

## User Story

**As a** user who has had 10 Bible chat interactions,
**I want** to be able to start a fresh session by clicking one button,
**so that** I can continue seeking spiritual guidance without needing to hard-reload the page.

---

## Changes Made

### frontend/src/lib/api.ts

- Added `resetSessionId()` — generates new ID, persists to localStorage, returns it

### frontend/src/app/[locale]/page.tsx

- `sessionId` changed from immutable to mutable state (`const [sessionId, setSessionId]`)
- `handleNewSession()` now calls `resetSessionId()` and `setSessionId(newId)` first
- Session limit chat bubble uses `tChat("sessionLimitMessage")` instead of `error.message`

### frontend/messages/*.json (all 7 locales)

- Added `sessionLimitMessage` key to `Chat` namespace in en, de, it, es, fr, pt, ar

### api/utils/security.py

- Removed hardcoded English prose from 429 response body
- Response now returns only the machine-readable `"error": "session_lifetime_limit"`

---

## Acceptance Criteria

- [x] User sends 10 messages → sees session limit message (in their locale) + "Start New Session" button
- [x] User clicks "Start New Session" → messages cleared, input re-enabled, new sessionId generated
- [x] First message after reset succeeds (HTTP 200, not 429) — critical regression test
- [x] localStorage updated to new ID after reset
- [x] Message displayed in user locale (from i18n, not backend)
- [x] Backend 429 no longer embeds English prose
- [x] All tests pass, pre-commit green

---

## Out of Scope

- Changing the limit from 10 (config change only)
- Hard paywall / account creation gate (soft encouragement by design)
- Android app session limit (separate story)
- Preventing repeated session rotations (soft limit, by design)
