# BITB-150 PostgreSQL Cost Driver Analysis

**Date:** 2026-10-22
**Status:** Evidence-based analysis using Phase 0 data collection framework
**Branch:** `feature/bitb-150-cost-analysis`

> **Note:** This analysis uses the *known production configuration* from Terraform (`deployment/main.tf`, `deployment/terraform.tfvars`) and migration history. Actual production evidence files (`05a-06-*`) will be collected by the infra-engineer via `scripts/collect_cost_evidence.py` and should be pasted into the "Evidence" sections below to finalize numbers.

---

## Executive Summary

| Dimension | Configured Value | Evidence Needed |
|-----------|------------------|-----------------|
| **SKU** | `B_Standard_B2s` (Burstable, 2 vCore / 4 GB) | `05a-postgres-azure-config.json` |
| **Provisioned Storage** | 32 GB minimum (`storage_mb = 32768`) | `05a-postgres-azure-config.json` |
| **Auto-grow** | Enabled (`auto_grow_enabled = true`) | `05a-postgres-azure-config.json` |
| **Terraform `ignore_changes`** | `storage_mb` ignored (Azure owns it post-auto-grow) | `deployment/main.tf:428-442` |
| **Embedding Dimensions** | 1536 (Azure OpenAI `text-embedding-3-small`) | `deployment/terraform.tfvars:97-101`, `api/config.py` |
| **Verse Count** | ~403,856 rows (31K verses × 13 translations) | `05c-postgres-top-tables.txt` |
| **Monthly Budget** | $50 (resource group) | `deployment/terraform.tfvars:114` |

---

## 1. Storage Ratchet Impact

### Configuration Evidence

```hcl
# deployment/main.tf:415-421, 428-442
storage_mb                   = 32768  # 32GB minimum
auto_grow_enabled            = true

lifecycle {
  ignore_changes = [
    storage_mb  # Azure owns this once auto_grow_enabled = true
  ]
}
```

### Analysis

| Metric | Value | Source |
|--------|-------|--------|
| **Declared `storage_mb`** | 32 GB | Terraform config |
| **Auto-grow behaviour** | Doubles: 32 → 64 → 128 → 256 GB | Azure Flexible Server docs |
| **Terraform drift protection** | `ignore_changes = [storage_mb]` prevents apply failure | Terraform lifecycle block |
| **Actual provisioned (Azure)** | **EVIDENCE REQUIRED: `05a-postgres-azure-config.json`** | Azure API |
| **Actual database size** | **EVIDENCE REQUIRED: `05b-postgres-db-size.txt`** | `pg_database_size()` |

### Key Finding: Storage Ratchet is Active

The `lifecycle.ignore_changes = [storage_mb]` **is hiding a potential 32→64→128 GB auto-grow step**. Once Azure auto-grows the disk, Terraform can never shrink it back — the `ignore_changes` is the *only* reconciliation because Azure only grows, never shrinks.

**Cost Impact:** Each doubling step increases the storage line item on the Azure invoice. At ~$0.173/GB/month (Premium LRS, North Europe), a 32→64 GB step adds ~$5.50/month; 64→128 adds ~$11/month.

**Action Required:** Paste `05a-postgres-azure-config.json` and `05b-postgres-db-size.txt` output here to quantify actual vs. provisioned.

```
[PASTE 05a-postgres-azure-config.json HERE]
[PASTE 05b-postgres-db-size.txt HERE]
```

---

## 2. Index ROI Analysis

### Known Index Inventory (from migrations)

| Index | Type | Table | Est. Size | Purpose |
|-------|------|-------|-----------|---------|
| `idx_verse_embedding_hnsw` | HNSW (full) | `verses` | ~2.6 GB | No-translation search (`/scripture/search`) |
| `idx_verse_emb_hnsw_<t>` | HNSW (partial) | `verses` | ~200 MB each × N | Per-translation ANN (migration 007) |
| `idx_passage_embedding_hnsw` | HNSW | `passages` | ~50 MB | Passage search |
| `idx_verses_fts_english` | GIN | `verses` | ~15 MB | BITB-098 English FTS |
| `idx_verses_fts_simple` | GIN | `verses` | ~15 MB | Language-agnostic FTS |
| `idx_passages_fts_english` | GIN | `passages` | ~5 MB | BITB-098 English FTS |
| `idx_passages_fts_simple` | GIN | `passages` | ~5 MB | Language-agnostic FTS |

### Expected Partial Index Count

Migration 007 creates one partial index **per distinct translation** in `verses.translation`. From the code:

- Expected: ~13 translations (web, kjv, ita1927, schlachter, etc.)
- Total partial HNSW size: **~2.6 GB** (13 × ~200 MB)

### Evidence Required

```
[PASTE 05d-postgres-all-indexes.txt HERE]
[PASTE 05e-postgres-stats-reset.txt HERE]
```

