# BITB-123: Where the Azure Bill Goes — Monitoring (~25%) and Postgres (~50%)

**Status:** 🎯 Todo
**Priority:** P2 — three quarters of the bill sits in two line items nobody has attributed
**Size:** M (the analysis is the deliverable; each fix it authorises is its own small story)
**Created:** 2026-09-12
**Prompted by:** Owner's spend review — "monitoring is ~25% of the cost, the DB is ~50%"

## User Story

**As** the person paying the Azure invoice for a single-region, single-instance side project,
**I want** the monitoring and database spend broken down to the meter and each driver traced to the
Terraform or application line that creates it, **so that** I can cut cost against evidence instead
of guessing which knob is the expensive one.

## Why This Is Not Just "Downsize Things"

The starting numbers are an owner-side estimate, not an invoice reading. Two of them are already in
tension with the configuration:

- `deployment/terraform.tfvars` sets `monthly_budget = 50`, and `deployment/README.md` advertises
  "~$25-40/month" against a **B1ms** database. The server has since been upgraded to
  `B_Standard_B2s` (`deployment/main.tf:405`) and the README was never updated. The published cost
  table is stale and must not be used as the baseline.
- If monitoring is 25% and the database is 50%, then Container Apps (two always-on replicas),
  Container Registry (~$5 Basic), Azure OpenAI embeddings, the Logic App and Key Vault together
  make up the remaining 25%. With `backend_min_replicas = 1` and `frontend_min_replicas = 1`
  (`deployment/terraform.tfvars`) there is no scale-to-zero, so that residual looks small. Either
  the split is different from the estimate or the total is larger than $50. **Phase 0 settles this
  before anything is changed.**

Nothing in Part A or Part B gets implemented on the strength of the estimate. The percentages are
the reason to look; the meter export is the reason to act.

## Phase 0 — Attribution (blocking, do this first)

Per `AGENTS.md` → *Reproducible Repo Analyses*: these numbers do not live in this repo's history, so
the exact commands are cited and their output is pasted into the PR.

```bash
# Full last-3-months cost by meter for the app resource group.
az costmanagement query \
  --type ActualCost \
  --timeframe Custom --time-period from=2026-06-01 to=2026-09-01 \
  --dataset-granularity Monthly \
  --scope "/subscriptions/f5bc5a63-92f8-4ab6-ad94-84673eeebb56/resourceGroups/bible-app-rg" \
  --dataset-aggregation '{"cost":{"name":"Cost","function":"Sum"}}' \
  --dataset-grouping name="ResourceId" type="Dimension" \
  --dataset-grouping name="MeterSubCategory" type="Dimension"
```

Three months, not one: a single month cannot distinguish a standing charge from a one-off
(an HNSW rebuild, a storage auto-grow step, a seeding run).

Then the two ingestion questions that the cost export alone will not answer:

```kusto
// Which tables are actually being paid for, and how much per day.
Usage
| where TimeGenerated > ago(30d) and IsBillable == true
| summarize BillableGB = sum(Quantity) / 1000 by DataType, bin(TimeGenerated, 1d)
| summarize TotalGB = sum(BillableGB) by DataType
| order by TotalGB desc
```

```kusto
// Inside App Insights, which telemetry type dominates.
union requests, dependencies, traces, customMetrics, exceptions, availabilityResults
| where timestamp > ago(7d)
| summarize Records = count() by itemType
| order by Records desc
```

**Exit criterion for Phase 0:** a table of resource → meter → 3-month monthly cost that sums to the
actual invoice, plus the per-`DataType` billable GB. Parts A and B are then re-ranked against that
table, and anything below ~5% of the bill is dropped rather than worked.

---

## Part A — Monitoring

### What the configuration commits us to

| Driver | Evidence | Why it costs |
| --- | --- | --- |
| Log Analytics, pay-per-GB, **no daily cap** | `deployment/main.tf:254-261` — `sku = "PerGB2018"`, `retention_in_days = 30`, no `daily_quota_gb` | Ingestion is unbounded: a log-spewing regression bills without a ceiling |
| All Container Apps console + system logs land in that workspace | `deployment/main.tf:366` — `log_analytics_workspace_id` on the environment, no `logs_destination` override | `ContainerAppConsoleLogs_CL` is typically the largest table in a Container Apps workspace |
| App Insights with **no sampling** | `api/main.py:21-25` — `configure_azure_monitor(connection_string=…, logger_name="bible_app")`; no `sampling_ratio` | The distro defaults to exporting 100% of traces/requests/dependencies |
| 2 availability web tests × 3 geos × every 5 min | `deployment/main.tf:282-350` — `frequency = 300`, three `geo_locations` each | **51,840 executions/month**, each writing an `availabilityResults` record (and a request record at the backend) |
| 32 alert rules — 12 metric, 20 log-query | `deployment/monitoring.tf` | Log search alert rules are billed per rule per month, with evaluation frequency as a multiplier |
| Log-alert evaluation frequency skewed to 5 min | 17 rules at `PT5M`, 3 at `PT15M` | **155,520 KQL evaluations/month** across the 20 rules |
| Logic App (Consumption) + Key Vault for the Telegram bridge | `deployment/monitoring.tf:190-360` | Per-action billing on every alert fan-out; Key Vault per-operation on every token read |

