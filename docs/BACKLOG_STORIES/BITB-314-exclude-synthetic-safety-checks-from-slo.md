---
id: BITB-314
status: todo
priority: P2
size: S
created: 2026-11-14
---

# BITB-314: Exclude Synthetic ML-Safety Probe Checks From the Content-Safety SLO Metrics

**Prompted by:** BITB-291 (PR #1279), follow-up 1 in its PR description.

## Problem

BITB-291 adds `POST /health/content-safety-probe` (`api/routes/health.py`). The `ml-safety-path`
job in `.github/workflows/prod-monitor.yml` calls it every 5 minutes with two messages, a benign
one and an unsafe one. Each call runs a real `ContentSafetyService.check()`
(`api/utils/content_safety.py`), so it increments the same counters as real user traffic
(`content_safety.checks_total`, `content_safety.fallback_total`, `content_safety.failover_total`,
`llama_guard.*` in `api/utils/metrics.py`). That adds about 576 synthetic checks per day.

BITB-290's keyword-fallback-share SLO and its burn-rate alerts (`deployment/monitoring.tf`, workbook
`deployment/azure-monitor/workbook-performance-dashboard.json`) divide by `checks_total`. The
synthetic checks therefore skew the SLO in two ways:

- On low-traffic days the probe dominates the denominator, so the share looks healthier than real
  user traffic.
- When the ML path is down, the probe's own fallbacks count as user-facing fallbacks, which
  double-alerts on top of the `ml-safety-path` Telegram alert.

## Acceptance criteria

- [ ] The probe endpoint marks its checks as synthetic (e.g. a `synthetic=true` metric attribute, or
      a `synthetic` argument to `check()` that skips or labels the metric increments). Real chat
      traffic is unaffected.
- [ ] The SLO query, burn-rate alerts and workbook tiles from BITB-290 exclude synthetic checks.
      Probe health stays visible on its own (separate tile, or the `ml-safety-path` job alone).
- [ ] Unit tests: a probe call does not change the non-synthetic counters (or labels them
      `synthetic=true`); a normal `check()` still does. Parametrized over the 11 languages
      (en, it, de, es, fr, pt, ar, ru, zh, hi, ko), since BITB-315 probes more than `en`.
- [ ] `docs/HOW-TO-ENABLE-CONTENT-SAFETY.md` explains that probe checks are excluded from the SLO.
- [ ] Owner step: `terraform apply` the updated alert/workbook queries.

## Depends on

BITB-291 (#1279) and BITB-290 merged.

## Related

BITB-272, BITB-290, BITB-291, BITB-315.
