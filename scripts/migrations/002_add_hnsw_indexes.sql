-- ============================================================================
-- Migration 002: Replace IVFFlat indexes with HNSW for better performance
-- ============================================================================
-- This migration replaces IVFFlat vector indexes with HNSW (Hierarchical
-- Navigable Small World) indexes for dramatically faster semantic search.
--
-- Expected performance improvement: 40-200x faster queries
-- Index build time: ~5-10 minutes for 31K verses
--
-- HNSW parameters:
-- - m = 16: Number of bi-directional links per layer (sweet spot for recall/speed)
-- - ef_construction = 64: Search depth during index build (higher = better quality)
--
-- Reference: https://github.com/pgvector/pgvector#hnsw
-- ============================================================================

BEGIN;

-- ============================================================================
-- Step 1: Drop existing IVFFlat indexes
-- ============================================================================

DROP INDEX IF EXISTS idx_verse_embedding;
DROP INDEX IF EXISTS idx_passage_embedding;

-- ============================================================================
-- Step 2: Create HNSW indexes (builds in foreground, locks table during build)
-- ============================================================================

-- Verses table HNSW index (31K rows × 1024 dims)
-- Build time: ~3-5 minutes
CREATE INDEX IF NOT EXISTS idx_verse_embedding_hnsw ON verses
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Passages table HNSW index (fewer rows, faster build)
-- Build time: ~30 seconds
CREATE INDEX IF NOT EXISTS idx_passage_embedding_hnsw ON passages
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- Step 3: Set runtime search parameters for optimal recall
-- ============================================================================
-- ef_search controls query-time accuracy/speed tradeoff
-- Default is 40, we set 80 for higher recall at slight speed cost
-- This is a session-level setting, can be adjusted per-query if needed

-- Note: This ALTER DATABASE command sets the default for all sessions.
-- Individual queries can override with: SET hnsw.ef_search = <value>;
ALTER DATABASE bibleapp SET hnsw.ef_search = 80;

COMMIT;

-- ============================================================================
-- Verification Queries (run after migration)
-- ============================================================================

-- Check index sizes:
-- SELECT schemaname, tablename, indexname,
--        pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
-- FROM pg_stat_user_indexes
-- WHERE indexname LIKE '%hnsw%';

-- Check index usage (after some queries):
-- SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
-- FROM pg_stat_user_indexes
-- WHERE indexrelname LIKE '%hnsw%';

-- Test query performance (should be 10-50ms instead of 200-2000ms):
-- EXPLAIN ANALYZE
-- SELECT reference, text, 1 - (embedding <=> '[...]'::vector) AS similarity
-- FROM verses
-- WHERE translation = 'kjv'
-- ORDER BY embedding <=> '[...]'::vector
-- LIMIT 5;
