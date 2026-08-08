# Database Migrations

This directory contains SQL migration scripts for the Vox Quieta database.

## How to Run Migrations

Connect to your database and run the migration script:

```bash
psql $DATABASE_URL -f scripts/migrations/<migration_file>.sql
```

Or for Docker:

```bash
docker exec -i <postgres_container> psql -U <user> -d <dbname> < scripts/migrations/<migration_file>.sql
```

---

## Migration 001: Add Feedback Tables

**File:** `001_add_feedback_tables.py`
**Purpose:** Add tables for user feedback on chat responses.

---

## Migration 002: Replace IVFFlat with HNSW Indexes

**File:** `002_add_hnsw_indexes.sql`
**Purpose:** Dramatically faster semantic search (40-200x improvement).

```bash
psql $DATABASE_URL -f scripts/migrations/002_add_hnsw_indexes.sql
```

---

## Migration 003: Add Full-Text Search Indexes

**File:** `003_add_fulltext_index.sql`
**Date:** 2026-02-24
**PR:** BITB-018.2
**Purpose:** Enable hybrid search (semantic + keyword matching)

### Prerequisites

- PostgreSQL 9.6+ (Azure DB is 14+)
- Database connection with CREATE INDEX permission

### Run Migration

```bash
psql $DATABASE_URL -f scripts/migrations/003_add_fulltext_index.sql
```

### Verify

```sql
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE indexname LIKE 'idx_%_fts_%';
-- Expected: 4 indexes (verses_english, verses_simple, passages_english, passages_simple)
```

### Rollback (if needed)

```sql
DROP INDEX IF EXISTS idx_verses_fts_english;
DROP INDEX IF EXISTS idx_verses_fts_simple;
DROP INDEX IF EXISTS idx_passages_fts_english;
DROP INDEX IF EXISTS idx_passages_fts_simple;
```

### Performance Impact

- Index creation: ~30-60 seconds on production DB (31,102 verses)
- Index size: ~10-15 MB per index (~60 MB total for 4 indexes)
- Query latency: +50-200ms for hybrid search (total <2s)
- Safe to run multiple times (idempotent)

---

## Migration 004: Add verse_topics Junction Table for Topic Boosting

**File:** `004_add_topic_boosting_schema.sql`
**Date:** 2026-02-24
**PR:** BITB-018.3
**Purpose:** Enable topic-based score boosting for semantic/hybrid search

### What This Migration Does

1. Creates `verse_topics` junction table linking verses to topics
2. Adds indexes on `verse_id` and `topic_id` for fast JOIN queries
3. Seeds 13 initial biblical topics (peace, forgiveness, faith, etc.)

### Prerequisites (Migration 004)

- `topics` table must already exist (created in `scripts/init.sql`)
- `verses` table must already exist

### Run Migration (Migration 004)

```bash
psql $DATABASE_URL -f scripts/migrations/004_add_topic_boosting_schema.sql
```

### Verify (Migration 004)

```sql
-- Check tables exist
SELECT tablename FROM pg_tables WHERE tablename IN ('topics', 'verse_topics');

-- Check seeded topics
SELECT name, description FROM topics ORDER BY name;

-- Check indexes
SELECT indexname FROM pg_indexes WHERE tablename = 'verse_topics';
```

### Rollback (Migration 004)

```sql
DROP TABLE IF EXISTS verse_topics;
-- Topics table is kept (it existed before this migration)
-- To remove seeded topics: DELETE FROM topics WHERE name IN ('anxiety', 'peace', ...);
```

### Performance Impact (Migration 004)

- Table creation: instant
- Index creation: instant (empty table)
- `verse_topics` is initially empty — populate with `scripts/populate_verse_topics.py`
  (BITB-044; see `docs/HOW-TO-POPULATE-VERSE-TOPICS.md`)
- Topic-boosted queries add ~1 LEFT JOIN: +50-100ms latency when topics match
- No impact when `TOPIC_BOOSTING_ENABLED=false` (feature flag default)

### Enabling Topic Boosting

Set in `api/.env`:

```env
TOPIC_BOOSTING_ENABLED=true
TOPIC_BOOST_FACTOR=0.2
```

The `TOPIC_BOOST_FACTOR` controls the multiplicative boost per matching topic:

- `0.2` = 20% boost per topic (default)
- Example: verse with 2 matching topics → `score * 1.4`

---

## Migration 005: Schedule daily purge of `blocked_message_samples`

**File:** `005_schedule_blocked_samples_purge.sql`
**Date:** 2026-05-19
**Purpose:** Replace startup-only TTL with a `pg_cron`-driven daily DELETE
so expired `blocked_message_samples` rows are reclaimed even when the API
container does not restart for long stretches.

### Prerequisites

1. `pg_cron` must be allow-listed via the `azure.extensions` server
   parameter (`deployment/main.tf` already includes it alongside
   `vector,uuid-ossp`). Restart the Postgres flexible server after
   updating this parameter.
2. `cron.database_name` must point at the app database (managed by the
   `cron_database_name` resource in `deployment/main.tf`). Restart again.
3. Run the migration as a superuser:

```bash
psql $DATABASE_URL -f scripts/migrations/005_schedule_blocked_samples_purge.sql
```

### Behaviour

- Job name: `purge-blocked-message-samples`
- Schedule: `15 3 * * *` (daily, 03:15 UTC)
- Statement: `DELETE FROM blocked_message_samples WHERE expires_at < now()`
- Idempotent: re-running the migration replaces any existing schedule of
  the same name.
- The app-side startup purge in `api/main.py` is kept as a backstop.

### Rollback (Migration 005)

```sql
SELECT cron.unschedule('purge-blocked-message-samples');
-- Optional: remove pg_cron from azure.extensions in Terraform.
```

