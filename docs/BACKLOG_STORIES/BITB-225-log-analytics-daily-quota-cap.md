# BITB-225: Log Analytics Daily Ingestion Cap as Bounded-Downside Insurance

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — Part A lever, deferred-to-insurance)

## User Story

**As** the owner of an ingestion-billed workspace with no ceiling, **I want** a
`daily_quota_gb` cap set above observed p99 ingestion, **so that** a future
log-spewing regression costs a bounded amount instead of an open-ended bill —
while normal operation never touches the cap.

## Why this is insurance, not savings

Phase 0 measured actual ingestion (`02-log-analytics-billable-gb.json`):

- Total billable: **≈3.0 GB / 30 days** (~0.10 GB/day average, p99 ≈ 0.2 GB/day)
- Top tables: `AppDependencies` 1.06 GB, `AppRequests` 0.35 GB, `AppMetrics`
  0.29 GB — together ~57% of the total
- The whole workspace line is only **4.31 CHF/mo** (`01-cost-by-resource-type.json`)

So today's cost does not justify optimization; the cap converts the *tail risk*
(a noisy-neighbour regression, a debug-log loop, an auto-instrumentation change)
from unbounded to bounded. The BITB-150 story's framing applies exactly: decide
deliberately whether a blind-but-capped day beats an uncapped bill, and write
the answer down.

## The cap-trip trade-off (the whole decision)

- **When the cap trips:** ingestion *stops* — the workspace goes blind, which
  also means **log-search alerts stop evaluating** on new data.
- **What still works:** the `prod-monitor.yml` Telegram probes (health,
  synthetic-chat, content-safety, cross-origin, verse-search, frontend, log-scan
  runs *before* the cap affects it on its own schedule — actually log-scan reads
  the workspace, so treat the GH direct probes as the survivors) and metric
  alerts (they read Azure Monitor metrics, not LA tables). The Telegram channel
  therefore stays alive for the most user-facing failure modes.
- **Required setting:** `daily_quota_gb` on `azurerm_log_analytics_workspace.main`
  (`deployment/main.tf:254-261`), plus `workspace_ingestion_access` behavior
  verified (notify-on-cap behavior documented).

## Proposed cap value

**1 GB/day** — 5× the observed p99 (0.2 GB), 10× the average, leaving headroom
for organic growth and a deploy-day spike, while still bounding a runaway to
~1 GB × the per-GB rate (≈2.30 CHF/GB → worst case ~2.3 CHF/day vs unbounded).

## Acceptance Criteria

- [ ] `daily_quota_gb = 1` set on the workspace resource in `deployment/main.tf`
- [ ] The blind-but-capped trade-off is recorded here (done above) and referenced
      from `deployment/README.md`'s monitoring section
- [ ] Cap-trip behavior verified once in a safe window (e.g. temporary 0.001 cap
      on a dev workspace, or by reviewing Azure's documented notify flow) —
      what stops, what keeps paging, what the owner sees
- [ ] A monthly one-line check (manual or the weekly evidence workflow) that
      daily ingestion stays under 50% of the cap — if it ever exceeds it, raise
      the cap deliberately, don't silently eat blind days
- [ ] The BITB-150 exit note links this story as the accepted insurance lever

## Out of Scope

- Table-level Basic plans (blocked by alert dependencies — declined in BITB-150)
- Sampling (BITB-226) — orthogonal; sampling reduces volume, the cap bounds it

## Related

- BITB-150 — parent; Part A lever 1, its caveat is quoted almost verbatim above
- BITB-056 — added the workspace and most ingestion sources
- BITB-223 — alert rationalization changes which rules a cap-trip would blind
