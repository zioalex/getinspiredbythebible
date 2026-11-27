---
id: BITB-310
status: in-review
priority: P2
kind: nfr
milestone: R1
size: XS
created: 2026-11-13
prs: [1320]
follow_ups: [BITB-345, BITB-346, BITB-347]
---

# BITB-310: Telemetry Endpoints Can Spend Chat Session Budget via a Stray `session_id`

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
`turnstile.tsx` checked on 2026-11-13, re-checked across their full history 2026-11-19), so
the *session lifetime* drain needs someone to send a session id deliberately. BITB-298 left
these routes on `require_rate_limit` because their models declare no `session_id`.

**Correction (2026-11-19, from the build verification).** Calling this "hardening, not a live
bug" was too generous. Even with no `session_id` in the body, `require_rate_limit` charged
every telemetry POST against the **chat per-IP bucket** (`RATE_LIMIT_REQUESTS_PER_MINUTE`,
default 20). A page that threw errors (the reporter sends up to 10 per page load) plus
read-aloud events could therefore 429 the user's own chat with no stray field involved — a
real, user-feelable fault, which is why this shipped as `fix:` rather than `chore:`.
The replacement bucket is deliberately a *loosening*: 60/min of its own, shared by both routes
and by web + Android arriving behind one NAT/CGNAT address (Cloudflare `X-Forwarded-For`
resolution means most traffic presents a real per-user IP).

## Requirements

1. Switch both routes to `require_ip_rate_limit("telemetry", settings.rate_limit_telemetry_per_minute)`
   (new setting, default 60, in `api/config.py` and `scripts/env-manifest.yaml`).
2. Add `model_config = ConfigDict(extra="forbid")` to `ClientErrorReport` unless a shipped
   client sends extra fields (check web + Android first).
3. Regression test: N telemetry posts carrying a chat `session_id` leave that session's chat
   budget untouched; the `(N+1)`th post from one IP over the telemetry limit gets 429.

## Acceptance criteria

- [x] Neither telemetry route can consume chat session budget, whatever the body contains
- [x] Telemetry has its own IP bucket (scope `telemetry`) and setting
- [x] Regression test as above

Verified independently on 2026-11-19 (PR #1320): all four new tests fail on `origin/main`, and
the session-budget test records the chat session being charged **6 times** there (3 ×
`/client-errors` + 3 × `/client-events`, the latter charged before its own 422) — the defect in
evidence. Full backend suite: 16568 passed, with only the three failures that also fail on
`origin/main` in the same sandbox (two `api.getbible.net` 403s through the agent proxy and
`test_db_backup_restore_script.py::TestDestructiveGuards::test_restore_new_server_requires_its_arguments`).

## Follow-ups

Filed with this PR, per *Backlog Hygiene*:

- **BITB-345** — scoped limiter buckets are only ever tested on the `memory` backend, where
  isolation holds by construction; the shared `rate_limit_hits` table is untested. This PR
  pins the `telemetry:<ip>` key shape, which is the narrow half of that gap.
- **BITB-346** — a rejected telemetry POST (422 or 429) increments no metric and logs nothing,
  so a future client schema drift would read as a *drop* in `client.errors_total`, i.e. as good
  news.
- **BITB-347** — `docs/SECURITY.md` "Limits" lists none of the six per-scope IP limits and
  states a session lifetime of 100 against a real default of 10.

## Related

BITB-298 (introduced `require_ip_rate_limit`).