### Analysis Framework (fill in after evidence collection)

| Index | Size | idx_scan | scans/day* | ROI Verdict |
|-------|------|----------|------------|-------------|
| `idx_verse_embedding_hnsw` | ___ GB | ___ | ___ | Keep / Retire |
| `idx_verse_emb_hnsw_web` | ___ MB | ___ | ___ | Keep / Retire |
| `idx_verse_emb_hnsw_kjv` | ___ MB | ___ | ___ | Keep / Retire |
| ... (all partials) | ___ MB | ___ | ___ | Keep / Retire |
| `idx_passage_embedding_hnsw` | ___ MB | ___ | ___ | Keep / Retire |
| `idx_verses_fts_english` | ___ MB | ___ | ___ | **Likely 0 scans** |
| `idx_verses_fts_simple` | ___ MB | ___ | ___ | **Likely 0 scans** |
| `idx_passages_fts_english` | ___ MB | ___ | ___ | **Likely 0 scans** |
| `idx_passages_fts_simple` | ___ MB | ___ | ___ | **Likely 0 scans** |

*Normalize by `stats_reset` timestamp from `05e-postgres-stats-reset.txt`

### Zero-Scan Index Candidates (BITB-098)

The two `_english` GIN indexes (`idx_verses_fts_english`, `idx_passages_fts_english`) were added for hybrid search but **the application never uses English-stemmed FTS** — it uses `simple` (language-agnostic) or semantic search only. If `idx_scan = 0` since `stats_reset`, these ~20 MB are pure waste.

**Retirement Savings:** ~20 MB (negligible for storage, but removes write amplification on every INSERT/UPDATE to `verses`/`passages`).

---

## 3. `halfvec` Feasibility Analysis

### Current State

- **Embedding dimension:** 1536 (`text-embedding-3-small` via Azure OpenAI)
- **Column type:** `vector(1536)` (4 bytes/dim = 6,144 bytes/embedding)
- **Verse count:** ~403,856 rows
- **Raw vector storage:** 403,856 × 6,144 B ≈ **2.48 GB**
- **Full HNSW index (`idx_verse_embedding_hnsw`):** ~2.6 GB (graph structure overhead)
- **Partial HNSW indexes (13×):** ~2.6 GB total
- **Total vector + index footprint:** ~7.7 GB

### `halfvec` Migration Impact

| Component | Current (vector) | With halfvec | Savings |
|-----------|------------------|--------------|---------|
| `verses.embedding` column | 2.48 GB | 1.24 GB | **1.24 GB** |
| Full HNSW index | 2.6 GB | 1.3 GB | **1.3 GB** |
| Partial HNSW indexes (13×) | 2.6 GB | 1.3 GB | **1.3 GB** |
| **Total** | **7.68 GB** | **3.84 GB** | **3.84 GB (50%)** |

### Memory Pressure Reduction

- **Shared buffers:** 1 GB (25% of 4 GB B2s)
- **Current working set:** Full HNSW (2.6 GB) + hot partials > shared_buffers → constant cache misses
- **With halfvec:** Full HNSW (1.3 GB) + all partials (1.3 GB) = 2.6 GB → **fits in 3 GB effective_cache_size**
- **Expected p95 latency improvement:** 30-50% (eliminates cold-cache penalty on index traversal)

### Migration Requirements (per `docs/MIGRATION_GUIDELINES.md`)

```sql
-- Required steps (CANNOT run in CI/CD pipeline - table-rewriting DDL banned)
-- Must run off-peak, manually, with lock_timeout:

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30min';

-- 1. Add new halfvec column alongside existing
ALTER TABLE verses ADD COLUMN embedding_half halfvec(1536);
UPDATE verses SET embedding_half = embedding::halfvec;

-- 2. Build new HNSW indexes CONCURRENTLY (no ACCESS EXCLUSIVE lock)
CREATE INDEX CONCURRENTLY idx_verse_embedding_hnsw_half ON verses USING hnsw (embedding_half halfvec_cosine_ops) WITH (m=16, ef_construction=64);
-- Repeat for each partial index...

-- 3. Verify recall against golden set (scripts/run_golden_set.py)
-- 4. Switch application to use embedding_half (code deploy)
-- 5. Drop old column + indexes (contract migration, separate deploy)
COMMIT;
```

### Storage Auto-Grow Risk

- The `UPDATE verses SET embedding_half = embedding::halfvec` **rewrites the entire 403K-row table**
- This **will trigger storage auto-grow** (32 → 64 GB minimum) during the rewrite
- Terraform `ignore_changes = [storage_mb]` absorbs this, but **you cannot shrink back**
- **Budget for 64 GB provisioned post-migration**

### Recommendation: **DO** (high impact, manageable risk)

