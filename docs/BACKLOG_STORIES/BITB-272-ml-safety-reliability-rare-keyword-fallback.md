# BITB-272: Make ML Content-Safety Classification Reliable So the Keyword Fallback Is Rare

**Status:** 🎯 Todo
**Priority:** P1
**Size:** L
**Created:** 2026-11-04
**Prompted by:** BITB-257 (PR #1241). The owner chose the fail-safe keyword fallback (option A),
which deliberately blocks some Bible-narrative questions while ML moderation is down. That
trade-off is only acceptable if the fallback runs rarely.

## Problem (verified in code, 2026-11-04)

- Production runs `content_safety_mode = "ml_only"` (`api/config.py`). Stage 2 is
  `LlamaGuardProvider` (`api/providers/llama_guard.py`): a primary Llama Guard model, then a
  secondary `openai/gpt-oss-safeguard-20b` model. **Both go through OpenRouter.** An OpenRouter
  outage, rate limit, auth failure or open circuit breaker therefore takes out every ML stage at
  once. `_check_stage2_llama_guard` then drops straight to `_keyword_fallback`
  (`api/utils/content_safety.py`).
- In `ml_only` mode, the other classifiers the code already supports (OpenAI Moderation,
  `_check_stage2_openai_moderation`, and Azure Content Safety) are never tried as failover. They
  are only used in `keyword_only` / `hybrid` modes.
- The fallback is not rare today. BITB-223 measured the `content_safety_fallback_rate` alert
  firing **99 times in 30 days**, which made it an alert-fatigue candidate rather than a page.
- Timeouts are tight (primary 3 s, secondary 5 s; the 2026-07 benchmark measured primary p99 ~2.3 s
  and a secondary outlier of 16.6 s). Slow-but-healthy responses also count as failures.
- The keyword fallback can't understand context. After BITB-257 it errs toward blocking (Bible
  narrative is sometimes blocked and gets a crisis card), so every fallback request risks a bad
  answer for a Bible-study user.

## User story

As a Bible-study user, I want my message checked by a context-aware classifier every time,
so that ordinary questions about Bible narrative ("Why did Cain kill Abel?") are not blocked.
I also want real threats to stay caught even when one provider is having problems.

## Functional requirements

1. **Failover across providers in `ml_only` mode.** When Llama Guard (both models) fails, try at
   least one ML classifier on a *different* provider before the keyword fallback, e.g. OpenAI
   Moderation (`OPENAI_API_KEY`) and/or Azure Content Safety. The order and enabled set are
   configurable.
2. **Failure classification.** Separate timeout, 429, 5xx, auth/config errors, malformed responses
   and an open breaker in metrics (extending `content_safety_fallback_total` /
   `llama_guard_fallback_total` labels). Config errors (no key) must be visible at startup, not
   discovered per request.
3. **Timeout and retry tuning from data.** Re-benchmark latency and set timeouts and one bounded
   retry (with jitter, inside the overall latency budget) from the measured p99. Keep a hard
   overall cap so the chat request isn't held.
4. **Circuit-breaker tuning.** Review the breaker thresholds and half-open probing so a brief blip
   doesn't send traffic to the keyword path for the whole open window.
5. **Observability and SLO.** A dashboard tile and alert for the *share of requests decided by
   the keyword fallback*, per stage and reason. Target SLO: **< 0.5 % of checked messages over
   7 days** (to be confirmed by the owner). The alert should fire on a sustained SLO burn, not on
   every single fallback (coordinate with BITB-223).
6. **Synthetic probe.** `prod-monitor.yml` (or the BITB-224 availability tests) exercises the ML
   classifier path end to end, so an outage is detected before users hit it.

## Non-functional requirements

- Latency: p95 of the safety check stays ≤ the current p95. Failover only adds latency on the
  failure path.
- Privacy: any new provider must meet the existing data-retention bar (ZDR, or documented
  retention). Messages are not logged in clear text.
- All 11 languages: the failover classifier must be checked against the existing multilingual
  safety golden set (crisis + threat + Bible-narrative cases for en, it, de, es, fr, pt, ar, ru,
  zh, hi, ko) before it is enabled.
- Cost: document the monthly cost of the extra provider (OpenAI Moderation is free).

## Acceptance criteria

- [ ] In `ml_only`, a simulated OpenRouter outage (Llama Guard primary + secondary failing) is
      handled by a second-provider ML classifier, not the keyword fallback (unit + integration test)
- [ ] The keyword fallback runs only when *every* configured ML classifier has failed; tested
- [ ] Fallback-share metric, dashboard tile and SLO burn alert exist; Terraform updated
- [ ] Timeouts/retry/breaker values set from a fresh benchmark, recorded in the story
- [ ] Failover classifier passes the multilingual safety golden set across all 11 languages
- [ ] Measured fallback share over 14 days of production after release is below the SLO
      (owner step)
- [ ] `docs/` content-safety documentation updated (pipeline diagram, env vars in
      `scripts/env-manifest.yaml`)

## Out of scope

- Making the keyword fallback itself smarter (BITB-257 and follow-ups own that).
- Replacing Llama Guard as the primary classifier.

## Open questions

- Which failover provider(s): OpenAI Moderation only, Azure Content Safety only, or both?
- Is the < 0.5 % / 7-day SLO the right target?
- Should a sustained fallback period show the user a soft "safety checks degraded" notice
  instead of a crisis card on borderline matches (BITB-257 option C, deferred)?

## Related

BITB-257 (fail-safe keyword fallback), BITB-223 (alert rationalization; fallback alert noise),
BITB-224 (availability tests), BITB-199 (second-opinion classifier model), BITB-155
(OpenRouter models).