And the overlap worth checking first, because it bills **both** buckets:

| Postgres server parameter | Value | Set at |
| --- | --- | --- |
| `log_connections` | `on` | `deployment/main.tf:531-536` |
| `log_min_duration_statement` | `100` (ms) | `deployment/main.tf:510-515` |
| `log_checkpoints` | `on` | `deployment/main.tf:517-522` |

No `azurerm_monitor_diagnostic_setting` for the Postgres server exists in `deployment/` — grep
returns nothing. **Either** those logs never reach Log Analytics (in which case the parameters are
producing server-side logs nobody reads — cheap, but also useless, and `log_connections` on a
pooled-connection app is noisy), **or** a diagnostic setting was added by hand in the portal and is
Terraform drift silently billing ingestion. `prod-deploy-drift.yml` runs every 15 minutes but checks
deployment drift, not diagnostic-setting drift. Establish which it is — this is the single highest
information-per-minute check in Part A.

### Levers, cheapest-risk first

1. **`daily_quota_gb` on the workspace.** A hard cap, not a saving — it converts an unbounded
   worst case into a bounded one. Set it above observed p99 daily ingestion so normal operation is
   unaffected. **Caveat, and it is the whole decision:** when the cap trips, ingestion stops, which
   means alerts stop. Decide deliberately whether a blind-but-capped day is preferable to an
   uncapped bill, and write the answer down. The Telegram channel in `prod-monitor.yml` is
   independent of Log Analytics and keeps working, which is what makes a cap tolerable.
2. **Sampling in `configure_azure_monitor`.** Adding `sampling_ratio` cuts `requests`/`dependencies`
   ingestion proportionally. The constraint is that the workbook
   (`deployment/azure-monitor/workbook-performance-dashboard.json`) and the p95-latency log alerts
   (`scripture_fetch_latency_p95`, `scripture_search_latency_p95`, `chat_ttft_p95`) compute
   percentiles over these tables. Azure Monitor's sampling writes `itemCount` for reweighting, but
   **every KQL query in the workbook and in those alert rules must be audited** for whether it
   reweights — an unweighted `percentile()` over sampled data is wrong, and quietly so. Sampling is
   only worth doing if that audit is part of it. On a site at this traffic level, check Phase 0
   first: if `requests` is not a top-2 `DataType`, skip this lever entirely.
3. **Table-level Basic plan for the console-log table.** `ContainerAppConsoleLogs_CL` is a
   high-volume, rarely-queried table and Basic-tier ingestion is materially cheaper per GB. Basic
   tables cannot be used by scheduled query rules — so this is only available for tables no alert
   reads. Check every rule in `monitoring.tf` for what it queries before moving any table;
   `backend_errors`, `backend_5xx_rate`, `backend_unhandled_exceptions` and friends read container
   logs, so this may be blocked outright. Establish that, then decide.
4. **Web-test geography.** Three continents for a single-region app serving mostly European users.
   Dropping `us-va-ash-azr` cuts those executions by a third. The counter-argument is real and
   documented: `backend_preflight` exists because of the 2026-07-05 `_IncludedRouter` outage
   (`deployment/main.tf:316-324`) and a third vantage point protects against a single-region false
   positive. Azure recommends ≥3 locations to avoid alerting on network blips. Treat this as
   "re-justify or keep", not "cut".
5. **Alert-rule consolidation.** 20 log-query rules, 17 at 5-minute frequency. Two questions per
   rule: has it ever fired, and does it need 5-minute evaluation? A rule that has never fired in six
   months is either well-designed insurance or dead weight — `AlertsManagementResources` history
   distinguishes them. Moving genuinely non-urgent rules from `PT5M` to `PT15M` reduces the billed
   frequency tier without deleting coverage.

**Explicitly not on the table:** deleting alert rules to save money in a system whose alerting
already has a documented outage in its history (BITB-064, BITB-056). Coverage is removed only when a
rule is shown to be redundant with another, never because it is a line item.

