# BITB-063: Typed Provider Error Contract — Make the Unreachable 503 Reachable

**Status:** 📋 Backlog
**Priority:** P1 (High) — 2026-07 adversarial audit E1 (HIGH); total-LLM-outage handling is dead code, outages misreport as generic 500s
**Size:** S (typed exception + two route handlers + the contract test that was always missing)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — E1 (context: A8, D4)

## User Story

As the operator, I want a total LLM-provider outage to surface as a 503 with a clear
"upstream unavailable" signal — to monitoring, to clients, and to users — so that incident response
starts with "OpenRouter is down" instead of a misleading generic-500 hunt, and clients back off
instead of retry-hammering a dead upstream.

## Problem / Motivation

When all OpenRouter fallback models are exhausted, the provider raises:

- `RuntimeError("All models unavailable or rate limited. …")` (`api/providers/openrouter.py:308`)
- `RuntimeError("All models unavailable in streaming. …")` (`api/providers/openrouter.py:491`)

The routes special-case the outage by substring: `if "All models rate limited" in str(e)`
(`api/routes/chat.py:75, 124`). **That substring appears in neither message.** The intended 503
branch (non-stream) and the intended friendly stream-error chunk are unreachable. The one scenario
the fallback chain was built for is the one it misreports — and no test pins the provider's message
to the route's match, which is exactly how this shipped (audit D4).

This is an instance of a broader anti-pattern flagged by the audit (A8): cross-boundary contracts
expressed as prose to be grepped (Android does the same against backend error bodies,
`ChatViewModel.kt:1176, 1185`).

## Acceptance Criteria

- [ ] A typed exception (e.g. `AllModelsExhaustedError`, carrying rate-limited-vs-unavailable
      detail) is raised by both `chat()` and `chat_stream()` exhaustion paths.
- [ ] Routes catch the **type**: non-stream → HTTP 503 with `Retry-After`; stream → the structured
      error chunk with a machine-readable `code` field.
- [ ] Contract tests: (a) provider exhaustion raises the typed error in both paths; (b) route maps
      it to 503/error-chunk. A change to either side alone fails CI.
- [ ] Error responses carry machine-readable `code` fields (groundwork for BITB follow-up on the
      Android substring matching — audit A8; Android change itself out of scope here).
- [ ] `prod-monitor` synthetic-chat treats the 503 as "upstream outage" (distinct alert text), not
      generic backend failure.
