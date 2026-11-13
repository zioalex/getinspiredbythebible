---
id: BITB-290
status: todo
priority: P1
size: M
rank: 160
created: 2026-11-10
---

# BITB-290: Fallback-Share SLO Tile and Burn-Rate Alert Replace the Any-Fallback Alert

**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 req. 5: `content_safety_fallback_rate` fired 99 times in 30 days (BITB-223). Since slice 1, `content_safety.fallback_total` counts only keyword-fallback decisions, so a share-of-checked-messages SLO (< 0.5 % over 7 days, owner to confirm) is now measurable.

## Acceptance criteria

- [ ] Dashboard tile: keyword-fallback share of checked messages by `stage`, `reason`, `failure_class`, `failover`
- [ ] Multi-window burn-rate alert in Terraform replaces the any-fallback alert; coordinate with BITB-223 so alerts are not duplicated
- [ ] Companion tile for `content_safety.failover_total` (failover absorbed vs failed)
- [ ] Owner step: confirm the SLO target

## Notes

Coordinate with BITB-223.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.