---

## Part B — Database (the ~50%)

### What the configuration commits us to

| Driver | Evidence | Note |
| --- | --- | --- |
| `B_Standard_B2s` — 2 vCore / 4 GB burstable | `deployment/main.tf:405` | Comment claims "~$33/month all-in"; upgraded from B1ms for the migration-007 partial HNSW indexes |
| **No reserved capacity / savings plan** | nothing in `deployment/` | An always-on server paying on-demand rates around the clock |
| `auto_grow_enabled = true`, and storage **never shrinks** | `deployment/main.tf:414`, plus the `lifecycle.ignore_changes = [storage_mb]` block at `:421-437` | Azure grows by doubling (32→64→128 GB). The ratchet is one-way and the declared `storage_mb = 32768` is now fiction — Terraform no longer knows the real size |
| 7-day backups, geo-redundancy off | `deployment/main.tf:410-411` | Already the cheap setting. Backup storage is billed against provisioned size, so the auto-grow ratchet inflates this too |
| One full HNSW index ≈ **2.6 GB** on `verses.embedding` | `scripts/migrations/007_partial_hnsw_verse_indexes.py` docstring | Kept for the no-translation search path |
| Plus one **partial** HNSW index per translation | same migration, built from translations discovered at runtime | Each ≈ 1/12th of the full index; the set roughly doubles the HNSW footprint |
| Two GIN indexes with no reader | BITB-098 | Already written up; strictly a write-amplification and storage cost |
| 1536-dim `vector` (4 bytes/dim) | `azure_embedding_deployment = "text-embedding-3-small"`, `api/config.py:432` | ~6 KB per embedding, before index overhead, over 403,856 verses |

### The question that decides the size of the prize

**What is `storage_mb` actually provisioned at right now?**

```bash
az postgres flexible-server show \
  --resource-group bible-app-rg \
  --name <server-name> \
  --query "{storage:storage.storageSizeGb, tier:sku.tier, sku:sku.name, iops:storage.iops}"
```

```sql
SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size;

SELECT relname,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       pg_size_pretty(pg_indexes_size(relid))        AS indexes
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;

SELECT indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;

SELECT stats_reset FROM pg_stat_database WHERE datname = current_database();
```

If the disk auto-grew to 64 GB while the data is ~10 GB, a large slice of the database line is
paying for empty space that **cannot be reclaimed on this server** — shrinking a Flexible Server
disk requires a dump/restore onto a new server. That changes what the right fix is, so establish it
before proposing anything. Capture `stats_reset` alongside `idx_scan`: a zero scan count over two
days means much less than one over two months (the point BITB-098 makes).

### Levers, cheapest-risk first

1. **Reserved capacity (1-year, Flexible Server compute).** No architectural change, no downtime, no
   code. It is the only lever here with zero engineering risk, and on an always-on server it is
   normally the largest single reduction. The commitment is the trade: verify against the roadmap
   that a B2s in North Europe is still the shape of this system in twelve months. If a tier change
   is plausible, price the reservation *after* deciding the tier, not before — buying a reservation
   for a SKU you then leave is the one way this lever loses money.
2. **Right-size on measured utilisation, in that order.** Pull 90 days of `cpu_percent`,
   `memory_percent` and `storage_percent` from Azure Monitor. B-series is burstable — sustained CPU
   above the baseline credit rate is a reason to go *up* to a General Purpose tier, not down, and
   the alert thresholds in `monitoring.tf:812-890` say what the system already expects. The B2s was
   a deliberate upgrade from B1ms so the per-translation partial indexes stay cached
   (`deployment/main.tf:399-404`). Reversing that without first shrinking the index footprint
   (lever 3) would trade money for the search latency this project has repeatedly paid to fix.
   **Down-sizing is the last lever considered, not the first.**
3. **Halve the vector footprint with `halfvec`.** pgvector's `halfvec` stores 2 bytes per dimension
   instead of 4, at a recall cost that is small-to-negligible for cosine ANN at 1536 dims. Applied to
   `verses.embedding` it roughly halves both the stored vectors and every HNSW index built over them
   — the full ~2.6 GB index and the whole per-translation partial set. That is the one change that
   attacks storage **and** memory pressure at once, and it is what makes a B1ms conversation
   possible later. It is also the most invasive: a column type change plus a full index rebuild over
   403,856 rows, which is exactly the shape of the 2026-08-17 outage. `CONCURRENTLY`,
   `lock_timeout`, and the rules in `docs/MIGRATION_GUIDELINES.md` are mandatory, and recall must be
   measured against the golden set (`docs/GOLDEN_SET_GUIDE.md`) before and after. **This is a
   separate story if the analysis justifies it — do not let it ride along in the analysis PR.**
