-- ============================================================================
-- Migration 003: Add full-text search indexes for hybrid search (BITB-018.2)
-- ============================================================================
-- This migration adds PostgreSQL full-text search (FTS) indexes to enable
-- hybrid search combining semantic similarity (pgvector) with keyword matching.
--
-- Indexes created:
-- - idx_verses_fts_english: English language stemming for verses
-- - idx_verses_fts_simple: Language-agnostic exact matching for verses
-- - idx_passages_fts_english: English language stemming for passages
-- - idx_passages_fts_simple: Language-agnostic exact matching for passages
--
-- Index build time: ~30-60 seconds for 31K verses
-- Index size: ~10-15 MB per index (~60 MB total)
-- Query latency impact: +50-200ms for hybrid search
--
-- This migration is idempotent and safe to run multiple times.
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_verses_fts_english') THEN
        CREATE INDEX idx_verses_fts_english ON verses USING GIN (to_tsvector('english', text));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_verses_fts_simple') THEN
        CREATE INDEX idx_verses_fts_simple ON verses USING GIN (to_tsvector('simple', text));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_passages_fts_english') THEN
        CREATE INDEX idx_passages_fts_english ON passages USING GIN (to_tsvector('english', text));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_passages_fts_simple') THEN
        CREATE INDEX idx_passages_fts_simple ON passages USING GIN (to_tsvector('simple', text));
    END IF;
END
$$;

-- ============================================================================
-- Verification Query
-- ============================================================================

SELECT indexname, tablename
FROM pg_indexes
WHERE indexname LIKE 'idx_%_fts_%';
