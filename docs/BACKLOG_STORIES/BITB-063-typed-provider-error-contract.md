# BITB-063: Typed Provider Error Contract — Make the Unreachable 503 Reachable

**Status:** ✅ Done
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

- [x] A typed exception (`AllModelsExhaustedError`, `api/providers/errors.py`), carrying
      rate-limited-vs-unavailable detail (`reason`), `models_tried`, and an optional `retry_after`,
      is raised by both `chat()` and `chat_stream()` exhaustion paths in `openrouter.py`. The
      third, unreachable breaker-open-with-no-fallbacks branch was converted too, for consistency
      (no test covers it — it cannot be reached given the guard conditions above it).
- [x] Routes catch the **type** (`api/routes/chat.py`): non-stream → HTTP 503 with `Retry-After`;
      stream → the structured error chunk with a machine-readable `error_code` field. The old
      `if "All models rate limited" in str(e)` substring branches (which never matched) are
      removed.
- [x] Contract tests added: (a) `test_provider_error_contract.py` asserts provider exhaustion
      raises the typed error in both `chat()`/`chat_stream()`; (b) the same file asserts each route
      maps it to a 503 / an error chunk. A change to either side alone now fails CI.
- [x] Error responses carry machine-readable `code` (JSON 503 detail) / `error_code` (SSE chunk)
      fields — matching the two conventions already established elsewhere in the codebase
      (`utils/security.py`'s `code` field, `synthetic_chat.py`'s `error_code` extraction) —
      groundwork for a later Android follow-up on the `ChatViewModel.kt` substring matching (audit
      A8); the Android change itself is out of scope here.
- [x] `prod-monitor`'s `synthetic_chat.py` already extracts `error_code` from SSE error chunks and
      appends it to the alert detail — so the Telegram alert now distinguishes an upstream outage
      the moment the backend emits `error_code: "upstream_unavailable"`, with **no probe change
      required**. Making the alert *subject/text* branch on the code, or adding a dedicated
      non-stream probe that asserts the 503 + `Retry-After` directly, is follow-up work: it touches
      `.github/actions/notify-telegram`'s pass/fail model and is orthogonal to the typed-error
      contract itself.
