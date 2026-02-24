# Azure Monitor Workbook — Performance Dashboard

Visual performance dashboard for the **getinspiredbythebible** Bible Chat application,
deployed as an Azure Monitor Workbook via Terraform.

## Overview

The dashboard consolidates five monitoring areas into a single view, giving on-call
engineers an instant read on application health without switching between multiple
Azure Portal blades.

| Panel | Focus | Key signals |
|-------|-------|-------------|
| 📊 Overview | Error detection | Error rate %, response-time percentiles, availability |
| 🤖 LLM Performance | AI provider health | TTFT, total duration, tokens/sec, fallback rate |
| 🗄️ Database Performance | pgvector query health | Search/query duration P50–P99, slow-query trend |
| 🚨 Error Analysis | Root-cause investigation | Error breakdown, slowest requests, failed requests, exceptions |
| 🖥️ Infrastructure | Container health | CPU/memory trend, restart events |

---

## Prerequisites

- **Application Insights enabled**: `enable_application_insights = true` in `terraform.tfvars`
- Terraform `azurerm` provider `~> 3.80` (already pinned in `deployment/main.tf`)
- The backend API must be instrumented with the OpenTelemetry stack from PRs B1–B4

---

## How to Deploy

The workbook resource is defined directly in `deployment/main.tf` and is therefore
deployed as part of the standard Terraform workflow. No extra steps needed.

```bash
# From repo root — always use Makefile targets
make tf-plan    # preview: should show azurerm_application_insights_workbook.performance_dashboard[0]
make tf-apply   # deploy
```

After a successful apply, the workbook Portal URL is printed as a Terraform output:

```bash
make tf-output
# workbook_portal_url = "https://portal.azure.com/#resource/.../workbook"
```

---

## How to Access in the Azure Portal

1. Open the **workbook_portal_url** from `make tf-output`, **or**
2. Navigate manually:
   - Azure Portal → **Resource Groups** → `bible-app-rg`
   - Select the Application Insights resource (`bible-app-insights`)
   - Left sidebar → **Workbooks**
   - Open **"bible-app - Performance Dashboard"**

---

## Panel-by-Panel Interpretation Guide

### 📊 Overview — Error Detection

**Request Volume & Error Rate** (tile)

The most important single number: `Error Rate %`. Use the colour thresholds as a
triage signal:

| Value | Colour | Action |
|-------|--------|--------|
| < 5 % | 🟢 Green | Normal |
| 5–10 % | 🟡 Yellow | Investigate; check LLM fallbacks and DB slow queries |
| > 10 % | 🔴 Red | Incident response; page on-call |

**Response Time Percentiles** (tile)

P50 represents the typical user experience; P95 and P99 reveal tail latency.
High P99 with low P50 usually points to one of:

- LLM provider throttling a subset of requests
- Database index misses on cold-start queries

**Availability** (tile, always fixed 7-day window)

Driven by the automated health-check web test (`/health/ready` endpoint, 5-minute
cadence from 3 Azure regions). Zero recent data means the web test is not yet
deployed — check `enable_application_insights` and re-run `make tf-apply`.

| Value | Colour | Meaning |
|-------|--------|---------|
| ≥ 99 % | 🟢 Green | SLA target met |
| 95–99 % | 🟡 Yellow | Degraded; investigate container restarts or probe timeouts |
| < 95 % | 🔴 Red | Significant outage; container may be crash-looping |

**Request Rate Over Time** (line chart)

Baseline traffic pattern. Use this to distinguish:

- **Traffic spike causing degradation** → scale-out may be needed
- **Low traffic but high error rate** → systematic error, not capacity

---

### 🤖 LLM Performance

**Time to First Token (TTFT)** (tile)

Streaming latency before the first token appears in the UI. Directly impacts
perceived responsiveness.

| P95 value | Colour | Action |
|-----------|--------|--------|
| < 3 000 ms | 🟢 Green | Healthy |
| 3 000–10 000 ms | 🟡 Yellow | Provider may be under load; monitor fallback rate |
| > 10 000 ms | 🔴 Red | Switch primary model or increase fallback aggressiveness |

