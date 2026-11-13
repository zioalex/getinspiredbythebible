---
id: BITB-292
status: todo
priority: P1
size: M
rank: 190
created: 2026-11-10
---

# BITB-292: Azure Content Safety as an Ordered Second ML Failover

**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 slice 1 fails over only to OpenAI Moderation. If both OpenRouter and OpenAI are down the keyword fallback runs. Azure Content Safety (already implemented as a provider for hybrid mode) can be a third ML classifier.

## Acceptance criteria

- [ ] Configurable ordered failover list for `ml_only` (e.g. `openai_moderation,azure`), default unchanged
- [ ] Azure is tried only after OpenAI Moderation fails; keyword fallback only when every configured classifier failed; unit + integration tests across the 11 languages
- [ ] Metrics reuse `content_safety.failover_total` with a `to_stage` label per hop
- [ ] Cost and data-retention for Azure documented

## Notes

Requires the Azure Content Safety resource and key in production.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.
