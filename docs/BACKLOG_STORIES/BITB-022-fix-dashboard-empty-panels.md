# BITB-022: Fix Remaining Empty Panels in Performance Dashboard

**Priority:** P0 (Critical — dashboard is partially broken in production)
**Status:** 🎯 Todo
**Size:** M (4-6 hours)
**Created:** 2026-03-06
**Last Updated:** 2026-03-06 (post-PR-241 error catalogue added)

---

## Background

The Azure Monitor Performance Dashboard was deployed and progressively fixed:

1. **BITB-021** (PR #239) — Added backend instrumentation to emit custom metrics
2. **Workbook source_id fix** (PR #240) — Connected workbook to Application Insights resource
3. **PR #241** — Further monitoring fixes (exact scope TBC)

After all fixes were deployed, the dashboard still shows broken panels in two categories:

**Category A — "Could not create tiles. Use tile settings to configure this section."**
These panels return **zero rows** from their KQL query. The workbook `tiles` visualisation
requires at least one row; an empty result set triggers this exact error instead of
showing zeros or "No data".

Affected panels:

- Request Volume & Error Rate
- Response Time Percentiles
- Time to First Token (TTFT)
- Total LLM Duration
- Fallback Rate
- Rate Limit Hits
- Semantic Search Duration
- General Query Duration
- Container Restart Events

**Category B — KQL function restriction errors**
These panels use KQL aggregation functions that are either not supported or produce
syntax errors in the Azure Monitor Workbook KQL runtime.

- **Availability (health probe)**: `Function 'countif' cannot be invoked in current context`
  - Root cause: `countif(success == true and timestamp > ago(1h))` — compound predicate
    with a time filter inside `countif()` is not valid in this KQL context. Must rewrite
    using nested `where` + `count()`.
- **Exception Summary (top 10 types)**: `Function 'any' cannot be invoked in current context`
  - Root cause: `any(outerMessage)` is a restricted aggregation in Azure Monitor KQL workbook
    context. Must replace with `take 1` pattern or `min(outerMessage)`.

**Working panels (must not be broken):**

- ✅ Request Rate Over Time
- ✅ Tokens per Second Trend (last 24h, 1h bins)
- ✅ Container CPU & Memory Trend (5min bins)

---

## User Story

**As a** site reliability engineer using the Performance Dashboard,
**I want** all dashboard panels to display real data (not "Could not create tiles" or function errors),
**so that** I can monitor application health, detect performance issues, and troubleshoot errors effectively.

---

## Root Cause Analysis (Confirmed Post-PR-241)

### Root Cause 1: Zero-row queries crash the `tiles` visualisation

The workbook `tiles` visualisation type in Azure Monitor **requires at least one row** to render.
When a KQL query returns zero rows (no data in the time range, or no matching metrics), the tiles
renderer emits: *"Could not create tiles. Use tile settings to configure this section."*

**Fix:** Every `tiles`-visualised query must be wrapped to guarantee exactly one row, even when
there is no data. Use the `union` trick:

```kql
// Pattern: always emit one row with defaults when there is no data
customMetrics
| where timestamp > {timeRange:start}
| where name == "llm.ttft_ms"
| summarize P50 = percentile(value, 50), P95 = percentile(value, 95), P99 = percentile(value, 99)
| union (print P50 = real(null), P95 = real(null), P99 = real(null))
| summarize P50 = max(P50), P95 = max(P95), P99 = max(P99)
| extend P50 = iff(isnull(P50), 0.0, P50), P95 = iff(isnull(P95), 0.0, P95), P99 = iff(isnull(P99), 0.0, P99)
| project ["TTFT P50 (ms)"] = round(P50, 0), ["TTFT P95 (ms)"] = round(P95, 0), ["TTFT P99 (ms)"] = round(P99, 0)
```

This pattern applies to **all** `tiles` panels.

### Root Cause 2: `countif()` with compound time predicate — Availability panel

**Current broken query (line ~94 in workbook JSON):**

```kql
availabilityResults
| where timestamp > ago(7d)
| summarize
    ["Last 1h"] = round(100.0 * countif(success == true and timestamp > ago(1h)) / max(1, countif(timestamp > ago(1h))), 1),
    ...
```

**Error:** `Function 'countif' cannot be invoked in current context`

The `timestamp > ago(1h)` predicate inside `countif()` is not valid within an outer
`summarize` that already has a time filter. The sub-filters create a nested aggregation
context that KQL does not support here.

**Fix:** Use conditional columns + `countif` with a boolean column, or split into
separate `summarize` statements:

```kql
availabilityResults
| where timestamp > ago(7d)
| extend in1h = timestamp > ago(1h), in24h = timestamp > ago(24h)
| summarize
    hits1h    = countif(success == true and in1h),
    total1h   = countif(in1h),
    hits24h   = countif(success == true and in24h),
    total24h  = countif(in24h),
    hits7d    = countif(success == true),
    total7d   = count()
| project
    ["Last 1h"]  = round(100.0 * hits1h  / max(1, total1h),  1),
    ["Last 24h"] = round(100.0 * hits24h / max(1, total24h), 1),
    ["Last 7d"]  = round(100.0 * hits7d  / max(1, total7d),  1)
```

This is also a `tiles` panel — needs the zero-row guarantee too.

### Root Cause 3: `any()` aggregation — Exception Summary panel

**Current broken query:**

```kql
exceptions
| where timestamp > {timeRange:start}
| summarize Count = count() by ExceptionType = type, ["Message Sample"] = any(outerMessage)
| order by Count desc
| take 10
```

**Error:** `Function 'any' cannot be invoked in current context`

`any()` is a non-deterministic aggregation that is restricted in certain KQL environments
(including some Azure Monitor Workbook query runners). Replace with `take 1` idiom or `min()`:

```kql
exceptions
| where timestamp > {timeRange:start}
| summarize Count = count(), MessageSample = min(outerMessage) by ExceptionType = type
| project ExceptionType, Count, ["Message Sample"] = MessageSample
| order by Count desc
| take 10
```

(`min()` is deterministic and universally supported; it still gives a representative sample.)

---

## Functional Requirements

### All `tiles`-visualised panels must guarantee one row

Apply the zero-row-safe pattern to every panel using `visualization: "tiles"`:

- [ ] Request Volume & Error Rate
- [ ] Response Time Percentiles
- [ ] Availability (health probe) — also fix `countif` predicate (see Root Cause 2)
- [ ] Time to First Token (TTFT)
- [ ] Total LLM Duration
- [ ] Fallback Rate
- [ ] Rate Limit Hits
- [ ] Semantic Search Duration
- [ ] General Query Duration
- [ ] Container Restart Events

### Fix KQL function restriction errors

- [ ] Availability panel: replace `countif(... and timestamp > ago(Xh))` with `extend` + boolean column pattern
- [ ] Exception Summary panel: replace `any(outerMessage)` with `min(outerMessage)`

### Do not break working panels

- [ ] Request Rate Over Time (linechart) — no changes needed, already working
- [ ] Tokens per Second Trend (linechart) — no changes needed, already working
- [ ] Container CPU & Memory Trend (linechart) — no changes needed, already working

---

## Acceptance Criteria

### Panels that show "Could not create tiles" must now render

After opening the dashboard in Azure Portal (any time range):

- [ ] **Request Volume & Error Rate** — shows tile(s) (zeros are acceptable if no traffic)
- [ ] **Response Time Percentiles** — shows tile(s) (zeros acceptable)
- [ ] **Availability (health probe)** — shows tile(s), no function error
- [ ] **Time to First Token (TTFT)** — shows tile(s) (zeros acceptable if no LLM traffic yet)
- [ ] **Total LLM Duration** — shows tile(s) (zeros acceptable)
- [ ] **Fallback Rate** — shows tile(s) (zeros acceptable)
- [ ] **Rate Limit Hits** — shows tile(s) (0 is a valid and expected value)
- [ ] **Semantic Search Duration** — shows tile(s) (zeros acceptable)
- [ ] **General Query Duration** — shows tile(s) (zeros acceptable)
- [ ] **Container Restart Events** — shows tile(s) (0 is a valid and expected value)

### Panels with KQL errors must resolve

- [ ] **Availability (health probe)** — no longer shows "Function 'countif' cannot be invoked in current context"
- [ ] **Exception Summary (top 10 types)** — no longer shows "Function 'any' cannot be invoked in current context"

### Working panels must continue to work

- [ ] Request Rate Over Time still shows data
- [ ] Tokens per Second Trend still shows data (or empty chart if no LLM traffic)
- [ ] Container CPU & Memory Trend still shows data

### Deployment

- [ ] Updated workbook JSON committed to `deployment/azure-monitor/workbook-performance-dashboard.json`
- [ ] Terraform applied successfully (workbook updated in Azure)
- [ ] No regressions in CI (pre-commit, tests all pass)

---

## Non-Functional Requirements

- [ ] **Graceful empty state:** Every `tiles` panel must display zeros (not errors) when there is
  no data in the selected time range
- [ ] **Query correctness:** All KQL queries must be syntactically valid for the Azure Monitor
  Workbook KQL runtime (subset of full KQL — some functions are restricted)
- [ ] **No breaking changes:** Working panels (Request Rate, Tokens/sec, CPU/Memory) must continue
  to work

---

## Tech Constraints

- Workbook JSON file: `deployment/azure-monitor/workbook-performance-dashboard.json`
- Terraform resource: `azurerm_application_insights_workbook.performance_dashboard` in
  `deployment/main.tf`
- Must deploy via `terraform apply` (same pattern as PR #240)
- KQL must use `{timeRange:start}` parameter (not `ago()`) for panels that respect the time picker
- Panels with hardcoded time windows (e.g., Rate Limit Hits at `ago(1h)`, Availability at `ago(7d)`) keep their fixed windows but still need the zero-row fix

## Out of Scope

- Adding new dashboard panels
- Adding alert rules
- Changing metric names or backend instrumentation
- Frontend Web Vitals integration
- Investigating whether custom metrics (LLM, DB) are actually being emitted — the panels should
  show zeros gracefully even if no custom metrics exist yet

---

## Dependencies

- ✅ BITB-021 (PR #239) merged — backend emits metrics
- ✅ Workbook source_id fix (PR #240) merged — dashboard scoped to Application Insights
- ✅ PR #241 merged — further monitoring improvements
- ✅ Application Insights configured and receiving data

---

## Definition of Done

- [ ] All 10 previously-broken `tiles` panels render (zero or real data — no "Could not create tiles")
- [ ] Availability panel: no KQL function error
- [ ] Exception Summary panel: no KQL function error
- [ ] All 3 previously-working panels still work
- [ ] `deployment/azure-monitor/workbook-performance-dashboard.json` updated in source control
- [ ] Terraform applied successfully
- [ ] PR merged, CI green
- [ ] Story marked ✅ Done in backlog
