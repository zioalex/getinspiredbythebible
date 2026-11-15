---
id: BITB-321
status: todo
priority: P1
size: M
created: 2026-11-15
depends_on: [BITB-320]
---

# BITB-321: Investigate Intermittent Server-Side Mid-Stream Chat Failures

## Problem

Since the deploy of `e401385` (2026-11-15), Android replies *sometimes* arrive without the final
`completion` SSE event (BITB-320). In `api/routes/chat.py` `generate()`, `chat_stream`
raised after content had started streaming, and the route then sent `{"type":"error"}` instead
of `completion`. The other possibility is that the connection was closed before `[DONE]`
(ingress, Cloudflare or client timeout). Which one it is, and what raised, is visible only in
production telemetry.

## Investigation

1. In App Insights, query `Chat stream failed` / `Chat stream runtime error` /
   `Streaming: all LLM models exhausted` around the reported failures. Group by exception type
   and provider/model.
2. Check for responses cut off without an exception (stream duration at the ingress or Cloudflare
   timeout).
3. Check whether the failures started with this deploy window (#1278–#1290: BITB-289 Llama Guard
   probe/budget, BITB-292 failover chain, BITB-296 body-size middleware, BITB-297 client IP,
   BITB-298 rate limits) or were already happening but hidden by Android.
4. Use the BITB-320 counters (`degraded` completion, `partial` error, client finalize) to
   size the problem.

## Acceptance criteria

- [ ] Root cause identified with log evidence, or ruled out as provider flakiness with a measured rate.
- [ ] A fix (or a tuned timeout/retry) with a regression test, or a documented decision to accept it.