4. **Retire indexes with no readers.** BITB-098 is already written for the two `_english` GIN
   indexes. This analysis adds one question to it: now that migration 007's partial indexes exist,
   does the no-translation search path still justify keeping the full ~2.6 GB
   `idx_verse_embedding_hnsw`? `pg_stat_user_indexes.idx_scan` answers it. If that path is
   effectively dead, this is the largest single storage reclaim available and it needs no type
   change — but it only converts to money if the disk can shrink, which loops back to the auto-grow
   finding above.
5. **Turn off `log_connections`.** Cheap on the database, possibly not cheap on ingestion — see the
   overlap table in Part A. Decide it there, once, rather than in both places.

---

## Out of Scope

- **Compute (Container Apps) and ACR.** The other ~25%. `min_replicas = 1` on both apps means the
  advertised scale-to-zero is not in use, which is very likely deliberate (cold starts on a chat
  UI). Worth its own story; not this one.
- **OpenRouter / LLM inference spend.** Not an Azure meter and not in the 25/50 split.
- **Switching cloud, region, or database vendor.** The question asked is how to spend less on what
  exists, not what to replace it with.
- **Implementing `halfvec`, buying the reservation, or dropping any index.** This story produces the
  evidence and the ranked recommendation. Each accepted recommendation becomes its own story with
  its own acceptance criteria — that separation is the point, because the migration-shaped ones
  carry outage risk and must not be reviewed as a footnote to a spreadsheet.

## Acceptance Criteria

- [ ] Phase 0 cost table (resource → meter → monthly cost, 3 months) pasted into the PR, with the
      exact `az` command that produced it, and reconciled against the actual invoice total
- [ ] The 25% / 50% estimate is either confirmed or corrected, in writing, against that table
- [ ] Log Analytics billable GB per `DataType` (30 days) captured; the top 3 tables named
- [ ] App Insights record counts by `itemType` (7 days) captured
- [ ] **Resolved:** whether a Postgres diagnostic setting exists outside Terraform, and if so whether
      it is drift to codify or ingestion to remove
- [ ] Actual provisioned `storage_mb`, database size, and the top 10 tables/indexes by size captured
      from production, with `stats_reset` recorded alongside `idx_scan`
- [ ] 90 days of `cpu_percent` / `memory_percent` / `storage_percent` captured for the server
- [ ] Alert-rule firing history pulled; every rule classified as *fired*, *never fired — keep as
      insurance*, or *never fired — redundant with <rule>*
- [ ] Each lever in Parts A and B carries an estimated monthly saving **derived from the Phase 0
      table**, not from list prices, and an explicit risk note
- [ ] Levers ranked by saving ÷ risk, with an explicit recommendation on which to do and which to
      decline; declined ones say why, so this is not re-litigated in six months
- [ ] A follow-up story is filed for each accepted lever that changes schema, indexes, sampling, or
      SKU — none of them are implemented in this story's PR
- [ ] `deployment/README.md`'s cost table corrected (it still says B1ms and "~$25-40/month") or
      replaced with a pointer to the Phase 0 output, so the next reader is not misled by it
- [ ] `monthly_budget` in `deployment/terraform.tfvars` reviewed against the real total — if actual
      spend exceeds it, the budget alert at 80% has been firing or is about to, and that is either
      a number to raise or a spend to cut

## Related

- BITB-098 — the two unread GIN indexes; a component of Part B lever 4, already scoped
- BITB-056 — added the Telegram Logic App bridge, storage auto-grow, and several of the log alerts
- BITB-064 — why the second (preflight) availability web test exists; the cost of removing it
- `deployment/main.tf` — workspace `:254`, App Insights `:268`, web tests `:282`/`:316`, Postgres
  `:389`, server parameters `:480-537`, budget `:1132`
- `deployment/monitoring.tf` — all 32 alert rules, the action group, and the Logic App bridge
- `api/main.py:15-32` — the `configure_azure_monitor` call with no sampling configured
- `scripts/migrations/007_partial_hnsw_verse_indexes.py` — the ~2.6 GB index figure and the
  per-translation partial index set
- `docs/MIGRATION_GUIDELINES.md`, `docs/RETROSPECTIVES/2026-08-17-tsvector-migration-outage.md` —
  binding on anything that rebuilds an index on `verses`
- `AGENTS.md` → *Reproducible Repo Analyses* — why every number above is cited with its command