### Verify

```sql
SELECT jobid, jobname, schedule, command
FROM cron.job
WHERE jobname = 'purge-blocked-message-samples';

-- Recent runs:
SELECT runid, jobid, status, start_time, end_time, return_message
FROM cron.job_run_details
WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'purge-blocked-message-samples')
ORDER BY start_time DESC
LIMIT 5;
```

---

## Migration 007: Per-translation partial HNSW indexes for verse search

**File:** `007_partial_hnsw_verse_indexes.py`
**Date:** 2026-06-24
**Purpose:** Phase 2 chat-latency fix. Replace reliance on the single full HNSW
index (`idx_verse_embedding_hnsw`) for per-language chat search with one **partial**
HNSW index per translation. (`hnsw.ef_search` is tuned by the application per
session, not by this migration — see the note below.)

### Why

The full index returns `hnsw.ef_search` nearest neighbours across **all**
translations, then the `WHERE translation = :t` filter drops the non-matching rows
*after* the index scan — thinning the candidate pool (observed 32 kept / 48 removed
at `ef_search = 80`) and hurting recall. A partial index per translation
(`... WHERE translation = '<t>'`) is filtered *by the index*: no post-filter, the
`LIMIT` fills, and the per-query working set drops ~12× (each partial ≈ 220 MB vs
the 2.6 GB full index).

> **Why this migration no longer touches `hnsw.ef_search`.** The ANN still needs
> `ef_search ≥ vector_candidate_pool` (≥ 120) to return a full pool, but managed
> Postgres (Azure Flexible Server, AWS RDS) refuses to *persist* that GUC at the
> database/role level — `ALTER DATABASE ... SET hnsw.ef_search` raises
> `permission denied to set parameter` even for the admin role, and an earlier
> version of this migration failed CI with exactly that error. The knob now lives
> in the API connection pool, which runs `SET hnsw.ef_search` per session on connect
> (`api/scripture/database.py`); a session-level SET needs no special privilege and
> is the vendor-recommended way to tune it.

### Why a `.py` migration

`CREATE INDEX CONCURRENTLY` cannot run inside a transaction block, but the SQL
runner executes a whole `.sql` file in one implicit transaction. This `.py`
migration issues each `CONCURRENTLY` build as its own autocommit statement. It
**discovers translations dynamically** (`SELECT DISTINCT translation FROM verses`),
so the index set never drifts from a hard-coded list.

### Prerequisites

- `verses` table populated (the migration indexes the translations it finds).
- `pg_prewarm` allow-listed via `azure.extensions` (added in `deployment/main.tf`)
  for the optional cache-warming step — non-fatal if missing.
- The full `idx_verse_embedding_hnsw` index is **kept** for the no-translation
  `/scripture/search` path.

### Run

```bash
psql is not used; run via the migration runner (or directly):
python scripts/migrations/007_partial_hnsw_verse_indexes.py
```

### Verify

```sql
-- One partial index per translation, each with a WHERE predicate:
SELECT indexname, indexdef FROM pg_indexes
WHERE tablename = 'verses' AND indexname LIKE 'idx_verse_emb_hnsw_%';

-- ef_search applied at the database level:
SELECT setting FROM pg_settings WHERE name = 'hnsw.ef_search';  -- expect 120

-- EXPLAIN should now use the partial index with NO post-filter:
-- EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM verses
--   WHERE embedding IS NOT NULL AND translation = 'valera'
--   ORDER BY embedding <=> '<vec>'::vector LIMIT 100;
-- -> Index Scan using idx_verse_emb_hnsw_valera, Rows Removed by Filter: 0
```

### Rollback

```sql
-- Drop the partial indexes (full index is untouched):
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT indexname FROM pg_indexes
           WHERE tablename = 'verses' AND indexname LIKE 'idx_verse_emb_hnsw_%'
  LOOP EXECUTE 'DROP INDEX IF EXISTS ' || quote_ident(r.indexname); END LOOP;
END $$;
-- Optionally restore the previous ef_search:
-- ALTER DATABASE <db> SET hnsw.ef_search = 80;
```

### Performance impact

- Build: each partial covers ~1/12th of the verses (~2.6k rows) and builds in
  seconds; `CONCURRENTLY` keeps `verses` readable throughout.
- Disk: ~2.6 GB total for the partials (on top of the 2.6 GB full index) — fits the
  32 GB volume. On a 4 GB box (`B2s`) only the *active* languages' partials need to
  stay hot; see `scripts/perf/search_concurrency_test.py` to measure whether 4 GB
  suffices under concurrent multilingual load.

## Migration 011: HNSW index on `topics.embedding` (BITB-062)

Numbered 011, not 009 — PR #866 (rate limiter, open at the time this migration was
written) already claims 009/010.

### Why

`search_topics_semantic` already queries with the index-friendly
`ORDER BY embedding <=> q LIMIT n` shape, but `topics.embedding` had no vector index —
every call was a full sequential scan. Unlike `verses`/`passages`, `topics` is small
(tens to low hundreds of rows), so one plain HNSW index (no per-translation
partitioning) is sufficient.

### Why a `.py` migration

Same reason as migration 007: `CREATE INDEX CONCURRENTLY` cannot run inside the
implicit transaction the `.sql` runner uses.

### Run

```bash
python scripts/migrations/011_add_topic_hnsw_index.py
```

### Verify

```sql
SELECT indexname, indexdef FROM pg_indexes
WHERE tablename = 'topics' AND indexname = 'idx_topic_embedding_hnsw';
```

### Rollback

```sql
DROP INDEX IF EXISTS idx_topic_embedding_hnsw;
```
