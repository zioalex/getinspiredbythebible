# BITB-289: Re-benchmark Llama Guard Timeouts, Add Jittered Retry, Tune Breaker Half-Open

**Status:** 🎯 Todo
**Priority:** P1
**Size:** M
**Created:** 2026-11-10
**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 req. 3 and 4: primary 3 s / secondary 5 s timeouts come from a 2026-07 benchmark (secondary outlier 16.6 s), and a brief blip can keep traffic off the ML path for the whole breaker open window.

## Acceptance criteria

- [ ] Fresh 100+ sample production benchmark of primary, secondary and OpenAI Moderation latency recorded in this story
- [ ] Timeouts and one bounded retry with jitter set from measured p99, inside a hard overall cap for the safety check
- [ ] Breaker thresholds and half-open probing reviewed so a short blip does not hold the keyword/failover path for the full open window; tests cover half-open recovery
- [ ] p95 of the safety check is not worse than today

## Notes

Depends on BITB-272 slice 1 (failover metrics) for before/after data.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.
