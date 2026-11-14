---
id: BITB-290
status: done
priority: P1
size: M
rank: 160
created: 2026-11-10
prs: [1281]
---

# BITB-290: Fallback-Share SLO Tile and Burn-Rate Alert Replace the Any-Fallback Alert

**Prompted by:** BITB-272 slice 1 (ML failover to OpenAI Moderation before the keyword fallback).

## Problem

BITB-272 req. 5: `content_safety_fallback_rate` fired 99 times in 30 days (BITB-223). Since slice 1, `content_safety.fallback_total` counts only keyword-fallback decisions, so a share-of-checked-messages SLO (< 0.5 % over 7 days, owner to confirm) is now measurable.

## Acceptance criteria

- [x] Dashboard tile: keyword-fallback share of checked messages by `stage`, `reason`, `failure_class`, `failover`
- [x] Multi-window burn-rate alert in Terraform replaces the any-fallback alert; coordinate with BITB-223 so alerts are not duplicated
- [x] Companion tile for `content_safety.failover_total` (failover absorbed vs failed)
- [ ] Owner step: confirm the SLO target (0.5 % / 7 days is the default of `content_safety_fallback_slo_target`)
- [ ] Owner step: `terraform apply` (destroys `content_safety_fallback_rate`, creates `content_safety_fallback_burn_fast` and `content_safety_fallback_burn_slow`)

## Plan / design

- New denominator counter `content_safety.checks_total` (label `mode`), incremented once per
  `ContentSafetyService.check()` call after the disabled early-return.
- SLO math: budget 0.5 % of checks over 7 days. Fast alert: 14.4x burn means a 7.2 % fallback
  share over both 1 h and 5 min pages Sev2 (PT5M evaluation). Slow alert: 6x burn means a 3 %
  share over both 6 h and 30 min pages Sev3 (PT15M evaluation). Low-traffic guard: at least 3
  fallbacks in the long window.
- The 7-day window is not evaluated directly because Azure caps scheduled-query look-back at
  48 h; burn rates over shorter windows are the standard multi-window substitute.
- BITB-223 coordination: the any-fallback rule `content_safety_fallback_rate` is replaced, not
  duplicated. The workbook SLO-target column is a literal 0.5 %; keep it in step with the
  Terraform variable if the target changes.
- Workbook: new *Content Safety* group (share tile, breakdown table, hourly share timechart,
  failover outcomes table).

## Notes

Coordinate with BITB-223.

## Related

BITB-272, BITB-257, BITB-223, BITB-224.
