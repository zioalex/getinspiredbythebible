---
id: BITB-346
status: todo
priority: P2
kind: nfr
size: XS
created: 2026-11-19
depends_on: [BITB-310]
---

# BITB-346: Rejected Telemetry Is Invisible — a Silent Drop Looks Like Good News

**Prompted by:** BITB-310 verification (finding 2).

## Problem

`POST /api/v1/client-errors` and `POST /api/v1/client-events` (`api/main.py`) return a 422
(unknown field) or a 429 (over the telemetry IP limit) **before** the handler body runs, so
neither `client_errors_counter` nor the TTS event counter is incremented and nothing is
logged. The rejection leaves no trace at all.

That matters because `deployment/monitoring.tf` alerts on a *spike* in
`client.errors_total`. If a future web client adds a field to its report body, `extra="forbid"`
(added by BITB-310) turns every report into a 422 and the metric drops to zero — which reads
as "the client got healthier", not "we stopped receiving error reports". The same blindness
applies to a NATted office or CGNAT range hitting the 60/min cap: real client errors vanish
with no signal.

Today's senders are safe — `frontend/src/lib/clientErrorReporter.ts` and
`frontend/src/lib/turnstile.tsx` post exactly `{type, detail}`, and Android does not call
`/client-errors` (verified 2026-11-19, including across the full `git log -p` history of both
files) — so this is a guard against future drift, not a live outage.

## Requirements

1. Count rejected telemetry with a bounded label set, e.g.
   `client.telemetry_rejected_total{route, reason}` with `reason` in
   `{invalid_body, rate_limited}` and `route` in `{client_errors, client_events}`.
   Reuse the existing meter in `api/utils/metrics.py`; do not add a new exporter.
2. For the 429 path this means recording inside `require_ip_rate_limit` (or a thin wrapper)
   rather than the handler, since the dependency returns first — keep the chat scopes'
   behaviour unchanged.
3. For the 422 path, a FastAPI `RequestValidationError` handler scoped to these two routes, or
   an equivalent that does not change the response body.
4. An alert (or a documented query) on a sustained non-zero `invalid_body` rate — that is the
   signal that a shipped client has drifted from the schema.

## Tests

- A body with an unknown field increments `invalid_body` for the right route and still returns
  422 with an unchanged body.
- Exceeding the telemetry limit increments `rate_limited` and still returns the standard 429
  detail dict.
- Label cardinality is bounded: an arbitrary route/reason cannot reach the metric.

## Acceptance criteria

- [ ] Both rejection paths are observable, with bounded labels
- [ ] Response bodies and status codes unchanged
- [ ] A sustained `invalid_body` rate is alertable (or the query is documented)

## Related

BITB-310 (added `extra="forbid"` and the telemetry limiter), BITB-307 (bounded metric labels).
