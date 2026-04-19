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
- `verse_topics` is initially empty — populate via curation scripts or manual tagging
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
