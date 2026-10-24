# BITB-150 Cost Analysis Report — Phase 0 Evidence

**Branch:** `feature/bitb-150-cost-analysis`
**Date:** 2026-10-21
**Status:** Phase 0 Data Collection — Commands documented, awaiting execution with Azure credentials

---

## Executive Summary

This report documents the commands and queries required to perform Phase 0 of BITB-150: attribution of actual Azure spend to meters and drivers. The 25% monitoring / 50% database estimate from the owner's spend review must be confirmed or corrected against real invoice data before any optimisation is proposed.

**No changes are implemented in this phase.** Each accepted lever becomes its own story with its own acceptance criteria.

---

## Phase 0 Commands — Exact, Reproducible, Cited

### 1. Azure Cost Management — 3-Month Meter-Level Breakdown

> **Correction (2026-10-22):** the story's original command, `az costmanagement
> query`, **does not exist** — the `costmanagement` CLI extension only ships
> `export` subcommands (verified against the MS Learn CLI reference). The
> equivalent supported CLI path is the Cost Management **Query API** via native
> `az rest`, which is what `scripts/collect_cost_evidence.py|.sh` run. The
> window below is computed dynamically at run time (last 3 full months).

```bash
# Full last-3-months cost by meter for the app resource group.
# Run from a shell with `az login` and the correct subscription selected.
az rest --method post \
  --uri "/subscriptions/f5bc5a63-92f8-4ab6-ad94-84673eeebb56/resourceGroups/bible-app-rg/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body '{
    "type": "ActualCost",
    "timeframe": "Custom",
    "timePeriod": {"from": "2026-07-01", "to": "2026-09-30"},
    "dataset": {
      "granularity": "Monthly",
      "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
      "grouping": [
        {"name": "ResourceId", "type": "Dimension"},
        {"name": "MeterSubCategory", "type": "Dimension"}
      ]
    }
  }'
```

**Expected output:** `properties.rows` — `ResourceId` × `MeterSubCategory` × monthly cost (3 months) — that sums to the actual invoice total. The collectors store this raw response in `01-cost-by-resource-meter.json`.

**Output location:** Paste JSON/CSV output here → **[PHASE 0 COST TABLE — PASTE HERE]**

---

### 2. Log Analytics — Billable GB per DataType (30 Days)

```kusto
// Which tables are actually being paid for, and how much per day.
// Run in the Log Analytics workspace associated with bible-app-rg.
Usage
| where TimeGenerated > ago(30d) and IsBillable == true
| summarize BillableGB = sum(Quantity) / 1000 by DataType, bin(TimeGenerated, 1d)
| summarize TotalGB = sum(BillableGB) by DataType
| order by TotalGB desc
```

**Output location:** Paste results here → **[LOG ANALYTICS BILLABLE GB — PASTE HERE]**

**Top 3 tables by billable GB:**

1. _______________ — ___ GB
2. _______________ — ___ GB
3. _______________ — ___ GB

---

### 3. Application Insights — Record Counts by itemType (7 Days)

```kusto
// Inside App Insights, which telemetry type dominates.
union requests, dependencies, traces, customMetrics, exceptions, availabilityResults
| where timestamp > ago(7d)
| summarize Records = count() by itemType
| order by Records desc
```

**Output location:** Paste results here → **[APP INSIGHTS RECORD COUNTS — PASTE HERE]**

---

### 4. PostgreSQL Diagnostic Setting — Drift Check

```bash
# Check for any diagnostic setting on the PostgreSQL Flexible Server
az monitor diagnostic-settings list \
  --resource /subscriptions/f5bc5a63-92f8-4ab6-ad94-84673eeebb56/resourceGroups/bible-app-rg/providers/Microsoft.DBforPostgreSQL/flexibleServers/bible-app-mb0172
```

**Expected:** Either empty (no diagnostic setting = server logs not ingested, `log_connections`/`log_min_duration_statement`/`log_checkpoints` are no-op) or a setting that was created manually in the portal (Terraform drift).

**Output location:** Paste results here → **[POSTGRES DIAGNOSTIC SETTING — PASTE HERE]**

**Resolution:** _______________________________________________________________________

---

### 5. PostgreSQL — Provisioned Storage, DB Size, Top Tables/Indexes

```bash
# Provisioned storage and SKU from Azure
az postgres flexible-server show \
  --resource-group bible-app-rg \
  --name bible-app-mb0172 \
  --query "{storage:storage.storageSizeGb, tier:sku.tier, sku:sku.name, iops:storage.iops}"
