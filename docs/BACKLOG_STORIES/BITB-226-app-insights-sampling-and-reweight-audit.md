# BITB-226: App Insights Sampling — Only After the Percentile-Reweighting Audit

**Status:** 🎯 Todo (gated — do not implement before the audit passes)
**Priority:** P2
**Size:** M (audit first, then a small code change)
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — Part A lever, accepted-but-deferred)

## User Story

**As** the owner paying ~2.30 CHF/GB for App Insights ingestion dominated by
`requests` and `dependencies`, **I want** a `sampling_ratio` configured *after*
every percentile/aggregate consumer is audited and fixed for reweighting, **so
that** I save ingestion money without silently corrupting the p95 latency alerts
and the performance dashboard.

## The evidence (why this lever survived the "top-2" gate)

BITB-150's rule: skip sampling entirely unless `requests` is a top-2 itemType.
It is:

- `03-app-insights-record-counts.json` (7 days): `AppDependencies` **250,063**
  records, `AppRequests` **82,303** — #1 and #2
- Ingestion (30d): `AppDependencies` 1.06 GB + `AppRequests` 0.35 GB + `AppMetrics`
  0.29 GB ≈ 57% of workspace ingestion
- Estimated saving at a moderate ratio (e.g. 0.5): **~2.90 CHF/mo** — small, which
  is why it sits behind the audit, not ahead of it

## Why the audit is the deliverable, not a footnote

Azure Monitor sampling writes `itemCount` so aggregates can be reweighted — but
**an unweighted `percentile()` over sampled data is wrong, quietly**. Before any
`sampling_ratio` is set, every consumer must be enumerated and either reweighted
or exempted:

| Consumer | Where | Fix needed |
|----------|-------|-----------|
| `scripture_fetch_latency_p95` alert | `deployment/monitoring.tf` (~:762) | `percentile(..., itemCount)` weighting or accept sampled p95 |
| `scripture_search_latency_p95` alert | `deployment/monitoring.tf` (~:919) | same |
| `chat_ttft_p95` alert | `deployment/monitoring.tf` (~:1609) | same (demoted in BITB-223, still must be correct) |
| Performance dashboard workbook | `deployment/azure-monitor/workbook-performance-dashboard.json` | every panel that counts/averages/percentiles over `requests`/`dependencies`/`customMetrics` |
| Log-based rules generally | `deployment/monitoring.tf` | count-based thresholds (error rates) must multiply by `itemCount` |
| `docs/` queries & runbooks | workbook/README references | update so humans don't copy unweighted KQL |

The 2026-08-17 retrospective's process rule ("benchmark before you build on a
performance claim") applies in spirit: do not change the data shape under the
dashboards without proving the dashboards still tell the truth.

## Acceptance Criteria

- [ ] **Audit artifact:** a complete inventory of every KQL consumer of
      `requests`, `dependencies`, `traces`, `customMetrics`, `exceptions`,
      `availabilityResults` across `deployment/` and the workbook JSON — committed
      with this story, each marked *reweighted / exempt (metric-alert only) /
      count-adjusted*
- [ ] Every percentile/count query identified above is either rewritten with
      `itemCount` reweighting or provably unaffected
- [ ] `sampling_ratio` chosen from measured value, not vibes: document the ratio
      (0.5 initial suggestion) and the resulting record/GB drop
- [ ] After enabling: one week of parallel observation — p95 alert behavior
      unchanged (no new false positives/negatives), workbook panels within
      expected variance
- [ ] Ingestion drop visible in the `Usage` table within the first week
- [ ] The saving is re-derived from the meter post-change and recorded here

## Out of Scope

- `ContainerAppConsoleLogs_CL` Basic-tier move (declined in BITB-150: 17 rules
  read it, and it is 0.016 GB/mo — nothing to save)
- Reducing *what* is instrumented (that's a code change, different story)

## Related

- BITB-150 — parent; the audit requirement is quoted from its lever 2
- BITB-223 — demotes one of the three p95 alerts but does not remove it
- BITB-022 — the workbook's panels and their query fixes (history of KQL pitfalls)