**Total LLM Duration** (tile)

End-to-end generation time including all streamed tokens. High values with low
TTFT usually mean the model is generating very long responses.

**Fallback Rate** (tile)

| Value | Colour | Action |
|-------|--------|--------|
| < 5 % | 🟢 Green | Primary model healthy |
| 5–10 % | 🟠 Orange | Primary model occasionally rate-limited |
| > 10 % | 🔴 Red | Consider switching primary model or upgrading plan |

**Rate Limit Hits** (tile, always last 1 h)

Raw count of HTTP 429 responses from the LLM provider. A sudden spike here
correlates with a TTFT spike and rising fallback rate.

**Tokens per Second Trend** (line chart, always last 24 h)

Generation throughput. A downward trend overnight may indicate the free tier
is nearing daily limits.

---

### 🗄️ Database Performance

**Semantic Search Duration** (tile)

pgvector cosine-similarity query timing. The HNSW index (added in PR #182)
should keep P95 below 100 ms under normal load.

| P95 value | Action |
|-----------|--------|
| < 100 ms | Healthy |
| 100–500 ms | Check index; `EXPLAIN ANALYSE` the vector query |
| > 500 ms | Index may be missing or DB under heavy memory pressure |

**General Query Duration** (tile)

Non-vector SQL queries (lookup by book/chapter/verse). P95 > 200 ms on simple
lookups usually indicates connection-pool exhaustion.

**Slow Query Count Trend** (line chart)

Queries exceeding 100 ms, bucketed hourly. A step-change up after a deployment
suggests a regression introduced by a schema or query change.

---

### 🚨 Error Analysis

**Error Count by Type** (pie chart)

- **Dominated by 4xx**: Likely a client-side issue (bad request format, auth
  failure, Turnstile rejection). Review frontend validation.
- **Dominated by 5xx**: Server-side failure — check LLM connectivity and DB.
- **Dominated by Timeout**: Either LLM taking too long or DB connection stalled.

**Top 10 Slowest Requests** (table)

Shows the `Correlation ID` for each outlier. Use it to drill down:

1. Copy the **Correlation ID** value from the table.
2. In Application Insights, go to **Transaction search**.
3. Paste the ID in the search box.
4. Open the matching request to see the full span tree
   (LLM call, DB query, correlation headers).

**Failed Requests with Details** (table)

The last 50 failures. The **Error** column contains the exception message
captured via the correlation-ID middleware (PR B1).

**Exception Summary** (table)

Top 10 exception types by frequency. Use this after deployments to quickly
spot new exception classes introduced by code changes.

---

### 🖥️ Infrastructure

**Container CPU & Memory Trend** (line chart)

5-minute averages from the `performanceCounters` table (requires the App
Insights SDK agent to be active inside the container).

| Resource | Threshold | Action |
|----------|-----------|--------|
| CPU | > 80 % sustained | Scale up or add replicas |
| Memory (backend) | > 900 MB | Near 1 GiB limit; check for leaks |
| Memory (frontend) | > 450 MB | Near 0.5 GiB limit |

**Container Restart Events** (tile, always last 1 h)

Any non-zero value in a stable production window warrants investigation.
Common causes:

- OOM kill (memory exceeding container limit)
- Liveness probe failure (app deadlocked)
- Crash-loop due to unhandled startup error

---

## Alert Thresholds Reference

| Metric | 🟢 Green | 🟡 Yellow | 🟠 Orange | 🔴 Red |
|--------|----------|-----------|-----------|--------|
| Error Rate % | < 5 % | 5–10 % | — | > 10 % |
| Availability (1 h) | ≥ 99 % | 95–99 % | — | < 95 % |
| TTFT P95 | < 3 000 ms | 3 000–10 000 ms | — | > 10 000 ms |
| Fallback Rate % | < 5 % | — | 5–10 % | > 10 % |
| Request Duration P95 | < 5 000 ms | 5 000–15 000 ms | — | > 15 000 ms |
| DB Search P95 | < 100 ms | 100–500 ms | — | > 500 ms |

---

## Drill-Down Guide: Metric → Trace

### Scenario: Error Rate spike

1. Open **Overview** panel → note the **Error Rate %** and time window.
2. Scroll to **Error Analysis** → **Error Count by Type** pie chart.
   - If 5xx: proceed to **Failed Requests with Details** table.
   - If 4xx: check frontend logs for malformed requests.
3. Pick a failed request row → copy **Correlation ID**.
4. Go to **Application Insights** → **Transaction search** → paste ID.
5. Open the matching request → expand spans:
   - `db.search` span: database query time
   - `llm.chat` span: LLM provider call, includes TTFT and total duration
6. If `llm.chat` span is missing but error exists: LLM provider returned an error
   before streaming; check **Rate Limit Hits** tile in LLM Performance panel.

### Scenario: High TTFT

1. Open **LLM Performance** → **Time to First Token** tile.
2. If P95 > 3 000 ms, check **Fallback Rate** tile.
   - High fallback rate: primary model is throttled. Consider enabling a faster
     paid fallback in `openrouter_fallback_models`.
   - Low fallback rate: latency is coming from the primary model itself;
     check OpenRouter status page.
3. Cross-reference **Tokens per Second Trend** — if TPS has also dropped,
   the provider is under global load.

### Scenario: DB slow queries

1. Open **Database Performance** → **Slow Query Count Trend**.
2. If the count is rising, check **Semantic Search P95**.
3. If search P95 > 100 ms, the HNSW index may have been dropped or is stale.
4. Connect to the database and run:

   ```sql
   SELECT schemaname, tablename, indexname
   FROM pg_indexes
   WHERE indexname LIKE '%hnsw%';
   ```

5. If no HNSW index exists, re-create it from the migrations.

---

## Dashboard Layout (ASCII)

```text
┌─────────────────────────────────────────────────────────────┐
│ Time Range: [1h] [6h] [24h] [7d] [30d]                     │
│ Quick Actions: App Insights | Live Metrics | Alerts | Logs  │
├─────────────────────────────────────────────────────────────┤
│ 📊 OVERVIEW                                                  │
│  ┌──────────────────┐ ┌──────────────────┐ ┌─────────────┐ │
│  │ Total Requests   │ │ P50 / P95 / P99  │ │ Avail 1h/   │ │
│  │ 5xx Errors       │ │ Response (ms)    │ │ 24h / 7d    │ │
│  │ Error Rate %  🔴 │ │                  │ │           🟢│ │
│  └──────────────────┘ └──────────────────┘ └─────────────┘ │
│  [Request Rate Line Chart]                                   │
├─────────────────────────────────────────────────────────────┤
│ 🤖 LLM PERFORMANCE                                           │
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌────────┐ │
│  │ TTFT       │ │ Duration   │ │ Fallback Rate│ │ Rate   │ │
│  │ P50/P95/P99│ │ P50/P95/P99│ │ Count / %  🟠│ │ Limits │ │
│  └────────────┘ └────────────┘ └──────────────┘ └────────┘ │
│  [Tokens/sec Line Chart (24h)]                               │
├─────────────────────────────────────────────────────────────┤
│ 🗄️ DATABASE PERFORMANCE                                      │
│  ┌──────────────────────┐ ┌──────────────────────┐          │
│  │ Search P50/P95/P99   │ │ Query P50/P95/P99    │          │
│  └──────────────────────┘ └──────────────────────┘          │
│  [Slow Query Count Line Chart]                               │
├─────────────────────────────────────────────────────────────┤
│ 🚨 ERROR ANALYSIS                                            │
│  [Error Type Pie]   [Top 10 Slowest Requests Table]          │
│  [Failed Requests Table]   [Exception Summary Table]         │
├─────────────────────────────────────────────────────────────┤
│ 🖥️ INFRASTRUCTURE                                            │
│  [CPU / Memory Line Chart]   ┌──────────────────┐           │
│                              │ Restarts (last 1h)│           │
│                              └──────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```
