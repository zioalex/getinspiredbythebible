# BITB-061: Make the Abuse-Control Stack Fail Closed (Turnstile, Rate Limits, Content Safety)

**Status:** 🚧 In Progress — Turnstile and content-safety phases complete; rate-limiter phase remains
**Priority:** P1 (High) — 2026-07 adversarial audit E2 + S3 + O2 (all HIGH); every layer of bot/abuse/safety protection currently fails open, silently
**Size:** M (three coordinated changes: Turnstile policy, shared rate-limit store, safety defaults/metrics)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — E2, S3, O2

## User Story

As the operator, I want bot verification, rate limiting, and content safety to hold their line when
their dependencies fail — and to alert me when they can't — so that an attacker's cheapest path to
free LLM usage (or a user in crisis's path past safety screening) is not "wait for an upstream
hiccup".

## Problem / Motivation

Three independent controls, one shared philosophy — availability over protection, silently:

1. **Turnstile fails open on everything.** `api/utils/turnstile.py:92–103`: timeout → allow, HTTP
   error → allow, *any* `Exception` → allow. No metric fires when the bypass branch is taken.
2. **The rate limiter forgets and divides.** `api/utils/rate_limiter.py:54–56` is in-memory,
   per-process. Prod runs up to 2 replicas (`deployment/terraform.tfvars:56–59`): effective limits
   are 2× configured, and every deploy/restart resets all counters — including the 10-message
   session lifetime cap. No dedicated unit tests exist (audit D4).
3. **Content safety defaults off and every stage falls back to allow.**
   `content_safety_enabled=False` (`api/config.py:234`); OpenAI moderation → keyword fallback on
   bare `except Exception` (`content_safety.py:426–428`); Llama Guard → allow on transient error
   (`:351–361`) and on **empty response** (`llama_guard.py:111–113`); Azure stage → allow on
   exception (`:482–494`). For a pastoral-care product serving people in crisis in 11 languages,
   the self-harm/violence screen vanishing on an upstream hiccup — unalerted — is not acceptable.

## Acceptance Criteria

### Turnstile

- [x] Verification *rejections* fail closed (403). Transient siteverify errors may fail open for
      isolated blips, but persistent errors trip to fail-closed (circuit-breaker style — reuse
      `utils/circuit_breaker.py`).
- [x] Every fail-open occurrence emits a metric/log; an alert fires on its rate.

**Implemented 2026-07-05:** instance `CircuitBreaker(name="turnstile", failure_threshold=5,
cooldown_seconds=30)` in `TurnstileVerifier.__init__`; explicit `success:false` rejections and
confirmed successes both record breaker success (siteverify answered — endpoint healthy); transient
exceptions (timeout/HTTP error/other) record a breaker failure and, while the breaker is still
closed, fail open and emit `utils.metrics.turnstile_fail_open_counter` labelled by `reason`. Once
the breaker trips open, `verify()` short-circuits to fail-closed without hitting the network until
the cooldown elapses.

### Rate limiting

- [ ] Counters live in a shared store surviving restarts and consistent across replicas — Postgres
      UPSERT sliding window (pg_cron cleanup already available) or managed Redis; decision recorded
      in the story on implementation.
- [ ] Session lifetime cap survives deploys; limits hold at N replicas.
- [ ] `utils/rate_limiter.py` gains dedicated unit tests (window expiry, session cap, concurrency).

### Content safety

- [x] Keyword stage (local, free) **always** runs for self-harm/violence categories regardless of
      ML-stage availability; ML-stage failure degrades to keyword-only, not to allow-all.
- [x] Empty Llama Guard response is treated as an error, not as "safe".
- [x] Every fail-open/fallback branch emits a metric; alert on sustained fallback rate.
- [x] `content_safety_enabled` default flipped on (or prod env explicitly sets it, with the
      config/.env.example divergence from audit D6 resolved for these keys).

**Implemented 2026-07-07:**

- `_check_stage2_llama_guard` no longer returns `None` (→ allow-all) when the Llama Guard
  provider isn't configured; it now degrades to `_full_keyword_fallback` like every other
  branch (`api/utils/content_safety.py`).
- `LlamaGuardProvider._parse_llama_guard_response` raises `LlamaGuardResponseError` on an
  empty/blank body instead of returning `(True, [])`; a malformed `choices[0].message.content`
  shape (`KeyError`/`IndexError`/`TypeError`) is also caught and raised as the same error type,
  recording a circuit-breaker failure in both cases (`api/providers/llama_guard.py`).
- New `content_safety.fallback_total` counter (`api/utils/metrics.py`), labelled
  `stage` (`llama_guard`/`openai_moderation`/`azure`) × `reason`, emitted from every fallback
  branch including the two that previously had none (OpenAI Moderation
  provider-unavailable/exception, Azure exception in hybrid mode — the latter now falls back to
  the keyword filter instead of silently reaching the terminal default-allow).
- New `content_safety_fallback_rate` scheduled-query alert in `deployment/monitoring.tf`
  (Sev2, `customMetrics` on `content_safety.fallback_total`, mirrors `embedding_fallback_rate`).
- `content_safety_enabled` now defaults to `True` in `api/config.py` (already `True` in
  Terraform/prod — the code default only affected local dev); `api/.env.example` updated to
  `CONTENT_SAFETY_ENABLED=true` / `CONTENT_SAFETY_MODE=ml_only` to match, resolving audit D6.
- Rate-limiter phase intentionally deferred to a follow-up story: it puts a DB round-trip on
  every chat request's hot path (new migration + pg_cron cleanup + concurrency tests) and
  shouldn't ride along with a safety-critical change in the same PR.
