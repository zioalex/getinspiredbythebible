-- Migration 003: PostgreSQL Performance Tuning for HNSW Indexes
-- =================================================================
--
-- **IMPORTANT:** This migration is REFERENCE-ONLY.
-- Actual configuration changes are applied via Terraform in deployment/main.tf
-- (azurerm_postgresql_flexible_server_configuration resources)
--
-- Purpose: Tune PostgreSQL for optimal HNSW index builds and pgvector query performance
--
-- Issue: During migration 002, the HNSW index build hit maintenance_work_mem limit:
--   NOTICE:  hnsw graph no longer fits into maintenance_work_mem after 14284 tuples
--   DETAIL:  Building will take significantly more time.
--   HINT:  Increase maintenance_work_mem to speed up builds.
--
-- Root Cause: 31K verses × 1024 dims × 4 bytes ≈ 127MB, but maintenance_work_mem = 64MB (default)
--
-- Applied: 2026-02-23 via Terraform (perf/postgresql-tuning PR)
-- Database: Azure PostgreSQL Flexible Server B1ms (2GB RAM, 1 vCore)
--
-- =================================================================

-- For reference, these are the configuration changes applied via Terraform:
-- (DO NOT run these ALTER SYSTEM commands manually - Terraform handles it)

/*
-- 1. Increase maintenance_work_mem to prevent index build spill to disk
ALTER SYSTEM SET maintenance_work_mem = '256MB';
-- Default: 64MB
-- New Value: 256MB (4x increase)
-- Impact: HNSW index builds complete 5-6x faster, entirely in memory

-- 2. Increase shared_buffers for better query caching
ALTER SYSTEM SET shared_buffers = '512MB';
-- Default: ~32MB
-- New Value: 512MB (25% of 2GB RAM - PostgreSQL best practice)
-- Impact: More verses/passages cached in memory, reduces disk I/O

-- 3. Set effective_cache_size for query planner optimization
ALTER SYSTEM SET effective_cache_size = '1.5GB';
-- Default: ~128MB
-- New Value: 1.5GB (75% of 2GB RAM - PostgreSQL best practice)
-- Impact: Query planner makes better decisions for pgvector searches

-- 4. Increase work_mem for complex sorts/joins
ALTER SYSTEM SET work_mem = '16MB';
-- Default: 4MB
-- New Value: 16MB
-- Impact: Faster pgvector similarity searches and ORDER BY operations

-- 5. Enable slow query logging
ALTER SYSTEM SET log_min_duration_statement = 100;
-- Default: -1 (disabled)
-- New Value: 100ms
-- Impact: Log all queries slower than 100ms for performance monitoring

-- 6. Enable checkpoint logging
ALTER SYSTEM SET log_checkpoints = 'on';
-- Default: off
-- New Value: on
-- Impact: Monitor checkpoint frequency and duration for I/O tuning

-- 7. Increase max_wal_size to reduce checkpoint frequency
ALTER SYSTEM SET max_wal_size = '2GB';
-- Default: 1GB
-- New Value: 2GB
-- Impact: Fewer checkpoints = less I/O spikes during write-heavy operations

-- 8. Enable connection logging
ALTER SYSTEM SET log_connections = 'on';
-- Default: off
-- New Value: on
-- Impact: Monitor connection patterns for troubleshooting

-- Reload configuration (Terraform restart handles this)
SELECT pg_reload_conf();
*/

-- =================================================================
-- Verification Queries (run these AFTER Terraform apply)
-- =================================================================

/*
-- Check current PostgreSQL configuration
SELECT
    name,
    setting,
    unit,
    source
FROM pg_settings
WHERE name IN (
    'maintenance_work_mem',
    'shared_buffers',
    'effective_cache_size',
    'work_mem',
    'log_min_duration_statement',
    'log_checkpoints',
    'max_wal_size',
    'log_connections'
)
ORDER BY name;
*/

-- Expected output (after Terraform apply):
--
-- name                         | setting  | unit | source
-- -----------------------------|----------|------|------------------
-- effective_cache_size         | 196608   | 8kB  | configuration file
-- log_checkpoints              | on       |      | configuration file
-- log_connections              | on       |      | configuration file
-- log_min_duration_statement   | 100      | ms   | configuration file
-- maintenance_work_mem         | 262144   | kB   | configuration file
-- max_wal_size                 | 2048     | MB   | configuration file
-- shared_buffers               | 65536    | 8kB  | configuration file
-- work_mem                     | 16384    | kB   | configuration file

-- =================================================================
-- Performance Testing (run these to validate improvements)
-- =================================================================

/*
-- Test HNSW index performance (should be < 50ms)
EXPLAIN ANALYZE
SELECT
    v.id,
    v.book_name,
    v.chapter,
    v.verse_number,
    v.text,
    1 - (v.embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM verses v
WHERE 1 - (v.embedding <=> '[0.1, 0.2, ...]'::vector) > 0.35
ORDER BY v.embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;

-- Expected: Index Scan using idx_verse_embedding_hnsw, execution time < 50ms

-- Check HNSW index usage statistics
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexname IN ('idx_verse_embedding_hnsw', 'idx_passage_embedding_hnsw')
ORDER BY tablename;

-- Expected: idx_scan should be increasing with each semantic search query
*/

-- =================================================================
-- Rollback Instructions
-- =================================================================

-- If needed, revert to default PostgreSQL configuration via Terraform:
-- 1. Comment out or remove the 8 azurerm_postgresql_flexible_server_configuration resources
-- 2. Run: terraform apply
-- 3. Azure will reset parameters to PostgreSQL defaults

-- =================================================================
-- References
-- =================================================================

-- PostgreSQL tuning guides:
-- - https://www.postgresql.org/docs/current/runtime-config-resource.html
-- - https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server
-- - https://pgtune.leopard.in.ua/ (reference calculator)
--
-- pgvector performance:
-- - https://github.com/pgvector/pgvector#performance
-- - https://github.com/pgvector/pgvector#hnsw
--
-- Azure PostgreSQL Flexible Server:
-- - https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-limits
-- - https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/how-to-server-parameters-portal

-- =================================================================
-- End of Migration 003
-- =================================================================
