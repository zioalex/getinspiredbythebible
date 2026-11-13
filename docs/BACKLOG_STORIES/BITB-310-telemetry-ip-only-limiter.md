# BITB-310: Telemetry Endpoints Can Spend Chat Session Budget via a Stray `session_id`

**Status:** 🎯 Todo
**Priority:** P2
**Size:** XS
**Created:** 2026-11-13
**Prompted by:** BITB-298 verification (finding 3).

## Problem

`POST /api/v1/client-errors` (`api/main.py:490`) and `POST /api/v1/client-events`
(`api/main.py:567`) are guarded by `require_rate_limit` (`api/utils/security.py:186`), which
reads `session_id` from any POST body and charges the request against that **chat session's
lifetime cap**.

- `ClientErrorReport` (`api/main.py:472`) does not forbid extra fields, so a body such as
  `{"type": "x", "session_id": "<chat session>"}` passes validation and spends a chat turn.
- `ClientEvent` forbids extra fields (422), but `require_rate_limit` runs as a dependency
  *before* body validation, so the session is charged before the 422 is returned.

No shipped client sends `session_id` to these endpoints today (`clientErrorReporter.ts`,
`turnstile.tsx` checked on 2026-11-13), so this is hardening, not a live bug. BITB-298 left
these routes on `require_rate_limit` because their models declare no `session_id`.

## Requirements

1. Switch both routes to `require_ip_rate_limit("telemetry", settings.rate_limit_telemetry_per_minute)`
   (new setting, default 60, in `api/config.py` and `scripts/env-manifest.yaml`).
2. Add `model_config = ConfigDict(extra="forbid")` to `ClientErrorReport` unless a shipped
   client sends extra fields (check web + Android first).
3. Regression test: N telemetry posts carrying a chat `session_id` leave that session's chat
   budget untouched; the `(N+1)`th post from one IP over the telemetry limit gets 429.

## Acceptance criteria

- [ ] Neither telemetry route can consume chat session budget, whatever the body contains
- [ ] Telemetry has its own IP bucket (scope `telemetry`) and setting
- [ ] Regression test as above

## Related

BITB-298 (introduced `require_ip_rate_limit`).