```

```sql
-- Database size
SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size;

-- Top 10 tables by total size (data + indexes + toast)
SELECT relname,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       pg_size_pretty(pg_indexes_size(relid))        AS indexes
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;

-- All indexes by size, with scan counts and stats reset timestamp
SELECT indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;

-- When were statistics last reset? (Critical for interpreting idx_scan)
SELECT stats_reset FROM pg_stat_database WHERE datname = current_database();
```

**Output location:** Paste all results here → **[POSTGRES STORAGE & INDEXES — PASTE HERE]**

**Key findings:**

- Provisioned storage: ___ GB
- Actual database size: ___ GB
- Top table: _______________ — ___ GB
- Top index: _______________ — ___ GB
- `stats_reset`: _______________
- Indexes with `idx_scan = 0`: _______________________________________________

---

### 6. PostgreSQL — 90 Days CPU / Memory / Storage Utilisation

```bash
# Pull metrics from Azure Monitor for the PostgreSQL server
# CPU percentage
az monitor metrics list \
  --resource /subscriptions/f5bc5a63-92f8-4ab6-ad94-84673eeebb56/resourceGroups/bible-app-rg/providers/Microsoft.DBforPostgreSQL/flexibleServers/bible-app-mb0172 \
  --metric cpu_percent \
  --interval PT1H \
  --start-time 2026-07-01T00:00:00Z \
  --end-time 2026-10-01T00:00:00Z \
  --aggregation Average Maximum

# Memory percentage
az monitor metrics list \
  --resource /subscriptions/f5bc5a63-92f8-4ab6-ad94-84673eeebb56/resourceGroups/bible-app-rg/providers/Microsoft.DBforPostgreSQL/flexibleServers/bible-app-mb0172 \
  --metric memory_percent \
  --interval PT1H \
  --start-time 2026-07-01T00:00:00Z \
  --end-time 2026-10-01T00:00:00Z \
  --aggregation Average Maximum

# Storage percentage
az monitor metrics list \
  --resource /subscriptions/f5bc5a63-92f8-4ab6-ad94-84673eeebb56/resourceGroups/bible-app-rg/providers/Microsoft.DBforPostgreSQL/flexibleServers/bible-app-mb0172 \
  --metric storage_percent \
  --interval PT1H \
  --start-time 2026-07-01T00:00:00Z \
  --end-time 2026-10-01T00:00:00Z \
  --aggregation Average Maximum
