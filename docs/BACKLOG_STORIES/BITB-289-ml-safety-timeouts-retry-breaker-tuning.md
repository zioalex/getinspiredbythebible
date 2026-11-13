---
id: BITB-289
status: in-progress
priority: P1
size: M
rank: 160
created: 2026-11-10
---

# BITB-289: Re-benchmark Llama Guard Timeouts, Add Jittered Retry, Tune Breaker Half-Open

**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 req. 3 and 4: primary 3 s / secondary 5 s timeouts come from a 2026-07 benchmark (secondary outlier 16.6 s), and a brief blip can keep traffic off the ML path for the whole breaker open window.

## Acceptance criteria

- [ ] Fresh 100+ sample production benchmark of primary, secondary and OpenAI Moderation latency recorded in this story
- [ ] Timeouts and one bounded retry with jitter set from measured p99, inside a hard overall cap for the safety check _(partially done in slice 1: retry, jitter and 8 s cap implemented with provisional values; final values come from the AC1 benchmark)_
- [x] Breaker thresholds and half-open probing reviewed so a short blip does not hold the keyword/failover path for the full open window; tests cover half-open recovery
- [ ] p95 of the safety check is not worse than today _(owner step: verify in production after deploy)_

## Implementation (slice 1)

- `utils/circuit_breaker.py`: opt-in `single_probe` (the first caller after the cooldown holds a probe lease; concurrent callers are short-circuited; the lease expires after `probe_timeout_seconds` so a probe that never records an outcome cannot wedge the breaker) and `max_cooldown_seconds` (each consecutive failed probe by the lease holder doubles the cooldown, capped; stale failures without a lease do not escalate it; success resets it). Defaults keep the other breakers (openrouter, embedding, rate limiter, turnstile) unchanged. `current_cooldown_seconds` is exposed for tests/logging.
- `config.py`: `llama_guard_secondary_timeout` (5 s), `llama_guard_total_budget_seconds` (8 s), `llama_guard_retry_jitter_max_ms` (250), `llama_guard_breaker_failure_threshold` (5), `llama_guard_breaker_cooldown_seconds` (10), `llama_guard_breaker_max_cooldown_seconds` (60). All provisional pending the benchmark; validated (positive values, max cooldown >= base).
- `providers/llama_guard.py`: breaker uses single-probe + backoff; `analyze_text` tracks a deadline, applies 0..jitter-max uniform jitter before the secondary retry (only if it leaves at least 0.5 s), caps the secondary timeout at the remaining budget, enforces the overall deadline with `asyncio.timeout` around each model call (httpx timeouts are per-phase, so a trickled response could otherwise overrun; an overrun surfaces as `httpx.TimeoutException` so the ml_only OpenAI Moderation failover still triggers), and skips the secondary (breaker failure, metric outcome `skipped_budget`) when under 0.5 s remains.
- Tests: `tests/test_circuit_breaker.py` (new), `tests/test_llama_guard.py` (budget, jitter, skip, half-open stampede, 11-language parametrized recovery).

## Benchmark how-to (AC1)

Latency is already recorded: histogram `llama_guard.model_call_duration_ms`, attributes `model_tier` (`primary`|`secondary`) and `outcome` (`success`|`failed`). In App Insights read p50/p95/p99 per tier from that metric (filter `outcome=success`, and separately `failed` for timeout shape) instead of an ad-hoc script. Fallback and recovery rates: `llama_guard.primary_result_total` and `llama_guard.secondary_model_total` (`recovered`|`also_failed`|`skipped_budget`). OpenAI Moderation latency comes from the BITB-272 failover metrics. Set the timeouts from measured p99 and record the numbers here.

## Notes

Depends on BITB-272 slice 1 (failover metrics) for before/after data.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.
