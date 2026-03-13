# Database Migrations

This directory contains SQL migration scripts for the Bible Inspiration Chat database.

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