```

**Output location:** Paste summarised results (p50, p95, max) here → **[POSTGRES UTILISATION — PASTE HERE]**

---

### 7. Alert Rules — Firing History Classification

```bash
# Get firing history for all alert rules in the resource group
# This requires querying the AlertsManagementResources table in Log Analytics
# or using the Azure REST API for alert history
```

**Manual classification table (to be filled after data collection):**

| Alert Rule | Type | Frequency | Fired in last 6 months? | Classification |
|------------|------|-----------|------------------------|----------------|
| backend_availability | metric | PT5M | | |
| backend_preflight_availability | metric | PT5M | | |
| backend_restarts | metric | PT5M | | |
| db_cpu | metric | PT5M | | |
| db_memory | metric | PT5M | | |
| db_storage | metric | PT5M | | |
| db_connections_failed | metric | PT5M | | |
| backend_cpu_high | metric | PT5M | | |
| backend_memory_high | metric | PT5M | | |
| backend_replicas_at_max | metric | PT5M | | |
| frontend_cpu_high | metric | PT5M | | |
| frontend_memory_high | metric | PT5M | | |
| backend_probe_failures | log | PT5M | | |
| backend_errors | log | PT5M | | |
| backend_error_rate_other | log | PT5M | | |
| scripture_fetch_errors | log | PT5M | | |
| scripture_grounding_errors | log | PT5M | | |
| scripture_pipeline_errors | log | PT5M | | |
| chat_verseless_responses | log | PT5M | | |
| scripture_fetch_latency_p95 | log | PT5M | | |
| scripture_search_latency_p95 | log | PT5M | | |
| verse_grounding_paraphrase_brackets | log | PT5M | | |
| embedding_fallback_rate | log | PT5M | | |
| rate_limiter_fail_closed | log | PT5M | | |
| backend_5xx_rate | log | PT5M | | |
| backend_unhandled_exceptions | log | PT5M | | |
| backend_asgi_exceptions | log | PT5M | | |
| backend_client_rejection_spike | log | PT5M | | |
| frontend_client_errors | log | PT5M | | |
| content_safety_fallback_rate | log | PT5M | | |
| llama_guard_primary_failure_rate | log | PT5M | | |
| chat_ttft_p95 | log | PT5M | | |

**Classification values:** `fired` / `never fired — keep as insurance` / `never fired — redundant with <rule>`

---

## Phase 0 Exit Criteria — Checklist

- [ ] Phase 0 cost table (resource → meter → monthly cost, 3 months) pasted above, with the exact `az` command that produced it, and reconciled against the actual invoice total
- [ ] The 25% / 50% estimate is either confirmed or corrected, in writing, against that table
- [ ] Log Analytics billable GB per `DataType` (30 days) captured; the top 3 tables named
- [ ] App Insights record counts by `itemType` (7 days) captured
- [ ] **Resolved:** whether a Postgres diagnostic setting exists outside Terraform, and if so whether it is drift to codify or ingestion to remove
- [ ] Actual provisioned `storage_mb`, database size, and the top 10 tables/indexes by size captured from production, with `stats_reset` recorded alongside `idx_scan`
- [ ] 90 days of `cpu_percent` / `memory_percent` / `storage_percent` captured for the server
- [ ] Alert-rule firing history pulled; every rule classified as *fired*, *never fired — keep as insurance*, or *never fired — redundant with <rule>*

---

## Lever Analysis — To Be Completed After Phase 0

*Each lever below must carry an estimated monthly saving derived from the Phase 0 table (not list prices) and an explicit risk note. Levers ranked by saving ÷ risk.*

### Part A — Monitoring Levers

| # | Lever | Phase 0 Evidence | Est. Monthly Saving | Risk Note | Recommendation |
|---|-------|------------------|---------------------|-----------|----------------|
| 1 | `daily_quota_gb` on workspace | | | Cap converts unbounded worst case to bounded; ingestion stops when cap trips (alerts stop). Telegram bridge independent. | |
| 2 | Sampling in `configure_azure_monitor` | | | Requires KQL audit of workbook + p95 alert rules for `itemCount` reweighting. Only worth it if `requests` is top-2 DataType. | |
| 3 | Table-level Basic plan for `ContainerAppConsoleLogs_CL` | | | Basic tables cannot be used by scheduled query rules. Check all 20 log rules for what they query. | |
| 4 | Web-test geography (drop `us-va-ash-azr`) | | | Cuts executions by 1/3. Counter-argument: 3 geos protects against single-region false positive. | |
| 5 | Alert-rule consolidation (PT5M → PT15M) | | | 17 rules at PT5M. Moving non-urgent rules reduces billed frequency tier. Check firing history. | |

### Part B — Database Levers

| # | Lever | Phase 0 Evidence | Est. Monthly Saving | Risk Note | Recommendation |
|---|-------|------------------|---------------------|-----------|----------------|
| 1 | Reserved capacity (1-year, B2s compute) | | | Zero engineering risk, no downtime. Commitment trade: verify B2s in North Europe is still shape in 12 months. | |
| 2 | Right-size on measured utilisation | | | B-series is burstable. Sustained CPU above baseline → go UP to General Purpose, not down. B2s was deliberate for partial index caching. | |
| 3 | `halfvec` for `verses.embedding` | | | Halves vector + HNSW footprint (~2.6 GB full index + partial set). Column type change + full index rebuild over 403,856 rows. `CONCURRENTLY`, `lock_timeout`, recall measured against golden set. | |
| 4 | Retire indexes with no readers (BITB-098 + full HNSW) | | | `idx_scan` from Phase 0. If no-translation path dead, full ~2.6 GB index reclaimable. Only converts to money if disk can shrink. | |
| 5 | Turn off `log_connections` | | | Cheap on DB, possibly not cheap on ingestion. Decide in Part A overlap table. | |

---

## Follow-Up Stories — To Be Filed After Analysis

*Each accepted lever that changes schema, indexes, sampling, or SKU becomes its own story. None implemented in this story's PR.*

- [ ] Story for `daily_quota_gb` implementation
- [ ] Story for sampling + KQL audit
- [ ] Story for Basic table migration (if viable)
- [ ] Story for web-test geography change
- [ ] Story for alert rule frequency changes
- [ ] Story for reserved capacity purchase
- [ ] Story for `halfvec` migration (schema + index rebuild)
- [ ] Story for index retirement (BITB-098 + full HNSW)
- [ ] Story for `log_connections` change

---

## Documentation Updates — To Be Done in This PR

- [ ] `deployment/README.md` cost table corrected (currently says B1ms and "~$25-40/month") or replaced with a pointer to the Phase 0 output
- [ ] `monthly_budget` in `deployment/terraform.tfvars` reviewed against real total — if actual spend exceeds it, the budget alert at 80% has been firing or is about to, and that is either a number to raise or a spend to cut

---

## Appendix — Terraform Resource Mapping (Verified 2026-10-21)

| Logical Name | Terraform Resource | Resource Type |
|--------------|-------------------|---------------|
| Log Analytics Workspace | `azurerm_log_analytics_workspace.main` | `Microsoft.OperationalInsights/workspaces` |
| App Insights | `azurerm_application_insights.main[0]` | `Microsoft.Insights/components` |
| Web Test: backend_availability | `azurerm_application_insights_standard_web_test.backend_availability[0]` | `Microsoft.Insights/webtests` |
| Web Test: backend_preflight | `azurerm_application_insights_standard_web_test.backend_preflight[0]` | `Microsoft.Insights/webtests` |
| PostgreSQL Flexible Server | `azurerm_postgresql_flexible_server.main` | `Microsoft.DBforPostgreSQL/flexibleServers` |
| Container App Environment | `azurerm_container_app_environment.main` | `Microsoft.App/managedEnvironments` |
| Container App: backend | `azurerm_container_app.backend` | `Microsoft.App/containerApps` |
| Container App: frontend | `azurerm_container_app.frontend` | `Microsoft.App/containerApps` |
| Logic App: telegram_alert | `azurerm_logic_app_workflow.telegram_alert[0]` | `Microsoft.Logic/workflows` |
| Key Vault: alerts | `azurerm_key_vault.alerts` | `Microsoft.KeyVault/vaults` |
| Metric Alerts | 12 × `azurerm_monitor_metric_alert` | `Microsoft.Insights/metricAlerts` |
| Log Alerts | 20 × `azurerm_monitor_scheduled_query_rules_alert_v2` | `Microsoft.Insights/scheduledQueryRules` |

---

## Notes for the Data Collector

1. **Authentication:** All `az` commands require `az login` with a service principal or user account that has `Microsoft.CostManagement/exports/read` and `Microsoft.Insights/metrics/read` on the subscription/resource group.

2. **Time periods:** The cost query uses `from=2026-07-01 to=2026-10-01` (3 full months). Adjust if running at a different date.

3. **PostgreSQL connection:** The SQL queries require a connection to the production database. Use the connection string from Terraform output or the `DATABASE_URL` secret.

4. **Log Analytics workspace ID:** The workspace name is dynamically created. Use the query in `prod-monitor.yml` (lines 330-337) to resolve it programmatically.

5. **KQL queries:** Run in the Azure Portal → Log Analytics workspace → Logs, or via `az monitor log-analytics query`.

6. **Alert history:** The `AlertsManagementResources` table in Log Analytics contains firing history. Query it with a 6-month window.

7. **Output format:** Paste raw command output (JSON/CSV) into the report. Do not summarise until the verification step.

---

*End of Phase 0 Report Template. Fill in all **[PASTE HERE]** sections after command execution.*
