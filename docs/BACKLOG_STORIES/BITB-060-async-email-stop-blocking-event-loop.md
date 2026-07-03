# BITB-060: Stop the Email Service from Freezing the Event Loop

**Status:** 📋 Backlog
**Priority:** P0 (Critical) — 2026-07 adversarial audit S1 (CRITICAL); one feedback/contact submission can stall every concurrent chat on a replica
**Size:** S (core fix is ~3 lines; guard rail + test add ~half a day)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — S1

## User Story

As a user mid-conversation, I want my chat stream to keep flowing even while another user submits
the contact form, so that background side-channels (email notifications) can never freeze the
product's core interaction.

## Problem / Motivation

`api/utils/email_service.py:73` uses the **synchronous** `httpx.Client(timeout=10.0)`, and it is
called directly — no `await`, no thread offload — from `async def` routes:

- `api/routes/feedback.py:72` (feedback notification)
- `api/routes/feedback.py:145` (contact notification)
- `api/routes/admin.py:47` (weekly report)

While SMTP2GO is slow (up to the 10s timeout), the **entire event loop** on that replica is frozen:
every in-flight SSE chat stream stalls, and health probes can time out — re-creating the
readiness-flap failure mode that BITB-057 just fixed, via a different door.

## Acceptance Criteria

- [ ] `email_service` uses `httpx.AsyncClient` (or wraps the sync call in
      `anyio.to_thread.run_sync`) so no email send ever blocks the event loop.
- [ ] All three call sites await the async path; failure behavior (log + continue) is unchanged.
- [ ] A regression guard prevents recurrence: lint rule or unit test asserting no `httpx.Client(`
      usage is reachable from `api/routes/` / async service code (the audit's suggested grep-based
      check is acceptable).
- [ ] A test simulates a slow SMTP2GO response and asserts a concurrent request completes without
      added latency (event loop not blocked).
- [ ] `utils/email_service.py` gets the dedicated unit tests it currently lacks (audit D4 overlap).