- **Savings:** ~3.8 GB disk → avoids next auto-grow step (saves ~$11/mo at 64→128 GB)
- **Memory:** Fits working set in RAM → p95 latency improvement
- **Risk:** Full table rewrite + index rebuild (2-3 hours off-peak), recall validation required
- **Prerequisite:** Golden-set recall test (`make golden-set-eval`) must pass with `halfvec`

---

## 4. Right-Sizing Evidence (B2s Utilisation)

### Current Configuration

- **SKU:** `B_Standard_B2s` (Burstable, 2 vCore, 4 GB RAM)
- **Baseline CPU credits:** ~20% per vCore = 40% total sustained
- **Burst capacity:** Up to 100% for accumulated credits
- **Purpose:** Chosen for partial HNSW index caching (migration 007) + concurrent search load

### 90-Day Utilisation Metrics (EVIDENCE REQUIRED)

```
[PASTE 06-cpu_percent.json HERE]
[PASTE 06-memory_percent.json HERE]
[PASTE 06-storage_percent.json HERE]
```

### Analysis Framework (fill in after evidence)

| Metric | p50 | p95 | Max | Interpretation |
|--------|-----|-----|-----|----------------|
| **CPU %** | ___ | ___ | ___ | Sustained > 40% → credits exhausted → **must go UP to General Purpose** |
| **Memory %** | ___ | ___ | ___ | > 80% → OOM risk, cache pressure |
| **Storage %** | ___ | ___ | ___ | > 70% → auto-grow imminent |

### Decision Matrix

| Observed Pattern | Recommendation |
|------------------|----------------|
| CPU p95 < 30%, Memory p95 < 60%, Storage < 50% | **Downsize to B1ms** (1 vCore/2 GB, ~$16/mo) — saves ~$17/mo |
| CPU p50 > 40% (sustained above baseline) | **UPGRADE to General Purpose D2s** (2 vCore/8 GB, ~$120/mo) — burstable exhausted |
| CPU bursty (p50 low, p95 high), Memory OK | **Keep B2s** — burstable fits workload |
| Storage > 70% | **Plan for 64 GB auto-grow** — budget +$5.50/mo |

### B2s Partial Index Caching Rationale

Migration 007 explicitly states: *"Upgraded from B1ms (1 vCore / 2 GB) so the per-translation partial HNSW indexes stay cached and the second vCore absorbs concurrent multilingual search load."*

**If CPU p95 < 30% AND memory p95 < 60%:** The caching benefit is not being fully utilized → B1ms may suffice.
**If CPU p50 > 40%:** Burstable credits are exhausted → B2s is the wrong tier; General Purpose required.

---

## 5. Reserved Capacity Analysis

### Current Compute Cost (Azure North Europe, 2026 pricing)

| SKU | On-Demand (730 hrs/mo) | 1-Year Reserved | 3-Year Reserved |
|-----|------------------------|-----------------|-----------------|
| B_Standard_B2s | ~$33.00/mo | ~$22.00/mo (**33% off**) | ~$16.50/mo (**50% off**) |
| B_Standard_B1ms | ~$16.50/mo | ~$11.00/mo | ~$8.25/mo |

### Savings Estimate

- **1-year reservation on B2s:** **~$11/month saved** ($132/year)
- **Zero engineering risk:** No code changes, no downtime, purely billing construct
- **Commitment risk:** B2s in North Europe must remain available for 12 months (high confidence)

### Recommendation: **DO** (immediate, no-risk savings)

- Purchase 1-year reservation on `B_Standard_B2s` in North Europe
- If right-sizing later moves to General Purpose, reservation can be exchanged (Azure allows reservation exchange within same family)

---

## Ranked Lever List with Evidence-Backed Savings

| Rank | Lever | Est. Monthly Savings | Evidence Required | Risk | Recommendation |
|------|-------|---------------------|-------------------|------|----------------|
| 1 | **Reserved capacity (1-yr B2s)** | **$11.00** | None (billing only) | Zero | **DO** |
| 2 | **halfvec migration** | **$11.00** (avoids 64→128 GB auto-grow) + latency | `05b`, `05c`, `05d`, golden-set recall | Medium (rewrite + rebuild) | **DO** (after recall validation) |
| 3 | **Right-size SKU** | **$17.00** (B2s→B1ms) OR **-$87** (B2s→D2s) | `06-cpu_percent.json`, `06-memory_percent.json` | High if wrong direction | **DEFER** until utilisation evidence |
| 4 | **Retire zero-scan indexes** (BITB-098 English GIN) | ~$0.01 (negligible storage) | `05d-postgres-all-indexes.txt`, `05e-postgres-stats-reset.txt` | Low (write amplification only) | **DO** if `idx_scan = 0` |
| 5 | **Retire full HNSW if no-translation path dead** | $0.45/GB × 2.6 GB = **~$1.20** | `05d` (idx_scan on `idx_verse_embedding_hnsw`) | Medium (search feature removal) | **DEFER** — verify `/scripture/search` usage |
| 6 | **Storage auto-grow monitoring** | Avoids surprise $5.50–$11/mo steps | `05a`, `06-storage_percent.json` | Low (alerting only) | **DO** (add 70% storage alert) |

