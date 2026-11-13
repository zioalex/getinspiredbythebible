---
id: BITB-001
status: done
priority: P0
size: S
rank: 80
prs: [171]
---

# BITB-001: Fix Turnstile 403 Errors on Example Sentences

**Status note:** (PR #171 merged, deployed to production 2026-02-23 12:26 UTC)

**Completed:** 2026-02-23

**As a** new user visiting the app for the first time,
**I want** to click example sentences and get immediate responses,
**so that** I can quickly understand what the app does without frustration.

**Acceptance Criteria:**

- [x] Example sentence buttons are disabled until Turnstile is ready
- [x] Users see "Preparing secure connection..." message while waiting
- [x] No 403 errors when clicking examples after page load
- [x] Unit tests verify buttons are disabled when `turnstileEnabled && !turnstileReady`
- [x] E2E tests verify suggested prompts are present and clickable

**Tech Constraints:**

- Must work with existing Cloudflare Turnstile integration
- Frontend-only fix (no backend changes needed)

**Out of Scope:**

- Changing Turnstile provider or configuration
- Adding retry logic for failed Turnstile challenges

**PR:** #171 (`fix/turnstile-ready-check`) - Merged
**Tracking Doc:** `docs/DONE/PR171-turnstile-ready-fix.md`
