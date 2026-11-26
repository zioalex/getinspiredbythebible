---
id: BITB-321
status: todo
priority: P1
kind: fix
milestone: R1
size: S
created: 2026-11-15
---

# BITB-321: Llama Guard Primary Model Returns Null Content on Every Call

## Problem

Since at least 2026-11-09 (the start of the 7-day log window), **every** call to the primary
content-safety model `meta-llama/llama-guard-4-12b` (`api/providers/llama_guard.py`, `MODEL`)
fails with `Llama Guard API returned malformed response shape`. OpenRouter answers with
`choices[0].message.content: null`. Every chat message then retries on the secondary
`openai/gpt-oss-safeguard-20b` (reasoning model, `SECONDARY_MAX_TOKENS = 800`).

Evidence: `make az-chat-stream-errors DAYS=7` (2026-11-16) shows `llama_guard_malformed` ==
`llama_guard_primary_failed` in every hour across revisions 0000064–0000078.

## Impact

- About +0.8 s on every chat turn (`content_safety=780–850ms` in `chat_stage_timings`).
- Moderation runs entirely on the secondary model. Its precision and recall in the 11
  languages are less validated than the primary's (see BITB-293's golden set).
- The breaker never opens (the secondary recovers), so nothing alerts.

## Suspected cause

The primary call uses `PRIMARY_MAX_TOKENS = 20` and no `reasoning` field. If the route
OpenRouter now picks for this model spends tokens on reasoning, or needs a provider
preference, the visible content can be empty. Reproduce with a direct OpenRouter call (needs the
key) and compare `usage`, `finish_reason` and `provider`.

## Acceptance criteria

- [ ] Root cause shown with a captured OpenRouter response (no message text in the repo).
- [ ] Fix (request parameters, provider pinning or a model swap) with a regression test on the
      response shape the route actually returns.
- [ ] A metric or alert fires when the primary failure rate is above X% for an hour, so a
      silently dead primary is caught.
- [ ] Owner step: after deploy, `make az-chat-stream-errors DAYS=1` shows `llama_guard_malformed`
      near zero and `content_safety` stage time back to its pre-failure level.
