# BITB-291: Synthetic Probe of the ML Content-Safety Path in prod-monitor

**Status:** 🎯 Todo
**Priority:** P1
**Size:** M
**Created:** 2026-11-10
**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 req. 6: an outage of Llama Guard or the failover is currently found only when users hit the keyword fallback.

## Acceptance criteria

- [ ] `prod-monitor.yml` (or the BITB-224 availability tests) sends a benign Bible-narrative question and a known-unsafe probe and asserts the ML path (not the keyword fallback) decided, e.g. via a response header or metric
- [ ] Probe failure alerts the owner; the probe message is clearly synthetic and not stored as user data
- [ ] Documented in `docs/` with the zero-to-running steps

## Notes

Related: BITB-224.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.