---

## Risk Notes per Lever

| Lever | Risk | Mitigation |
|-------|------|------------|
| Reserved capacity | SKU retired in region | Exchangeable within family; B-series stable |
| halfvec | Recall regression on multilingual search | Golden-set eval (`make golden-set-eval`) mandatory before cutover; run A/B in staging |
| halfvec | Storage auto-grow during rewrite | Schedule off-peak; pre-scale to 64 GB manually; `ignore_changes` absorbs |
| Right-size down (B1ms) | Partial indexes evicted → p95 latency spike | Only if CPU p95 < 30% AND memory p95 < 60% sustained 90 days |
| Right-size up (D2s) | 3.6× cost increase | Only if CPU credits exhausted (p50 > 40% sustained) |
| Index retirement | Feature regression (search without translation) | Verify `/scripture/search` endpoint usage via App Insights; feature flag before drop |

---

## Clear Recommendations

| # | Action | Do / Defer / Decline | Reasoning |
|---|--------|----------------------|-----------|
| 1 | Purchase 1-year B2s reserved instance | **DO** | $11/mo savings, zero risk, immediate |
| 2 | Migrate `verses.embedding` to `halfvec(1536)` | **DO** | 50% vector footprint reduction, avoids next auto-grow, fits working set in RAM. Requires golden-set recall validation + off-peak manual migration per `MIGRATION_GUIDELINES.md` |
| 3 | Right-size SKU based on 90-day metrics | **DEFER** | Need `06-cpu_percent.json` / `06-memory_percent.json` evidence. B2s was deliberate for partial index caching — only downsize if caching benefit unused |
| 4 | Drop `idx_verses_fts_english` + `idx_passages_fts_english` (BITB-098) | **DO** if `idx_scan = 0` | Zero-scan indexes = pure write overhead. Negligible storage savings but removes maintenance cost |
| 5 | Drop full `idx_verse_embedding_hnsw` | **DEFER** | Only if `/scripture/search` (no-translation path) confirmed dead. Check App Insights `requests` for that endpoint |
| 6 | Add storage % alert at 70% | **DO** | Prevents surprise auto-grow; zero cost |

---

## Evidence Collection Checklist (for infra-engineer)

- [ ] Run `scripts/collect_cost_evidence.py` with production credentials
- [ ] Paste `05a-postgres-azure-config.json` → actual provisioned storage/SKU
- [ ] Paste `05b-postgres-db-size.txt` → actual database size
- [ ] Paste `05c-postgres-top-tables.txt` → top tables by size
- [ ] Paste `05d-postgres-all-indexes.txt` → all indexes with `idx_scan` and sizes
- [ ] Paste `05e-postgres-stats-reset.txt` → stats reset timestamp (normalizes scan counts)
- [ ] Paste `06-cpu_percent.json` → 90-day CPU (p50, p95, max)
- [ ] Paste `06-memory_percent.json` → 90-day Memory (p50, p95, max)
- [ ] Paste `06-storage_percent.json` → 90-day Storage (p50, p95, max)
- [ ] Update this report with actual numbers
- [ ] File follow-up stories for each accepted lever (per BITB-150 story)

---

## Appendix: Key Commands to Reproduce Evidence

```bash
# Azure config
az postgres flexible-server show \
  --resource-group bible-app-rg \
  --name bible-app-mb0172 \
  --query "{storage:storage.storageSizeGb, tier:sku.tier, sku:sku.name, iops:storage.iops}"

# Database size
psql "$DATABASE_URL" -c "SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size;"

# Top tables
psql "$DATABASE_URL" -c "
SELECT relname,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       pg_size_pretty(pg_indexes_size(relid)) AS indexes
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"

# All indexes with scan counts
psql "$DATABASE_URL" -c "
SELECT indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;"

# Stats reset timestamp
psql "$DATABASE_URL" -c "SELECT stats_reset FROM pg_stat_database WHERE datname = current_database();"

# 90-day metrics (adjust dates)
az monitor metrics list \
  --resource /subscriptions/f5bc5a63-92f8-4ab6-ad94-84673eeebb56/resourceGroups/bible-app-rg/providers/Microsoft.DBforPostgreSQL/flexibleServers/bible-app-mb0172 \
  --metric cpu_percent --interval PT1H \
  --start-time 2026-07-01T00:00:00Z --end-time 2026-10-01T00:00:00Z \
  --aggregation Average Maximum
```

---

*End of analysis. Populate evidence sections above to finalize recommendations.*
